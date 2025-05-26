# ui/dialogs/loop_definition_dialog.py
import sys
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QWidget # QWidget 추가 (그룹박스 대용)
)
from PyQt5.QtGui import QDoubleValidator

# --- 수정된 임포트 경로 ---
from core import constants # For SEQ_PARAM_KEY_LOOP_...

class LoopDefinitionDialog(QDialog):
    """
    테스트 시퀀스 내의 루프 파라미터 정의를 위한 커스텀 다이얼로그입니다.
    사용자는 이 다이얼로그를 통해 루프를 적용할 특정 액션의 특정 파라미터와
    해당 파라미터의 시작값, 스텝값, 종료값을 설정합니다.
    """
    def __init__(self,
                 target_actions_data: List[Tuple[int, str, Dict[str,str]]],
                 parent: Optional[QWidget] = None):
        """
        LoopDefinitionDialog를 초기화합니다.

        Args:
            target_actions_data (List[Tuple[int, str, Dict[str,str]]]):
                루프 대상이 될 수 있는 액션들의 정보 리스트.
                각 튜플은 (original_sequence_index, action_prefix, parsed_params_dict) 형태입니다.
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)
        self.setWindowTitle("루프 파라미터 정의") # 한글 제목
        self.setMinimumWidth(450)

        self.target_actions_data = target_actions_data

        # UI 멤버 변수 선언
        self.action_combo: Optional[QComboBox] = None
        self.param_combo: Optional[QComboBox] = None
        self.start_value_input: Optional[QLineEdit] = None
        self.step_value_input: Optional[QLineEdit] = None
        self.end_value_input: Optional[QLineEdit] = None
        self.button_box: Optional[QDialogButtonBox] = None

        self.action_param_map: Dict[int, List[str]] = {} # 콤보박스 인덱스 -> 해당 액션의 루프 가능한 파라미터 이름 리스트

        print(f"DEBUG_LoopDialog_Init: Received target_actions_data: {target_actions_data}")

        main_layout = QVBoxLayout(self)

        # --- 1. 루프 대상 액션 및 파라미터 선택 ---
        target_selection_group = QWidget()
        target_selection_layout = QGridLayout(target_selection_group)
        target_selection_layout.addWidget(QLabel("<b>루프 대상 액션 및 파라미터:</b>"), 0, 0, 1, 2)

        self.action_combo = QComboBox()
        self.param_combo = QComboBox()

        for original_idx, prefix, params in target_actions_data:
            loopable_numeric_params: List[str] = []
            print(f"DEBUG_LoopDialog_Init: Processing action original_idx={original_idx}, prefix='{prefix}', params={params}")

            # I2C Write 액션의 'VAL' 파라미터 (16진수 문자열이나 정수형으로 변환될 값)
            if prefix == constants.SEQ_PREFIX_I2C_WRITE_NAME or \
               prefix == constants.SEQ_PREFIX_I2C_WRITE_ADDR:
                # params 딕셔너리의 모든 키를 순회하며 "VAL" 상수와 일치하는지 명시적으로 확인
                # SequencePlayer._parse_sequence_item에서 key.strip()을 이미 수행했으므로,
                # 여기서 params의 키는 이미 공백이 제거된 상태임.
                for key_in_params_dict in params.keys():
                    if key_in_params_dict == constants.SEQ_PARAM_KEY_VALUE: # constants.SEQ_PARAM_KEY_VALUE는 "VAL"
                        loopable_numeric_params.append(constants.SEQ_PARAM_KEY_VALUE)
                        break # 해당 키를 찾았으므로 더 이상 이 액션의 파라미터 키를 찾을 필요 없음
            # SMU 또는 Chamber의 값 설정 액션의 'VAL' 파라미터 (실수형)
            elif prefix in [constants.SEQ_PREFIX_SM_SET_V, constants.SEQ_PREFIX_SM_SET_I,
                            constants.SEQ_PREFIX_CHAMBER_SET_TEMP]:
                for key_in_params_dict in params.keys():
                    if key_in_params_dict == constants.SEQ_PARAM_KEY_VALUE:
                        loopable_numeric_params.append(constants.SEQ_PARAM_KEY_VALUE)
                        break
            # Delay 액션의 'SEC' 파라미터 (실수형)
            elif prefix == constants.SEQ_PREFIX_DELAY:
                for key_in_params_dict in params.keys():
                    if key_in_params_dict == constants.SEQ_PARAM_KEY_SECONDS:
                        loopable_numeric_params.append(constants.SEQ_PARAM_KEY_SECONDS)
                        break
            # SMU 보호 전류 설정 액션의 'I_LIMIT' 파라미터 (실수형)
            elif prefix == constants.SEQ_PREFIX_SM_SET_PROTECTION_I:
                for key_in_params_dict in params.keys():
                    if key_in_params_dict == constants.SEQ_PARAM_KEY_CURRENT_LIMIT:
                         loopable_numeric_params.append(constants.SEQ_PARAM_KEY_CURRENT_LIMIT)
                         break
            # Chamber Check Temp의 'VAL'(목표온도), 'TOLERANCE_DEG', 'TIMEOUT_SEC' (실수형)
            elif prefix == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP:
                possible_target_keys = [
                    constants.SEQ_PARAM_KEY_VALUE,
                    constants.SEQ_PARAM_KEY_TOLERANCE,
                    constants.SEQ_PARAM_KEY_TIMEOUT
                ]
                # params.keys()를 직접 순회하는 대신 possible_target_keys를 순회하며 params에 있는지 확인
                for target_key in possible_target_keys:
                    if target_key in params: # params는 params_dict임
                        loopable_numeric_params.append(target_key)
                        # 발견해도 break하지 않고 모든 possible_target_keys를 확인하여 추가
            
            print(f"DEBUG_LoopDialog_Init: For original_idx={original_idx}, prefix='{prefix}', identified loopable_params: {loopable_numeric_params}")

            if loopable_numeric_params:
                action_display_name = f"단계 {original_idx + 1}: {prefix}"
                current_combo_idx = self.action_combo.count()
                self.action_combo.addItem(action_display_name, original_idx)
                self.action_param_map[current_combo_idx] = loopable_numeric_params

        if self.action_combo: # None 체크
            self.action_combo.currentIndexChanged.connect(self._update_param_combo)

        target_selection_layout.addWidget(QLabel("대상 액션:"), 1, 0)
        target_selection_layout.addWidget(self.action_combo, 1, 1)
        target_selection_layout.addWidget(QLabel("대상 파라미터:"), 2, 0)
        target_selection_layout.addWidget(self.param_combo, 2, 1)

        main_layout.addWidget(target_selection_group)

        if self.action_combo and self.action_combo.count() > 0:
            self._update_param_combo(0)
        else:
            main_layout.addWidget(QLabel("선택된 액션에 루프 적용 가능한 파라미터가 없습니다."))

        # --- 2. 루프 범위 설정 (시작, 스텝, 종료) ---
        loop_range_group = QWidget()
        loop_range_layout = QGridLayout(loop_range_group)

        loop_range_layout.addWidget(QLabel("시작 값:"), 0, 0)
        self.start_value_input = QLineEdit()
        self.start_value_input.setValidator(QDoubleValidator())
        self.start_value_input.setPlaceholderText("예: 0.1 또는 10 (숫자)")
        loop_range_layout.addWidget(self.start_value_input, 0, 1)

        loop_range_layout.addWidget(QLabel("스텝 값:"), 1, 0)
        self.step_value_input = QLineEdit()
        self.step_value_input.setValidator(QDoubleValidator())
        self.step_value_input.setPlaceholderText("예: 0.01 또는 1 (0이 아니어야 함)")
        loop_range_layout.addWidget(self.step_value_input, 1, 1)

        loop_range_layout.addWidget(QLabel("종료 값:"), 2, 0)
        self.end_value_input = QLineEdit()
        self.end_value_input.setValidator(QDoubleValidator())
        self.end_value_input.setPlaceholderText("예: 1.0 또는 100")
        loop_range_layout.addWidget(self.end_value_input, 2, 1)

        main_layout.addWidget(loop_range_group)

        # --- OK, Cancel 버튼 ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # 루프 가능한 파라미터가 없으면 OK 버튼 비활성화
        if not self.action_combo or self.action_combo.count() == 0 or \
           (self.param_combo and self.param_combo.count() == 0) :
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button:
                ok_button.setEnabled(False)

    def _update_param_combo(self, action_combo_idx: int):
        """선택된 액션에 따라 파라미터 콤보박스 내용을 업데이트합니다."""
        if not self.param_combo or not self.action_combo: return

        self.param_combo.clear()
        current_action_text = self.action_combo.itemText(action_combo_idx) # Get text for logging
        found_params_for_action = []

        if action_combo_idx >= 0 and action_combo_idx in self.action_param_map:
            found_params_for_action = self.action_param_map[action_combo_idx]
            self.param_combo.addItems(found_params_for_action)
        
        print(f"DEBUG_LoopDialog: Action selected: '{current_action_text}' (idx {action_combo_idx}). Found loopable params: {found_params_for_action}")

        # 파라미터 콤보가 비어있으면 OK 버튼 비활성화
        if self.button_box:
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button:
                ok_button.setEnabled(self.param_combo.count() > 0)

    def get_loop_parameters(self) -> Optional[Dict[str, Any]]:
        """
        사용자가 입력한 루프 파라미터를 검증하고 딕셔너리 형태로 반환합니다.
        유효하지 않으면 None을 반환합니다.
        """
        if not self.action_combo or self.action_combo.currentIndex() < 0 or \
           not self.param_combo or not self.param_combo.currentText() or \
           not self.start_value_input or not self.step_value_input or not self.end_value_input:
            QMessageBox.warning(self, "입력 오류", "루프 대상 액션, 파라미터 및 모든 범위 값을 선택/입력해야 합니다.")
            return None

        try:
            start_val_str = self.start_value_input.text().strip()
            step_val_str = self.step_value_input.text().strip()
            end_val_str = self.end_value_input.text().strip()

            if not all([start_val_str, step_val_str, end_val_str]):
                QMessageBox.warning(self, "입력 오류", "시작, 스텝, 종료 값은 모두 입력되어야 합니다.")
                return None

            start_val = float(start_val_str)
            step_val = float(step_val_str)
            end_val = float(end_val_str)
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "시작, 스텝, 종료 값은 유효한 숫자여야 합니다.")
            return None

        if step_val == 0:
            QMessageBox.warning(self, "입력 오류", "스텝 값은 0이 될 수 없습니다.")
            return None

        # 루프 범위 유효성 검사: 스텝이 양수일 때 시작값이 종료값보다 크거나, 스텝이 음수일 때 시작값이 종료값보다 작으면 안됨
        if (step_val > 0 and start_val > end_val) or \
           (step_val < 0 and start_val < end_val):
            QMessageBox.warning(self, "입력 오류", "유효하지 않은 루프 범위입니다.\n양수 스텝: 시작 <= 종료\n음수 스텝: 시작 >= 종료")
            return None

        selected_action_original_index = self.action_combo.currentData() # UserData에서 원본 인덱스 가져옴

        return {
            constants.SEQ_PARAM_KEY_LOOP_ACTION_INDEX: selected_action_original_index,
            constants.SEQ_PARAM_KEY_LOOP_TARGET_PARAM_KEY: self.param_combo.currentText(),
            constants.SEQ_PARAM_KEY_LOOP_START_VALUE: start_val,
            constants.SEQ_PARAM_KEY_LOOP_STEP_VALUE: step_val,
            constants.SEQ_PARAM_KEY_LOOP_END_VALUE: end_val,
        }

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication

    # 테스트를 위한 MockConstants (실제 실행 시에는 core.constants가 임포트되어야 함)
    try:
        from core import constants as test_constants_module
    except ImportError:
        class MockCoreConstants:
            SEQ_PREFIX_I2C_WRITE_NAME = "I2C_W_NAME"
            SEQ_PREFIX_I2C_WRITE_ADDR = "I2C_W_ADDR" # 추가
            SEQ_PREFIX_SM_SET_V = "SM_SET_V"
            SEQ_PREFIX_SM_SET_I = "SM_SET_I" # 추가
            SEQ_PREFIX_CHAMBER_SET_TEMP = "CH_SET_TEMP" # 추가
            SEQ_PREFIX_DELAY = "DELAY_S"
            SEQ_PREFIX_SM_SET_PROTECTION_I = "SM_SET_PROT_I"
            SEQ_PREFIX_CHAMBER_CHECK_TEMP = "CH_CHECK_TEMP"

            SEQ_PARAM_KEY_VALUE = "VAL"
            SEQ_PARAM_KEY_SECONDS = "SEC"
            SEQ_PARAM_KEY_TARGET_NAME = "NAME" # I2C_WRITE_NAME용
            SEQ_PARAM_KEY_CURRENT_LIMIT = "I_LIMIT" # SM_SET_PROT_I용
            SEQ_PARAM_KEY_TOLERANCE = "TOLERANCE_DEG" # CHAMBER_CHECK_TEMP용
            SEQ_PARAM_KEY_TIMEOUT = "TIMEOUT_SEC" # CHAMBER_CHECK_TEMP용


            SEQ_PARAM_KEY_LOOP_ACTION_INDEX = "LP_ACT_IDX"
            SEQ_PARAM_KEY_LOOP_TARGET_PARAM_KEY = "LP_TGT_KEY"
            SEQ_PARAM_KEY_LOOP_START_VALUE = "LP_STARTV"
            SEQ_PARAM_KEY_LOOP_STEP_VALUE = "LP_STEPV"
            SEQ_PARAM_KEY_LOOP_END_VALUE = "LP_ENDV"
        test_constants_module = MockCoreConstants()
        # 전역 constants를 mock으로 설정 (테스트 환경에서만)
        constants = test_constants_module # type: ignore


    app = QApplication(sys.argv)

    mock_target_actions_data = [
        (0, test_constants_module.SEQ_PREFIX_SM_SET_V, {test_constants_module.SEQ_PARAM_KEY_VALUE: "0.5", "TERM": "FRONT"}),
        (1, test_constants_module.SEQ_PREFIX_DELAY, {test_constants_module.SEQ_PARAM_KEY_SECONDS: "0.1"}),
        (2, test_constants_module.SEQ_PREFIX_I2C_WRITE_NAME, {test_constants_module.SEQ_PARAM_KEY_TARGET_NAME: "REG_X", test_constants_module.SEQ_PARAM_KEY_VALUE: "0x10"}),
        (3, test_constants_module.SEQ_PREFIX_SM_SET_PROTECTION_I, {test_constants_module.SEQ_PARAM_KEY_CURRENT_LIMIT: "0.05"}),
        (4, test_constants_module.SEQ_PREFIX_CHAMBER_CHECK_TEMP, {
            test_constants_module.SEQ_PARAM_KEY_VALUE: "25.0",
            test_constants_module.SEQ_PARAM_KEY_TOLERANCE: "0.5",
            test_constants_module.SEQ_PARAM_KEY_TIMEOUT: "60"
            })
    ]

    dialog = LoopDefinitionDialog(mock_target_actions_data)
    if dialog.exec_() == QDialog.Accepted:
        params = dialog.get_loop_parameters()
        print("Loop parameters accepted:", params)
    else:
        print("Loop definition cancelled.")
    # sys.exit(app.exec_()) # 다이얼로그만 테스트 시에는 불필요