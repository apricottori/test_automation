# core/sequence_player.py
import time
import sys 
from typing import List, Tuple, Dict, Any, Optional, ForwardRef, cast

from PyQt5.QtCore import QObject, pyqtSignal
# pyqtSlot은 현재 이 파일에서 직접 사용되지 않으므로, 필요하면 나중에 추가합니다.
# from PyQt5.QtCore import pyqtSlot 

from . import constants
from .helpers import normalize_hex_input
from .register_map_backend import RegisterMap
from .hardware_control import I2CDevice, Multimeter, Sourcemeter, Chamber # Chamber 임포트 확인
# SequenceItem, LoopActionItem, SimpleActionItem 모델 임포트
from .data_models import SequenceItem, LoopActionItem, SimpleActionItem

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
                 sequence_items: List[SequenceItem], # 타입 변경: List[str] -> List[SequenceItem]
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
        
        # 활성 루프 컨텍스트를 관리하기 위한 스택
        self.active_loop_contexts: List[Dict[str, Any]] = [] 
        
        self._current_smu_set_voltage: Optional[float] = None
        self._current_smu_set_current: Optional[float] = None
        self._current_chamber_set_temp: Optional[float] = None

    def _resolve_placeholders(self, value: Any, current_loop_vars: Dict[str, Any]) -> Any:
        """Recursively resolves placeholders in a string or list/dict of strings."""
        if isinstance(value, str):
            for var_name, var_val in current_loop_vars.items():
                placeholder = f"{{{var_name}}}"
                if placeholder in value:
                    # Try to maintain type if the placeholder is the entire string
                    if value == placeholder:
                        return var_val 
                    value = value.replace(placeholder, str(var_val))
            return value
        elif isinstance(value, list):
            return [self._resolve_placeholders(item, current_loop_vars) for item in value]
        elif isinstance(value, dict):
            return {k: self._resolve_placeholders(v, current_loop_vars) for k, v in value.items()}
        return value

    def _get_current_loop_variables_map(self) -> Dict[str, Any]:
        """Returns a flat map of all current loop variables from active_loop_contexts."""
        loop_vars_map = {}
        for context in self.active_loop_contexts:
            var_name = context.get("loop_variable_name")
            current_val = context.get("current_value")
            if var_name and current_val is not None:
                loop_vars_map[var_name] = current_val
        return loop_vars_map

    def _parse_sequence_item(self, item_text: str) -> Tuple[Optional[str], Dict[str, str]]:
        # 이 함수는 이제 SequenceItem 객체를 직접 사용하므로, 문자열 파싱은 불필요.
        # 다만, SequenceControllerTab 등 UI 단에서 문자열을 SequenceItem으로 변환하거나,
        # SequenceItem을 문자열로 표시할 때 유사한 로직이 필요할 수 있음.
        # 여기서는 SequencePlayer가 이미 SequenceItem 객체를 받는다고 가정하고 비워두거나 삭제.
        # SequenceControllerTab에서 이 함수를 호출하는 부분이 있다면, 해당 부분도 수정 필요.
        # 지금은 빈 값 반환 또는 예외 발생으로 처리.
        # raise NotImplementedError("_parse_sequence_item is deprecated as SequencePlayer now uses SequenceItem objects.")
        # 임시로 기존 로직 유지 (SequenceControllerTab에서 호출될 수 있으므로)
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
        base_conditions: Dict[str, Any] = {}
        if self.main_window_ref and hasattr(self.main_window_ref, 'get_current_measurement_conditions'):
            try:
                base_conditions = self.main_window_ref.get_current_measurement_conditions()
            except Exception as e:
                self.log_message_signal.emit(f"Warning: main_window_ref.get_current_measurement_conditions 호출 중 오류: {e}.")
        else: # Fallback if main_window_ref or method is not available
            if self.sourcemeter:
                if self.sourcemeter.get_cached_set_voltage() is not None:
                    base_conditions[constants.EXCEL_COL_COND_SMU_V] = self.sourcemeter.get_cached_set_voltage()
                if self.sourcemeter.get_cached_set_current() is not None:
                    base_conditions[constants.EXCEL_COL_COND_SMU_I] = self.sourcemeter.get_cached_set_current()
            if self.chamber:
                if self.chamber.get_cached_target_temperature() is not None:
                    base_conditions[constants.EXCEL_COL_COND_CHAMBER_T] = self.chamber.get_cached_target_temperature()
        
        # 활성 루프 컨텍스트의 모든 변수를 기본 조건에 추가
        # 루프 변수 이름은 "loop_" 접두사를 가질 수 있음 (구현에 따라 다름)
        for loop_ctx in self.active_loop_contexts:
            loop_var_name = loop_ctx.get("loop_variable_name") # 기본값 없이 가져옴
            current_loop_val = loop_ctx.get("current_value", None)
            if loop_var_name and current_loop_val is not None: # 변수 이름이 있고, 값도 있을 때만 추가
                 # SequencePlayer 내부에서 active_loop_vars 만들 때 이미 접두사 붙였다면 여기선 필요 없음
                 # 여기서는 loop_ctx에서 가져온 loop_variable_name을 그대로 사용한다고 가정
                base_conditions[str(loop_var_name)] = current_loop_val # str()로 명시적 형변환
        return base_conditions

    def run_sequence(self):
        total_items = len(self.sequence_items) # 전체 아이템 수 (루프 포함)
        self.log_message_signal.emit(f"시퀀스 실행 시작... (총 {total_items} 최상위 아이템, Sample: {self.sample_number})")

        self.request_stop_flag = False
        self.active_loop_contexts = [] # 루프 컨텍스트 초기화

        if self.chamber and hasattr(self.chamber, 'set_stop_flag_ref'):
            self.chamber.set_stop_flag_ref(self)

        # 재귀적으로 액션 실행을 위한 내부 헬퍼 함수 호출
        final_success, final_message = self._execute_actions_recursively(self.sequence_items, top_level_call=True)
        
        self.sequence_finished_signal.emit(final_success, final_message)

    def _execute_actions_recursively(self, actions_to_execute: List[SequenceItem], top_level_call: bool = False) -> Tuple[bool, str]:
        halt_on_error = self.settings.get("error_halts_sequence", False)
        overall_success = True
        completion_message = constants.MSG_SEQUENCE_PLAYBACK_COMPLETE

        for item_index, current_action_item in enumerate(actions_to_execute):
            if self.request_stop_flag:
                self.log_message_signal.emit("시퀀스 실행 중단 요청됨.")
                return False, constants.MSG_SEQUENCE_PLAYBACK_ABORTED

            action_type = current_action_item.get("action_type")
            item_id = current_action_item.get("item_id", f"item_{item_index}")
            display_name = current_action_item.get("display_name", action_type)
            self.log_message_signal.emit(f"\n--- 실행: '{display_name}' (ID: {item_id}, Type: {action_type}) ---")

            step_success = False
            error_msg = ""

            if action_type == "Loop":
                loop_item = cast(LoopActionItem, current_action_item)
                loop_var_name = loop_item.get("loop_variable_name")
                start_val = loop_item.get("start_value")
                stop_val = loop_item.get("stop_value")
                step_val = loop_item.get("step_value")
                loop_count = loop_item.get("loop_count")
                looped_actions = loop_item.get("looped_actions", [])

                current_loop_val = start_val
                iteration = 0

                # 루프 컨텍스트 설정
                loop_context = {
                    "item_id": item_id,
                    "loop_variable_name": loop_var_name if loop_var_name else f"loop_iter_{len(self.active_loop_contexts)}",
                    "current_value": None, # 초기에는 None, 루프 진입 시 설정
                    "sweep_type": loop_item.get("sweep_type") # Store sweep_type for logging/conditions
                }
                self.active_loop_contexts.append(loop_context)
                self.log_message_signal.emit(f"  Loop Start: {display_name} (Type: {loop_context.get('sweep_type')})")

                # Determine loop iteration logic based on sweep_type
                sweep_type = loop_item.get("sweep_type")
                current_iter_value: Any = None
                loop_iterations_source: List[Any] = []

                if sweep_type == "NumericRange":
                    if not all(v is not None for v in [start_val, stop_val, step_val]) or (step_val is not None and step_val == 0):
                        error_msg = "NumericRange loop: start, stop, or step value is invalid or step is zero."; break
                    # Generate all values for the range
                    current = start_val
                    if step_val is not None and start_val is not None and stop_val is not None: # Check for None before comparison
                        if step_val > 0:
                            while current <= stop_val:
                                loop_iterations_source.append(current)
                                current += step_val
                        else: # step_val < 0 (already checked step_val != 0)
                            while current >= stop_val:
                                loop_iterations_source.append(current)
                                current += step_val
                    else:
                        error_msg = "NumericRange loop: start, stop or step value is None after check."; break
                elif sweep_type == "ValueList":
                    value_list = loop_item.get("value_list", [])
                    if not value_list:
                        error_msg = "ValueList loop: list of values is empty."; break
                    loop_iterations_source = value_list
                elif sweep_type == "FixedCount":
                    if loop_count is None or loop_count <= 0:
                        error_msg = "FixedCount loop: loop_count is invalid."; break
                    loop_iterations_source = list(range(1, loop_count + 1)) # 1-based iteration count for display
                else:
                    error_msg = f"Unknown or unsupported sweep_type: {sweep_type}"; break

                for iter_idx, current_iter_value_from_source in enumerate(loop_iterations_source):
                    if self.request_stop_flag: break

                    loop_context["current_value"] = current_iter_value_from_source
                    if loop_var_name: # If a variable name is defined for this loop
                        self.log_message_signal.emit(f"    Loop Iteration {iter_idx+1}/{len(loop_iterations_source)}: {loop_var_name} = {current_iter_value_from_source}")
                    else: # For FixedCount without a variable name, or other generic cases
                        self.log_message_signal.emit(f"    Loop Iteration {iter_idx+1}/{len(loop_iterations_source)}")

                    # 내부 액션 실행
                    loop_internal_success, loop_internal_msg = self._execute_actions_recursively(looped_actions)
                    if not loop_internal_success:
                        error_msg = f"루프 내부 액션 실패: {loop_internal_msg}"; break
                
                self.active_loop_contexts.pop() # 현재 루프 컨텍스트 제거
                if error_msg:
                    self.log_message_signal.emit(f"  Loop Error: {error_msg}")
                    step_success = False
                elif self.request_stop_flag:
                     self.log_message_signal.emit(f"  Loop Interrupted by user.")
                     step_success = False # 중단 시 성공으로 간주 안함
                else:
                    self.log_message_signal.emit(f"  Loop End: {display_name}")
                    step_success = True
            
            else: # SimpleActionItem 처리
                simple_item = cast(SimpleActionItem, current_action_item)
                params = simple_item.get("parameters", {})
                
                # Resolve placeholders in parameters
                current_loop_vars_map = self._get_current_loop_variables_map()
                resolved_params = self._resolve_placeholders(params, current_loop_vars_map)
                
                modified_params: Dict[str, Any] # Declare type for modified_params
                # Initialize step_success to True for simple actions, errors will set it to False
                current_step_success_flag = True 

                if not isinstance(resolved_params, dict): # Should always be a dict after resolving
                    error_msg = "Internal error: Parameter resolution did not return a dictionary."
                    current_step_success_flag = False
                    modified_params = {} # Initialize to empty dict to avoid further errors
                else:
                    # Use resolved_params for all subsequent logic
                    modified_params = resolved_params

                # Proceed only if no error from placeholder resolution
                if current_step_success_flag:
                    try:
                        current_conditions_with_loops = self._get_current_conditions() # 모든 활성 루프 변수 포함
                        
                        # ... (기존 SimpleActionItem 타입에 따른 실행 로직) ...
                        # 예: I2C_WRITE_NAME
                        if action_type == constants.SEQ_PREFIX_I2C_WRITE_NAME:
                            name = modified_params.get(constants.SEQ_PARAM_KEY_TARGET_NAME)
                            val_str_from_params = modified_params.get(constants.SEQ_PARAM_KEY_VALUE)
                            
                            val_str = str(val_str_from_params) 

                            if self.i2c_device and self.register_map and name and val_str:
                                field_info = self.register_map.logical_fields_map.get(name)
                                if not field_info: error_msg = constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)
                                else:
                                    try:
                                        # 루프 변수가 val_str을 대체해야 하는 경우, 여기서 처리.
                                        # 예를 들어, 루프 변수명이 params[VALUE_FIELD_NAME_IN_LOOP_DEF] 와 같다면,
                                        # val_str = str(current_loop_context[params[VALUE_FIELD_NAME_IN_LOOP_DEF]])
                                        # 현재는 루프 변수가 val_str을 직접 대체하지 않음. SequencePlayer의 _get_current_conditions에만 포함.
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
                        
                        # ... (다른 SimpleActionItem 타입들 처리 - measurement_result_signal 호출 시 current_conditions_with_loops 사용) ...
                        elif action_type == constants.SEQ_PREFIX_I2C_READ_NAME:
                            name = modified_params.get(constants.SEQ_PARAM_KEY_TARGET_NAME); var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                            if self.register_map and name and var_name:
                                read_val_hex = self.register_map.get_logical_field_value_hex(name, from_initial=False)
                                if constants.HEX_ERROR_NO_FIELD in read_val_hex or constants.HEX_ERROR_CONVERSION in read_val_hex : error_msg = f"Register '{name}' 읽기 오류: {read_val_hex}"
                                else: self.measurement_result_signal.emit(var_name, read_val_hex, self.sample_number, current_conditions_with_loops); self.log_message_signal.emit(f"  Register '{name}' 읽기 값: {read_val_hex} (저장 변수: {var_name})"); step_success = True
                            elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                            else: error_msg = "Name/Variable 파라미터 누락"
                        
                        elif action_type == constants.SEQ_PREFIX_I2C_WRITE_ADDR:
                            addr = modified_params.get(constants.SEQ_PARAM_KEY_ADDRESS)
                            val_str = modified_params.get(constants.SEQ_PARAM_KEY_VALUE)
                            if self.i2c_device and addr and val_str:
                                norm_addr = normalize_hex_input(addr, 4) # Ensure 4 hex chars for address
                                norm_val = normalize_hex_input(val_str, 2) # Ensure 2 hex chars for value
                                if norm_addr is None: error_msg = f"잘못된 주소 형식: {addr}"
                                elif norm_val is None: error_msg = f"잘못된 값 형식: {val_str}"
                                else:
                                    if self.i2c_device.write(norm_addr, norm_val):
                                        if self.register_map: # register_map이 있는 경우에만 값 업데이트 시도
                                            try:
                                                val_int_for_map = int(norm_val, 16)
                                                self.register_map.confirm_address_values_update({norm_addr: val_int_for_map})
                                            except ValueError:
                                                self.log_message_signal.emit(f"  Warning: I2C_WRITE_ADDR - '{norm_val}'을 register_map 업데이트를 위해 int로 변환 실패.")
                                        self.log_message_signal.emit(f"  I2C Write Addr: {norm_addr}, 값: {norm_val} 쓰기 완료."); step_success = True
                                    else: error_msg = f"I2C Write 실패 (Addr: {norm_addr}, Val: {norm_val})"
                            elif not self.i2c_device: error_msg = "I2C 장치가 초기화되지 않았습니다."
                            else: error_msg = "Address/Value 파라미터 누락"
                        
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
                                        self.measurement_result_signal.emit(var_name, read_val_hex, self.sample_number, current_conditions_with_loops)
                                        self.log_message_signal.emit(f"  I2C Read Addr: {norm_addr}, 값: {read_val_hex} (저장 변수: {var_name})"); step_success = True
                                    else: error_msg = f"I2C Read 실패 (Addr: {norm_addr})"
                            elif not self.i2c_device: error_msg = "I2C 장치가 초기화되지 않았습니다."
                            elif not self.register_map: error_msg = constants.MSG_NO_REGMAP_LOADED
                            else: error_msg = "Address/Variable 파라미터 누락"
                        
                        elif action_type == constants.SEQ_PREFIX_MM_MEAS_V:
                            var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                            if self.multimeter and self.settings.get("multimeter_use") and var_name:
                                s, v = self.multimeter.measure_voltage()
                                if s and v is not None: self.measurement_result_signal.emit(var_name, v, self.sample_number, current_conditions_with_loops); self.log_message_signal.emit(f"  Multimeter V: {v:.6f} (Var: {var_name})"); step_success = True
                                else: error_msg = "Multimeter 전압 측정 실패"
                            elif not self.settings.get("multimeter_use"): error_msg = constants.MSG_DEVICE_NOT_ENABLED.format(device_name="Multimeter")
                            elif not self.multimeter: error_msg = "Multimeter가 초기화되지 않았습니다."
                            else: error_msg = "변수명 누락"
                        elif action_type == constants.SEQ_PREFIX_MM_MEAS_I:
                            var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE)
                            if self.multimeter and self.settings.get("multimeter_use") and var_name:
                                s, curr = self.multimeter.measure_current()
                                if s and curr is not None: self.measurement_result_signal.emit(var_name, curr, self.sample_number, current_conditions_with_loops); self.log_message_signal.emit(f"  Multimeter I: {curr:.6e} (Var: {var_name})"); step_success = True
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

                        elif action_type == constants.SEQ_PREFIX_SM_MEAS_I:
                            var_name = modified_params.get(constants.SEQ_PARAM_KEY_VARIABLE); term = modified_params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT)
                            if self.sourcemeter and self.settings.get("sourcemeter_use") and var_name:
                                s, curr = self.sourcemeter.measure_current(term)
                                if s and curr is not None: self.measurement_result_signal.emit(var_name, curr, self.sample_number, current_conditions_with_loops); self.log_message_signal.emit(f"  SM I ({term}): {curr:.4e} (Var: {var_name})"); step_success = True
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
                                    is_stable, last_temp = self.chamber.is_temperature_stable(target_temp_float, tolerance_float, timeout_float)
                                    
                                    if self.request_stop_flag: error_msg = "온도 안정화 대기 중 중단됨."
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
                        current_step_success_flag = False # Update local flag
                    except Exception as e:
                        error_msg = f"실행 중 예외: {type(e).__name__} - {e}"
                        current_step_success_flag = False # Update local flag
                        import traceback
                        self.log_message_signal.emit(f"  Stack trace: {traceback.format_exc()}")
                
                step_success = current_step_success_flag # Assign to the loop-level step_success

            if not step_success and not error_msg: 
                error_msg = "알 수 없는 오류로 단계 실행 실패"
            
            if error_msg: 
                self.log_message_signal.emit(f"Error during '{display_name}' (ID: {item_id}): {error_msg}")
            
            if not step_success:
                overall_success = False
                completion_message = f"오류로 중단 (항목: '{display_name}', 오류: {error_msg})"
                if halt_on_error:
                    self.log_message_signal.emit(f"오류로 인해 시퀀스 중단됨 (항목: '{display_name}').")
                    return False, completion_message
            
            if not self.request_stop_flag and top_level_call: # 최상위 호출에서만 짧은 딜레이
                 time.sleep(0.01)
        
        return overall_success, completion_message

    def request_stop_sequence(self):
        self.request_stop_flag = True
        self.log_message_signal.emit("시퀀스 중단 요청됨 (플래그 설정). 다음 단계 시작 전 또는 루프 반복 시 중단됩니다.")