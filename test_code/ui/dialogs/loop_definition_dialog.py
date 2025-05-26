# ui/dialogs/loop_definition_dialog.py
import sys
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QWidget, QFormLayout # QWidget 추가 (그룹박스 대용), QFormLayout 추가
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
        Loop Definition Dialog Constructor

        Args:
            target_actions_data: List of (original_index, action_prefix, params_dict) tuples to process.
                                 These are actions from the main sequence list that are eligible for looping.
                                 original_index is the index of the action in the SequenceControllerTab's QListWidget.
            parent: Parent widget for this dialog.
        """
        super().__init__(parent)
        
        self.setWindowTitle("Define Loop")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        # Main layout for the dialog
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout() # Form layout for structured input fields
        
        # --- UI Element Creation --- 
        # These QComboBoxes and QLineEdits will capture user input for loop definition.
        self.action_combo = QComboBox() # To select which action in the sequence to apply the loop to.
        print(f"DEBUG_LoopDialog_Init: self.action_combo after creation: {self.action_combo}") 
        self.param_combo = QComboBox()  # To select which parameter of the chosen action will be looped.
        print(f"DEBUG_LoopDialog_Init: self.param_combo after creation: {self.param_combo}") 
        
        self.start_value_input = QLineEdit() # Input for the loop's start value.
        self.step_value_input = QLineEdit()  # Input for the loop's step value.
        self.end_value_input = QLineEdit()    # Input for the loop's end value.
        
        # Adding rows to the form layout for a clean UI structure.
        form_layout.addRow("대상 액션:", self.action_combo)
        form_layout.addRow("대상 파라미터:", self.param_combo)
        form_layout.addRow("시작 값:", self.start_value_input)
        form_layout.addRow("스텝 값:", self.step_value_input)
        form_layout.addRow("종료 값:", self.end_value_input)
        
        main_layout.addLayout(form_layout)
        
        # Standard OK and Cancel buttons for the dialog.
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept) # Connects OK to dialog's accept slot.
        self.button_box.rejected.connect(self.reject) # Connects Cancel to dialog's reject slot.
        main_layout.addWidget(self.button_box)
        
        # --- Action and Parameter Processing --- 
        # This dictionary will map the index of an action in self.action_combo 
        # to a list of its parameter keys that are eligible for looping (e.g., numeric parameters).
        self.action_param_map: Dict[int, List[str]] = {} 
        
        # Defines which parameter keys are considered numeric and thus loopable for each action type.
        # This is crucial for filtering parameters that can be iterated over.
        numeric_param_key_candidates = {
            constants.SEQ_PREFIX_I2C_WRITE_NAME: [constants.SEQ_PARAM_KEY_VALUE],
            constants.SEQ_PREFIX_I2C_WRITE_ADDR: [constants.SEQ_PARAM_KEY_VALUE],
            constants.SEQ_PREFIX_DELAY: [constants.SEQ_PARAM_KEY_SECONDS],
            constants.SEQ_PREFIX_SM_SET_V: [constants.SEQ_PARAM_KEY_VALUE],
            constants.SEQ_PREFIX_SM_SET_I: [constants.SEQ_PARAM_KEY_VALUE],
            constants.SEQ_PREFIX_SM_SET_PROTECTION_I: [constants.SEQ_PARAM_KEY_CURRENT_LIMIT],
            constants.SEQ_PREFIX_CHAMBER_SET_TEMP: [constants.SEQ_PARAM_KEY_VALUE],
            constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP: [
                constants.SEQ_PARAM_KEY_VALUE, # Target temperature
                constants.SEQ_PARAM_KEY_TOLERANCE, # Temperature tolerance
                constants.SEQ_PARAM_KEY_TIMEOUT    # Timeout for stabilization
            ]
        }
        
        print(f"DEBUG_LoopDialog_Init: Received target_actions_data: {target_actions_data}")
        
        # Iterate through the provided sequence actions to find loopable numeric parameters.
        for original_idx, prefix, params in target_actions_data:
            print(f"DEBUG_LoopDialog_Init: Processing action original_idx={original_idx}, prefix='{prefix}', params={params}")
            
            loopable_numeric_params = [] # Store parameter keys of the current action that can be looped.
            
            # Get the list of parameter keys that are candidates for looping for the current action's prefix.
            possible_target_keys = numeric_param_key_candidates.get(prefix, [])
            
            if possible_target_keys:
                for target_key_candidate in possible_target_keys:
                    # Check if the candidate key (or its case-insensitive version) exists in the action's parameters.
                    # This allows for some flexibility in how parameter keys are defined in constants vs. used in sequence items.
                    if target_key_candidate in params:
                        if target_key_candidate not in loopable_numeric_params:
                             loopable_numeric_params.append(target_key_candidate)
                    else:
                        # Fallback: case-insensitive check if the exact key wasn't found.
                        for actual_param_key in params.keys():
                            if actual_param_key.upper() == target_key_candidate.upper() and actual_param_key not in loopable_numeric_params:
                                loopable_numeric_params.append(actual_param_key)
            
            print(f"DEBUG_LoopDialog_Init: For original_idx={original_idx}, prefix='{prefix}', identified loopable_params: {loopable_numeric_params}")

            # If loopable parameters were found for this action, add it to the action_combo.
            # The original_idx (from the main sequence list) is stored as item data for later reference.
            if loopable_numeric_params:
                action_display_name = f"단계 {original_idx + 1}: {prefix}" # User-friendly display name for the action.
                current_combo_idx = self.action_combo.count() # Get current count before adding, this will be the index for action_param_map.
                self.action_combo.addItem(action_display_name, original_idx) # Add to QComboBox, storing original_idx.
                self.action_param_map[current_combo_idx] = loopable_numeric_params # Map this combo index to its loopable params.

        # Connect the signal for action selection changes *after* populating action_combo.
        # This prevents _update_param_combo from being called unnecessarily during initial population.
        self.action_combo.currentIndexChanged.connect(self._update_param_combo)

        # After populating, if there are any actions, select the first one and update the parameter combo box.
        if self.action_combo.count() > 0:
            print("DEBUG_LoopDialog_Init: Action combo has items. Setting current index to 0.")
            self.action_combo.setCurrentIndex(0) # Triggers currentIndexChanged, which calls _update_param_combo.
            # Explicit call for clarity and to ensure it runs if the signal mechanism has issues or for initial state.
            print("DEBUG_LoopDialog_Init: Explicitly calling _update_param_combo for index 0.")
            self._update_param_combo(0) 
        else:
            # If no actions have loopable parameters, inform the user and disable the OK button.
            main_layout.addWidget(QLabel("선택된 액션에 루프 적용 가능한 파라미터가 없습니다."))
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button:
                ok_button.setEnabled(False)

    def _update_param_combo(self, action_combo_idx: int):
        """
        Updates the 'param_combo' (target parameter QComboBox) based on the currently selected action 
        in 'action_combo'. This method is typically called when the selected index of 'action_combo' changes.

        Args:
            action_combo_idx: The index of the currently selected item in self.action_combo.
        """
        print(f"DEBUG_LoopDialog_Update: _update_param_combo called with action_combo_idx = {action_combo_idx}")
        print(f"DEBUG_LoopDialog_Update: self.action_combo is {self.action_combo} (type: {type(self.action_combo)})")
        print(f"DEBUG_LoopDialog_Update: self.param_combo is {self.param_combo} (type: {type(self.param_combo)})")

        # --- Bug Fix Note (YYYY-MM-DD by YourName/AI) ---
        # Original bug: The condition `if not self.param_combo or not self.action_combo ...` would incorrectly evaluate to True
        # even when self.param_combo (and self.action_combo) were valid QComboBox objects (not None).
        # This was because the "truthiness" of a QComboBox object (e.g., if it has no items yet)
        # might be interpreted as False in a boolean context for `not self.param_combo`.
        # The fix is to explicitly check for `is None` to ensure the objects themselves are valid and not None,
        # rather than relying on their implicit boolean value, which fixed the early bail-out.
        # The following `param_combo_is_none` and `action_combo_is_none` variables were part of debugging this issue
        # and confirmed that the objects were indeed not None, leading to the `is None` check as the solution.
        param_combo_is_none = self.param_combo is None
        action_combo_is_none = self.action_combo is None
        idx_is_invalid = action_combo_idx < 0

        print(f"DEBUG_LoopDialog_Update: Condition check: self.param_combo is None -> {param_combo_is_none}")
        print(f"DEBUG_LoopDialog_Update: Condition check: self.action_combo is None -> {action_combo_is_none}")
        print(f"DEBUG_LoopDialog_Update: Condition check: action_combo_idx < 0 -> {idx_is_invalid}")

        # Corrected condition: Explicitly check if the QComboBox objects are None.
        if self.param_combo is None or self.action_combo is None or action_combo_idx < 0:
            print("DEBUG_LoopDialog_Update: One of the conditions (explicit None check or invalid index) is True - Bailing out.")
            return

        self.param_combo.blockSignals(True)  # Prevent signals during modification.
        self.param_combo.clear() # Clear previous parameter items.

        current_action_text = self.action_combo.itemText(action_combo_idx) # For logging.
        print(f"DEBUG_LoopDialog_Update: Updating param_combo for action_combo_idx={action_combo_idx}, action_text='{current_action_text}'")
        print(f"DEBUG_LoopDialog_Update: action_param_map keys: {list(self.action_param_map.keys())}")
        print(f"DEBUG_LoopDialog_Update: action_param_map content: {self.action_param_map}") 

        # Retrieve the list of loopable parameter keys for the selected action using its index.
        found_params_for_action = []
        if action_combo_idx in self.action_param_map:
            found_params_for_action = self.action_param_map[action_combo_idx]
            print(f"DEBUG_LoopDialog_Update: Found params for selected action (idx {action_combo_idx}): {found_params_for_action}")
            
            if found_params_for_action: # If there are loopable parameters for this action.
                for param_key in found_params_for_action:
                    self.param_combo.addItem(param_key) # Add each parameter key to the param_combo.
                    print(f"DEBUG_LoopDialog_Update: Added param '{param_key}' to param_combo.")
            else:
                print(f"DEBUG_LoopDialog_Update: found_params_for_action is empty for idx {action_combo_idx}.")
        else:
            # This case should ideally not happen if action_combo is populated correctly from actions that *have* loopable_params.
            print(f"DEBUG_LoopDialog_Update: No parameters found in action_param_map for action index {action_combo_idx}.")

        self.param_combo.blockSignals(False) # Re-enable signals.
        
        # Enable or disable the dialog's OK button based on whether any loopable parameters were found and added.
        if self.button_box:
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button:
                has_params_to_loop = self.param_combo.count() > 0
                ok_button.setEnabled(has_params_to_loop)
                print(f"DEBUG_LoopDialog_Update: OK button enabled: {has_params_to_loop}")
                
                if not has_params_to_loop:
                    # Inform user if the selected action, despite being in action_combo, ended up having no params for param_combo.
                    QMessageBox.warning(self, "파라미터 없음", 
                                       f"선택한 액션 '{current_action_text}'에 루프 가능한 파라미터가 없습니다.\n"
                                       "다른 액션을 선택하거나 대화상자를 닫고 다른 액션을 선택하세요.")

    def get_loop_parameters(self) -> Optional[Dict[str, Any]]:
        """
        사용자가 입력한 루프 파라미터를 검증하고 딕셔너리 형태로 반환합니다.
        유효하지 않으면 None을 반환합니다.
        """
        if not self.action_combo or self.action_combo.currentIndex() < 0 or \
           not self.param_combo or not self.param_combo.currentText() or \
           not self.start_value_input or not self.step_value_input or not self.end_value_input:
            print("DEBUG_LoopDialog_Get: Missing UI components or selection")
            QMessageBox.warning(self, "입력 오류", "루프 대상 액션, 파라미터 및 모든 범위 값을 선택/입력해야 합니다.")
            return None

        # 선택된 액션 정보 출력
        action_idx = self.action_combo.currentIndex()
        action_text = self.action_combo.currentText()
        original_idx = self.action_combo.itemData(action_idx)
        selected_param = self.param_combo.currentText()
        
        print(f"DEBUG_LoopDialog_Get: Selected action idx={action_idx}, text='{action_text}', original_idx={original_idx}")
        print(f"DEBUG_LoopDialog_Get: Selected parameter: '{selected_param}'")

        try:
            start_val_str = self.start_value_input.text().strip()
            step_val_str = self.step_value_input.text().strip()
            end_val_str = self.end_value_input.text().strip()

            print(f"DEBUG_LoopDialog_Get: Input values - start='{start_val_str}', step='{step_val_str}', end='{end_val_str}'")

            if not all([start_val_str, step_val_str, end_val_str]):
                print("DEBUG_LoopDialog_Get: Missing input values")
                QMessageBox.warning(self, "입력 오류", "시작, 스텝, 종료 값은 모두 입력되어야 합니다.")
                return None

            start_val = float(start_val_str)
            step_val = float(step_val_str)
            end_val = float(end_val_str)
            
            print(f"DEBUG_LoopDialog_Get: Parsed values - start={start_val}, step={step_val}, end={end_val}")
        except ValueError as e:
            print(f"DEBUG_LoopDialog_Get: Value parsing error - {e}")
            QMessageBox.warning(self, "입력 오류", f"시작, 스텝, 종료 값은 유효한 숫자여야 합니다.\n오류: {e}")
            return None

        if step_val == 0:
            print("DEBUG_LoopDialog_Get: Step value is zero")
            QMessageBox.warning(self, "입력 오류", "스텝 값은 0이 될 수 없습니다.")
            return None

        # 루프 범위 유효성 검사: 스텝이 양수일 때 시작값이 종료값보다 크거나, 스텝이 음수일 때 시작값이 종료값보다 작으면 안됨
        if (step_val > 0 and start_val > end_val) or (step_val < 0 and start_val < end_val):
            invalid_direction = "시작값 > 종료값" if step_val > 0 else "시작값 < 종료값"
            expected_direction = "시작값 <= 종료값" if step_val > 0 else "시작값 >= 종료값"
            
            print(f"DEBUG_LoopDialog_Get: Invalid loop direction - {invalid_direction} with step={step_val}")
            QMessageBox.warning(self, "입력 오류", 
                              f"스텝 값({step_val})의 부호와 루프 방향이 일치하지 않습니다.\n"
                              f"현재: {invalid_direction}, 스텝 {step_val}\n"
                              f"조건: {expected_direction} (스텝 {step_val}일 때)")
            return None

        # 유효한 루프 파라미터 생성 및 반환
        result_params = {
            constants.SEQ_PARAM_KEY_LOOP_ACTION_INDEX: original_idx,
            constants.SEQ_PARAM_KEY_LOOP_TARGET_PARAM_KEY: selected_param,
            constants.SEQ_PARAM_KEY_LOOP_START_VALUE: start_val,
            constants.SEQ_PARAM_KEY_LOOP_STEP_VALUE: step_val,
            constants.SEQ_PARAM_KEY_LOOP_END_VALUE: end_val
        }
        
        print(f"DEBUG_LoopDialog_Get: Returning valid parameters: {result_params}")
        return result_params

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