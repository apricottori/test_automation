# core/sequence_player.py
import time
import sys 
from typing import List, Tuple, Dict, Any, Optional, ForwardRef 

from PyQt5.QtCore import QObject, pyqtSignal
# pyqtSlot은 현재 이 파일에서 직접 사용되지 않으므로, 필요하면 나중에 추가합니다.
# from PyQt5.QtCore import pyqtSlot 

from . import constants
from .helpers import normalize_hex_input
from .register_map_backend import RegisterMap
from .hardware_control import I2CDevice, Multimeter, Sourcemeter, Chamber # Chamber 임포트 확인

# main_window.RegMapWindow에 대한 Forward Reference 정의
# main_window.py가 프로젝트 루트에 있다고 가정합니다.
# 이 ForwardRef는 SequencePlayer가 main_window의 메소드를 호출할 때 타입 힌팅을 위해 사용됩니다.
RegMapWindowType = ForwardRef('main_window.RegMapWindow')


class SequencePlayer(QObject):
    """
    테스트 시퀀스를 실제로 실행하는 워커 클래스입니다.
    QThread에서 실행되어 GUI의 반응성을 유지합니다.
    """
    log_message_signal = pyqtSignal(str)
    measurement_result_signal = pyqtSignal(str, object, str, dict) 
    sequence_finished_signal = pyqtSignal(bool, str) 
    
    def __init__(self,
                 sequence_items: List[str],
                 current_settings: Dict[str, Any],
                 register_map_instance: Optional[RegisterMap],
                 i2c_device_instance: Optional[I2CDevice],
                 multimeter_instance: Optional[Multimeter],
                 sourcemeter_instance: Optional[Sourcemeter],
                 chamber_instance: Optional[Chamber], # Chamber 인스턴스 타입 힌트
                 sample_number: Optional[str],
                 main_window_ref: Optional[RegMapWindowType], 
                 parent: Optional[QObject] = None): 
        super().__init__(parent)
        self.sequence_items = sequence_items
        self.settings = current_settings if current_settings is not None else {}
        self.register_map = register_map_instance
        self.i2c_device = i2c_device_instance
        self.multimeter = multimeter_instance
        self.sourcemeter = sourcemeter_instance
        self.chamber = chamber_instance # Chamber 인스턴스 저장
        self.sample_number = sample_number if sample_number else ""
        self.main_window_ref = main_window_ref
        
        self.request_stop_flag: bool = False 
        
        self._current_smu_set_voltage: Optional[float] = None
        self._current_smu_set_current: Optional[float] = None
        self._current_chamber_set_temp: Optional[float] = None

    def _parse_sequence_item(self, item_text: str) -> Tuple[Optional[str], Dict[str, str]]:
        try:
            item_text_stripped = item_text.lstrip() 
            action_type_str, params_str = item_text_stripped.split(":", 1)
            action_type_str = action_type_str.strip()
            params_dict = {}
            if params_str.strip():
                param_pairs = params_str.split(';')
                for pair in param_pairs:
                    if '=' in pair: 
                        key, value = pair.split('=', 1)
                        params_dict[key.strip()] = value.strip()
            return action_type_str, params_dict
        except ValueError: 
            self.log_message_signal.emit(f"Error: 시퀀스 아이템 파싱 실패 - '{item_text_stripped if 'item_text_stripped' in locals() else item_text}'")
            return None, {}

    def _get_current_conditions(self) -> Dict[str, Any]:
        if self.main_window_ref and hasattr(self.main_window_ref, 'get_current_measurement_conditions'):
            try:
                return self.main_window_ref.get_current_measurement_conditions()
            except Exception as e:
                self.log_message_signal.emit(f"Warning: main_window_ref.get_current_measurement_conditions 호출 중 오류: {e}. 내부 캐시 사용.")
        
        conditions: Dict[str, Any] = {}
        # hardware_control.py의 GPIBDevice에서 캐시된 값을 가져오도록 수정됨.
        # SequencePlayer 내부 캐시는 main_window_ref가 없을 경우의 fallback으로 유지하거나,
        # main_window_ref.get_current_measurement_conditions()가 항상 최신 캐시를 제공한다고 가정하고 제거 가능.
        # 여기서는 main_window_ref 우선, 실패 시 SequencePlayer 내부 캐시 사용.
        if self.sourcemeter: # SMU 장비가 있을 때만 캐시 접근 시도
            if self.sourcemeter.get_cached_set_voltage() is not None:
                 conditions[constants.EXCEL_COL_COND_SMU_V] = self.sourcemeter.get_cached_set_voltage()
            if self.sourcemeter.get_cached_set_current() is not None:
                 conditions[constants.EXCEL_COL_COND_SMU_I] = self.sourcemeter.get_cached_set_current()
        if self.chamber: # Chamber 장비가 있을 때만 캐시 접근 시도
            if self.chamber.get_cached_target_temperature() is not None:
                 conditions[constants.EXCEL_COL_COND_CHAMBER_T] = self.chamber.get_cached_target_temperature()
        return conditions

    def run_sequence(self):
        total_steps = len(self.sequence_items)
        self.log_message_signal.emit(f"시퀀스 실행 시작... (총 {total_steps} 단계, Sample: {self.sample_number})")

        loop_stack: List[Dict[str, Any]] = [] 
        current_item_index = 0
        halt_on_error = self.settings.get("error_halts_sequence", False)

        # Chamber 중단 플래그 참조 설정 (Chamber 액션 실행 전에 수행)
        if self.chamber and hasattr(self.chamber, 'set_stop_flag_ref'):
            self.chamber.set_stop_flag_ref(self) # SequencePlayer 인스턴스(self)를 전달

        while current_item_index < len(self.sequence_items):
            if self.request_stop_flag:
                self.log_message_signal.emit("시퀀스 실행 중단 요청됨.")
                self.sequence_finished_signal.emit(False, constants.MSG_SEQUENCE_PLAYBACK_ABORTED)
                return

            item_text = self.sequence_items[current_item_index]
            self.log_message_signal.emit(f"\n--- 단계 {current_item_index + 1}/{total_steps}: {item_text.strip()} ---")
            
            action_type, params = self._parse_sequence_item(item_text)
            if not action_type: 
                error_msg_parse = f"단계 {current_item_index + 1} 파싱 실패."
                self.log_message_signal.emit(f"Error: {error_msg_parse}")
                if halt_on_error:
                    self.sequence_finished_signal.emit(False, error_msg_parse + " 시퀀스 중단됨.")
                    return
                current_item_index += 1
                continue

            step_success = False 
            error_msg = ""
            modified_params = params.copy() 
            
            # --- 루프 처리 로직 ---
            if action_type == constants.SEQ_PREFIX_LOOP_START:
                if loop_stack: 
                    error_msg = "중첩 루프는 현재 지원되지 않습니다 (LOOP_START 발견)."
                else:
                    try:
                        loop_params_from_item = {
                            'target_action_original_index': int(params[constants.SEQ_PARAM_KEY_LOOP_ACTION_INDEX]),
                            'target_param_key': params[constants.SEQ_PARAM_KEY_LOOP_TARGET_PARAM_KEY],
                            'current_value': float(params[constants.SEQ_PARAM_KEY_LOOP_START_VALUE]),
                            'step_value': float(params[constants.SEQ_PARAM_KEY_LOOP_STEP_VALUE]),
                            'end_value': float(params[constants.SEQ_PARAM_KEY_LOOP_END_VALUE]),
                            'loop_block_start_item_index': current_item_index + 1, 
                            'loop_block_end_item_index': -1 
                        }
                        for k_idx in range(current_item_index + 1, len(self.sequence_items)):
                            end_action_type_check, _ = self._parse_sequence_item(self.sequence_items[k_idx])
                            if end_action_type_check == constants.SEQ_PREFIX_LOOP_END:
                                loop_params_from_item['loop_block_end_item_index'] = k_idx
                                break
                        if loop_params_from_item['loop_block_end_item_index'] == -1:
                            raise ValueError("Matching LOOP_END not found for LOOP_START.")
                        loop_stack.append(loop_params_from_item)
                        self.log_message_signal.emit(f"  Loop Start: TargetParam='{loop_params_from_item['target_param_key']}' on Step {loop_params_from_item['target_action_original_index']+1}, Range=[{loop_params_from_item['current_value']:.4g} to {loop_params_from_item['end_value']:.4g} step {loop_params_from_item['step_value']:.4g}]")
                        step_success = True
                    except (KeyError, ValueError) as e: error_msg = f"루프 시작 파라미터 파싱 오류: {e}"
                
                if error_msg: self.log_message_signal.emit(f"  Error: {error_msg}")
                if not step_success and halt_on_error:
                    self.sequence_finished_signal.emit(False, f"루프 시작 오류로 중단: {error_msg}")
                    return
                current_item_index += 1 
                continue

            elif action_type == constants.SEQ_PREFIX_LOOP_END:
                if not loop_stack: error_msg = "짝이 맞지 않는 LOOP_END를 만났습니다."
                else:
                    current_loop = loop_stack[-1] 
                    current_loop['current_value'] += current_loop['step_value']
                    loop_iteration_finished = False
                    if current_loop['step_value'] == 0: loop_iteration_finished = True; error_msg += " 루프 스텝 값이 0이므로 루프를 강제 종료합니다."
                    elif current_loop['step_value'] > 0:
                        if current_loop['current_value'] > current_loop['end_value']: loop_iteration_finished = True
                    else: 
                        if current_loop['current_value'] < current_loop['end_value']: loop_iteration_finished = True
                    if loop_iteration_finished:
                        loop_stack.pop(); self.log_message_signal.emit(f"  Loop End (모든 반복 완료). {error_msg if error_msg else ''}")
                    else:
                        current_item_index = current_loop['loop_block_start_item_index']; self.log_message_signal.emit(f"  Looping: Next value for '{current_loop['target_param_key']}' = {current_loop['current_value']:.4g}"); continue 
                step_success = not bool(error_msg)
                if error_msg: self.log_message_signal.emit(f"  Error: {error_msg}")
                if not step_success and halt_on_error:
                    self.sequence_finished_signal.emit(False, f"루프 종료 오류로 중단: {error_msg}"); return
                current_item_index += 1; continue
            
            if loop_stack: 
                active_loop = loop_stack[-1]
                if current_item_index == active_loop['target_action_original_index']:
                    target_key_in_action = active_loop['target_param_key']
                    if target_key_in_action in modified_params:
                        current_loop_val_num = active_loop['current_value']
                        new_val_str_for_action = ""
                        if target_key_in_action == constants.SEQ_PARAM_KEY_VALUE and \
                           action_type in [constants.SEQ_PREFIX_I2C_WRITE_NAME, constants.SEQ_PREFIX_I2C_WRITE_ADDR] and \
                           self.register_map:
                            num_hex_digits = 2 
                            if action_type == constants.SEQ_PREFIX_I2C_WRITE_NAME:
                                field_name_for_length = modified_params.get(constants.SEQ_PARAM_KEY_TARGET_NAME)
                                if field_name_for_length:
                                    target_field_info = self.register_map.logical_fields_map.get(field_name_for_length)
                                    if target_field_info: num_hex_digits = (target_field_info['length'] + 3) // 4
                            try: new_val_str_for_action = f"0x{int(current_loop_val_num):0{max(1, num_hex_digits)}X}"
                            except ValueError: new_val_str_for_action = str(current_loop_val_num) 
                        else: new_val_str_for_action = f"{current_loop_val_num:.6g}" 
                        self.log_message_signal.emit(f"    Loop Override: Param '{target_key_in_action}' of '{action_type}' = {modified_params[target_key_in_action]} -> {new_val_str_for_action}")
                        modified_params[target_key_in_action] = new_val_str_for_action
            
            # --- 실제 액션 실행 ---
            try:
                current_conditions = self._get_current_conditions()

                if action_type == constants.SEQ_PREFIX_I2C_WRITE_NAME:
                    name = modified_params.get(constants.SEQ_PARAM_KEY_TARGET_NAME)
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE)
                    if self.i2c_device and self.register_map and name and val_str:
                        field_info = self.register_map.logical_fields_map.get(name)
                        if not field_info: error_msg = constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)
                        else:
                            try:
                                val_int = int(normalize_hex_input(val_str) or "0", 16)
                                if val_int >= (1 << field_info['length']):
                                    error_msg = constants.MSG_VALUE_EXCEEDS_WIDTH.format(value=val_str, field_id=name, length=field_info['length'])
                                else:
                                    i2c_ops, vals_to_confirm = self.register_map.set_logical_field_value(name, val_int)
                                    if not i2c_ops: self.log_message_signal.emit(f"  Register '{name}' 값 변경 없음 (이미 {val_str})."); step_success = True
                                    else:
                                        all_writes_ok = True
                                        for op_addr, op_val in i2c_ops:
                                            op_val_hex = f"0x{op_val:02X}"
                                            if not self.i2c_device.write(op_addr, op_val_hex):
                                                all_writes_ok = False; error_msg += f"I2C Write 실패 (Addr: {op_addr}, Val: {op_val_hex}); "; break
                                        if all_writes_ok:
                                            self.register_map.confirm_address_values_update(vals_to_confirm)
                                            self.log_message_signal.emit(f"  Register '{name}'에 {val_str} 쓰기 완료."); step_success = True
                            except ValueError: error_msg = constants.MSG_CANNOT_PARSE_HEX_FOR_FIELD.format(value=val_str)
                    elif not self.i2c_device: error_msg = "I2C 장치가 초기화되지 않았습니다."
                    elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                    else: error_msg = "Name/Value 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_I2C_WRITE_ADDR:
                    addr = modified_params.get(constants.SEQ_PARAM_KEY_ADDRESS)
                    val_hex = modified_params.get(constants.SEQ_PARAM_KEY_VALUE) 
                    if self.i2c_device and self.register_map and addr and val_hex:
                        norm_addr = normalize_hex_input(addr, 4); norm_val_hex = normalize_hex_input(val_hex, 2) 
                        if norm_addr is None or norm_val_hex is None: error_msg = f"잘못된 주소({addr}) 또는 값({val_hex}) 형식"
                        else:
                            val_int = int(norm_val_hex, 16)
                            i2c_ops, vals_to_confirm = self.register_map.set_address_byte_value(norm_addr, val_int)
                            if not i2c_ops: self.log_message_signal.emit(f"  Address '{norm_addr}' 값 변경 없음 (이미 {norm_val_hex})."); step_success = True
                            elif self.i2c_device.write(norm_addr, norm_val_hex):
                                self.register_map.confirm_address_values_update(vals_to_confirm)
                                self.log_message_signal.emit(f"  I2C Write Addr: {norm_addr}, Val: {norm_val_hex} -> Success"); step_success = True
                            else: error_msg = f"I2C Write 실패 (Addr: {norm_addr}, Val: {norm_val_hex})"
                    elif not self.i2c_device: error_msg = "I2C 장치가 초기화되지 않았습니다."
                    elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                    else: error_msg = "주소/값 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_I2C_READ_NAME:
                    name = modified_params.get(constants.SEQ_PARAM_KEY_TARGET_NAME); var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                    if self.register_map and name and var_name:
                        read_val_hex = self.register_map.get_logical_field_value_hex(name, from_initial=False)
                        if constants.HEX_ERROR_NO_FIELD in read_val_hex or constants.HEX_ERROR_CONVERSION in read_val_hex : error_msg = f"Register '{name}' 읽기 오류: {read_val_hex}"
                        else: self.measurement_result_signal.emit(var_name, read_val_hex, self.sample_number, current_conditions); self.log_message_signal.emit(f"  Register '{name}' 읽기 값: {read_val_hex} (저장 변수: {var_name})"); step_success = True
                    elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                    else: error_msg = "Name/Variable 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_I2C_READ_ADDR:
                    addr = modified_params.get(constants.SEQ_PARAM_KEY_ADDRESS); var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                    if self.i2c_device and self.register_map and addr and var_name:
                        norm_addr = normalize_hex_input(addr, 4)
                        if norm_addr is None: error_msg = f"잘못된 주소 형식: {addr}"
                        else:
                            read_hw_success, read_val_int = self.i2c_device.read(norm_addr)
                            if read_hw_success and read_val_int is not None:
                                self.register_map.confirm_address_values_update({norm_addr: read_val_int})
                                read_val_hex = f"0x{read_val_int:02X}"
                                self.measurement_result_signal.emit(var_name, read_val_hex, self.sample_number, current_conditions)
                                self.log_message_signal.emit(f"  I2C Read Addr: {norm_addr}, 값: {read_val_hex} (저장 변수: {var_name})"); step_success = True
                            else: error_msg = f"I2C Read 실패 (Addr: {norm_addr})"
                    elif not self.i2c_device: error_msg = "I2C 장치가 초기화되지 않았습니다."
                    elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                    else: error_msg = "Address/Variable 파라미터 누락"
                
                elif action_type == constants.SEQ_PREFIX_DELAY:
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_SECONDS)
                    if val_str:
                        try: delay_sec = float(val_str)
                        except ValueError: error_msg = f"지연 시간 값 '{val_str}' 오류"
                        else:
                            if delay_sec > 0: self.log_message_signal.emit(f"  {delay_sec}초 동안 대기..."); time.sleep(delay_sec); step_success = True
                            else: error_msg = "지연 시간은 0보다 커야 함"
                    else: error_msg = "지연 시간 파라미터 누락"

                # --- DMM, SMU, Chamber 액션 (hardware_control.py의 캐시 업데이트 로직 활용) ---
                elif action_type == constants.SEQ_PREFIX_MM_MEAS_V:
                    var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                    if self.multimeter and self.settings.get("multimeter_use") and var_name:
                        s, v = self.multimeter.measure_voltage()
                        if s and v is not None: self.measurement_result_signal.emit(var_name, v, self.sample_number, current_conditions); self.log_message_signal.emit(f"  Multimeter V: {v:.6f} (Var: {var_name})"); step_success = True
                        else: error_msg = "Multimeter 전압 측정 실패"
                    elif not self.settings.get("multimeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Multimeter")
                    elif not self.multimeter: error_msg = "Multimeter가 초기화되지 않았습니다."
                    else: error_msg = "변수명 누락"

                elif action_type == constants.SEQ_PREFIX_MM_MEAS_I:
                    var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                    if self.multimeter and self.settings.get("multimeter_use") and var_name:
                        s, curr = self.multimeter.measure_current()
                        if s and curr is not None: self.measurement_result_signal.emit(var_name, curr, self.sample_number, current_conditions); self.log_message_signal.emit(f"  Multimeter I: {curr:.6e} (Var: {var_name})"); step_success = True
                        else: error_msg = "Multimeter 전류 측정 실패"
                    elif not self.settings.get("multimeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Multimeter")
                    elif not self.multimeter: error_msg = "Multimeter가 초기화되지 않았습니다."
                    else: error_msg = "변수명 누락"

                elif action_type == constants.SEQ_PREFIX_MM_SET_TERMINAL:
                    term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL)
                    if self.multimeter and self.settings.get("multimeter_use") and term:
                        step_success = self.multimeter.set_terminal(term)
                        if step_success: self.log_message_signal.emit(f"  Multimeter 터미널 {term}으로 설정.")
                        else: error_msg = f"Multimeter 터미널 설정 실패 ({term})"
                    elif not self.settings.get("multimeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Multimeter")
                    elif not self.multimeter: error_msg = "Multimeter가 초기화되지 않았습니다."
                    else: error_msg = "터미널 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_SM_SET_V:
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE); term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and val_str:
                        try: 
                            val_float = float(val_str)
                            step_success = self.sourcemeter.set_voltage(val_float, term) 
                            if step_success: self.log_message_signal.emit(f"  SM Set V: {val_float:.3f}V on {term}")
                            else: error_msg = f"SM 전압 설정 실패 ({val_float}V, {term})"
                        except ValueError: error_msg = f"SM 전압 값 '{val_str}' 오류"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "값 파라미터 누락"
                
                elif action_type == constants.SEQ_PREFIX_SM_SET_I:
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE); term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and val_str:
                        try: 
                            val_float = float(val_str)
                            step_success = self.sourcemeter.set_current(val_float, term) 
                            if step_success: self.log_message_signal.emit(f"  SM Set I: {val_float:.3e}A on {term}")
                            else: error_msg = f"SM 전류 설정 실패 ({val_float}A, {term})"
                        except ValueError: error_msg = f"SM 전류 값 '{val_str}' 오류"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "값 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_SM_MEAS_V:
                    var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE); term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and var_name:
                        s, v = self.sourcemeter.measure_voltage(term)
                        if s and v is not None: self.measurement_result_signal.emit(var_name, v, self.sample_number, current_conditions); self.log_message_signal.emit(f"  SM V ({term}): {v:.4f} (Var: {var_name})"); step_success = True
                        else: error_msg = f"SM 전압 측정 실패 ({term})"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "변수명 누락"

                elif action_type == constants.SEQ_PREFIX_SM_MEAS_I:
                    var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE); term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and var_name:
                        s, curr = self.sourcemeter.measure_current(term)
                        if s and curr is not None: self.measurement_result_signal.emit(var_name, curr, self.sample_number, current_conditions); self.log_message_signal.emit(f"  SM I ({term}): {curr:.4e} (Var: {var_name})"); step_success = True
                        else: error_msg = f"SM 전류 측정 실패 ({term})"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "변수명 누락"

                elif action_type == constants.SEQ_PREFIX_SM_ENABLE_OUTPUT:
                    state_str = modified_params.get(constants.SEQ_PARAM_KEY_STATE, "TRUE").upper()
                    if self.sourcemeter and self.settings.get("sourcemeter_use"):
                        state_bool = (state_str == "TRUE"); step_success = self.sourcemeter.enable_output(state_bool)
                        if step_success: self.log_message_signal.emit(f"  SM Output: {state_str}")
                        else: error_msg = f"SM 출력 상태 변경 실패 ({state_str})"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "상태 파라미터 누락" 

                elif action_type == constants.SEQ_PREFIX_SM_SET_TERMINAL:
                    term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and term:
                        step_success = self.sourcemeter.set_terminal(term)
                        if step_success: self.log_message_signal.emit(f"  SM 터미널 {term}으로 설정.")
                        else: error_msg = f"SM 터미널 설정 실패 ({term})"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "터미널 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_SM_SET_PROTECTION_I:
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_CURRENT_LIMIT)
                    if self.sourcemeter and self.settings.get("sourcemeter_use") and val_str:
                        try:
                            limit_float = float(val_str)
                            step_success = self.sourcemeter.set_protection_current(limit_float)
                            if step_success: self.log_message_signal.emit(f"  SM Protection Current: {limit_float:.3e}A")
                            else: error_msg = f"SM 보호 전류 설정 실패 ({limit_float:.3e}A)"
                        except ValueError: error_msg = f"SM 보호 전류 값 '{val_str}' 오류"
                    elif not self.settings.get("sourcemeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Sourcemeter")
                    elif not self.sourcemeter: error_msg = "Sourcemeter가 초기화되지 않았습니다."
                    else: error_msg = "전류 제한 값 파라미터 누락"

                elif action_type == constants.SEQ_PREFIX_CHAMBER_SET_TEMP:
                    val_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE)
                    if self.chamber and self.settings.get("chamber_use") and val_str:
                        try:
                            temp_float = float(val_str)
                            if self.chamber.set_target_temperature(temp_float): 
                                if self.chamber.start_operation():
                                    self.log_message_signal.emit(f"  Chamber 목표 온도 {temp_float}°C 설정 및 동작 시작.")
                                    step_success = True
                                else: error_msg = "Chamber 동작 시작 실패"
                            else: error_msg = f"Chamber 목표 온도 설정 실패 ({temp_float}°C)"
                        except ValueError: error_msg = f"Chamber 온도 값 '{val_str}' 오류"
                    elif not self.settings.get("chamber_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Chamber")
                    elif not self.chamber: error_msg = "Chamber가 초기화되지 않았습니다."
                    else: error_msg = "온도 값 파라미터 누락"
                
                elif action_type == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP:
                    target_temp_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE)
                    timeout_str = modified_params.get(constants.SEQ_PARAM_KEY_TIMEOUT, str(constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC))
                    tolerance_str = modified_params.get(constants.SEQ_PARAM_KEY_TOLERANCE, str(constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG))

                    if self.chamber and self.settings.get("chamber_use") and target_temp_str:
                        try:
                            target_temp_float = float(target_temp_str); timeout_float = float(timeout_str); tolerance_float = float(tolerance_str)
                            # Chamber.is_temperature_stable은 내부적으로 self.request_stop_flag를 확인 (hardware_control.py 수정됨)
                            is_stable, last_temp = self.chamber.is_temperature_stable(target_temp_float, tolerance_float, timeout_float)
                            
                            if self.request_stop_flag: error_msg = "온도 안정화 대기 중 중단됨." # is_temperature_stable 내부에서도 확인하지만, 여기서도 한번 더 확인
                            elif is_stable: self.log_message_signal.emit(constants.MSG_CHAMBER_TEMP_STABLE.format(target_temp=target_temp_float, current_temp=last_temp if last_temp is not None else "N/A")); step_success = True
                            else: error_msg = constants.MSG_CHAMBER_TEMP_TIMEOUT.format(target_temp=target_temp_float, current_temp=last_temp if last_temp is not None else "N/A", timeout=timeout_float)
                        except ValueError: error_msg = "Chamber Check Temp 파라미터 숫자 변환 오류"
                    elif not self.settings.get("chamber_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Chamber")
                    elif not self.chamber: error_msg = "Chamber가 초기화되지 않았습니다."
                    else: error_msg = "목표 온도 파라미터 누락"

                else:
                     error_msg = f"알 수 없거나 아직 처리되지 않은 액션 타입: {action_type}"

            except ConnectionError as ce: 
                error_msg = f"장비 연결 오류: {str(ce)}"
                step_success = False
            except Exception as e:
                error_msg = f"실행 중 예외: {type(e).__name__} - {e}"
                step_success = False
                import traceback
                self.log_message_signal.emit(f"  Stack trace: {traceback.format_exc()}")

            if not step_success and not error_msg: 
                error_msg = "알 수 없는 오류로 단계 실행 실패"
            
            if error_msg: 
                self.log_message_signal.emit(f"Error at step {current_item_index + 1} ({action_type}): {error_msg}")
            
            if not step_success and halt_on_error:
                self.log_message_signal.emit(f"오류로 인해 시퀀스 중단됨 (단계: {current_item_index + 1}).")
                self.sequence_finished_signal.emit(False, f"오류로 중단 (단계 {current_item_index + 1}: {error_msg if error_msg else '알 수 없는 오류'})")
                return
            
            current_item_index += 1
            if not self.request_stop_flag:
                 time.sleep(0.01) 

        if not self.request_stop_flag : 
            self.sequence_finished_signal.emit(True, constants.MSG_SEQUENCE_PLAYBACK_COMPLETE)