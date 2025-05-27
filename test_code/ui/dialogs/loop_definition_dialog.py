# ui/dialogs/loop_definition_dialog.py
import sys
from typing import List, Tuple, Dict, Any, Optional, cast, Literal
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QWidget, QSpinBox, QDoubleSpinBox, QGroupBox,
    QRadioButton, QHBoxLayout # QHBoxLayout 추가
)
from PyQt5.QtGui import QDoubleValidator

from core import constants
from core.data_models import LoopActionItem, SimpleActionItem # 데이터 모델 임포트

class LoopDefinitionDialog(QDialog):
    """Loop 블록의 파라미터 (변수 스윕 또는 횟수 반복)를 정의하는 다이얼로그"""

    def __init__(self, existing_loop_data: Optional[LoopActionItem] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.existing_data = existing_loop_data

        self.setWindowTitle("Define Loop Block Parameters")
        self.setMinimumWidth(450)

        # UI 멤버 변수 선언
        self.loop_display_name_input: Optional[QLineEdit] = None
        
        # Loop Type Selection
        self.loop_type_group: Optional[QGroupBox] = None
        self.value_sweep_radio: Optional[QRadioButton] = None
        self.value_list_radio: Optional[QRadioButton] = None # New: ValueList
        self.fixed_count_radio: Optional[QRadioButton] = None
        
        # Value Sweep (NumericRange) Parameters
        self.sweep_params_group: Optional[QGroupBox] = None
        self.sweep_loop_variable_name_input: Optional[QLineEdit] = None
        self.start_value_input: Optional[QLineEdit] = None
        self.stop_value_input: Optional[QLineEdit] = None
        self.step_value_input: Optional[QLineEdit] = None

        # Value List Parameters
        self.list_params_group: Optional[QGroupBox] = None # New Group
        self.list_loop_variable_name_input: Optional[QLineEdit] = None # New
        self.value_list_input: Optional[QLineEdit] = None # New

        # Fixed Count Parameters
        self.count_params_group: Optional[QGroupBox] = None 
        self.count_loop_variable_name_input: Optional[QLineEdit] = None # New: Optional variable name for count loop
        self.loop_count_spinbox: Optional[QSpinBox] = None

        self.button_box: Optional[QDialogButtonBox] = None
        self._double_validator = QDoubleValidator() # 유효성 검사기

        self._init_ui()
        self._connect_signals()
        if self.existing_data:
            self._load_existing_data()
        else:
            if self.value_sweep_radio: self.value_sweep_radio.setChecked(True) # 기본 선택 NumericRange
        self._update_ui_for_loop_type()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout() # Use QFormLayout for overall structure where appropriate

        self.loop_display_name_input = QLineEdit()
        self.loop_display_name_input.setPlaceholderText("e.g., Temperature Sweep 25-85C")
        form_layout.addRow("Loop Display Name (Optional):", self.loop_display_name_input)

        # --- Loop Type Selection --- 
        self.loop_type_group = QGroupBox("Loop Type")
        loop_type_vbox = QVBoxLayout(self.loop_type_group) # Use QVBoxLayout inside group
        self.value_sweep_radio = QRadioButton("Numeric Range Sweep")
        self.value_list_radio = QRadioButton("List of Values Sweep")
        self.fixed_count_radio = QRadioButton("Fixed Number of Iterations")
        loop_type_vbox.addWidget(self.value_sweep_radio)
        loop_type_vbox.addWidget(self.value_list_radio)
        loop_type_vbox.addWidget(self.fixed_count_radio)
        form_layout.addRow(self.loop_type_group)

        # --- Numeric Range Sweep Parameters --- 
        self.sweep_params_group = QGroupBox("Numeric Range Sweep Parameters")
        sweep_form_layout = QFormLayout(self.sweep_params_group)
        self.sweep_loop_variable_name_input = QLineEdit()
        self.sweep_loop_variable_name_input.setPlaceholderText("e.g., Temperature, VDD_Voltage (no spaces)")
        self.start_value_input = QLineEdit(); self.start_value_input.setValidator(self._double_validator)
        self.stop_value_input = QLineEdit(); self.stop_value_input.setValidator(self._double_validator)
        self.step_value_input = QLineEdit(); self.step_value_input.setValidator(self._double_validator)
        sweep_form_layout.addRow("Loop Variable Name:", self.sweep_loop_variable_name_input)
        sweep_form_layout.addRow("Start Value:", self.start_value_input)
        sweep_form_layout.addRow("Stop Value:", self.stop_value_input)
        sweep_form_layout.addRow("Step Value:", self.step_value_input)
        main_layout.addWidget(self.sweep_params_group) # Add group directly to main_layout

        # --- Value List Sweep Parameters ---
        self.list_params_group = QGroupBox("List of Values Sweep Parameters")
        list_form_layout = QFormLayout(self.list_params_group)
        self.list_loop_variable_name_input = QLineEdit()
        self.list_loop_variable_name_input.setPlaceholderText("e.g., DAC_Setting, Mode")
        self.value_list_input = QLineEdit()
        self.value_list_input.setPlaceholderText("Comma-separated values (e.g., 1.0, 1.5, 2.0 or High,Mid,Low)")
        list_form_layout.addRow("Loop Variable Name:", self.list_loop_variable_name_input)
        list_form_layout.addRow("Values (comma-separated):", self.value_list_input)
        main_layout.addWidget(self.list_params_group)

        # --- Fixed Count Parameters --- 
        self.count_params_group = QGroupBox("Fixed Count Parameters")
        count_form_layout = QFormLayout(self.count_params_group)
        self.count_loop_variable_name_input = QLineEdit()
        self.count_loop_variable_name_input.setPlaceholderText("Optional: e.g., IterationCounter (no spaces)")
        self.loop_count_spinbox = QSpinBox()
        self.loop_count_spinbox.setMinimum(1)
        self.loop_count_spinbox.setMaximum(1000000) 
        self.loop_count_spinbox.setValue(10)
        count_form_layout.addRow("Loop Variable Name (Optional):", self.count_loop_variable_name_input)
        count_form_layout.addRow("Number of Iterations:", self.loop_count_spinbox)
        main_layout.addWidget(self.count_params_group)
        
        main_layout.addLayout(form_layout) # Add the main form layout (with display name and loop type group)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(self.button_box)

    def _connect_signals(self):
        if self.value_sweep_radio: self.value_sweep_radio.toggled.connect(self._update_ui_for_loop_type)
        if self.value_list_radio: self.value_list_radio.toggled.connect(self._update_ui_for_loop_type)
        if self.fixed_count_radio: self.fixed_count_radio.toggled.connect(self._update_ui_for_loop_type)
        if self.button_box: 
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)

    def _update_ui_for_loop_type(self):
        is_sweep_range = self.value_sweep_radio.isChecked() if self.value_sweep_radio else False
        is_sweep_list = self.value_list_radio.isChecked() if self.value_list_radio else False
        is_count = self.fixed_count_radio.isChecked() if self.fixed_count_radio else False

        if self.sweep_params_group: self.sweep_params_group.setVisible(is_sweep_range)
        if self.list_params_group: self.list_params_group.setVisible(is_sweep_list)
        if self.count_params_group: self.count_params_group.setVisible(is_count)
        
        # Ensure only one radio button is checked
        if is_sweep_range:
            if self.value_list_radio and self.value_list_radio.isChecked(): self.value_list_radio.setChecked(False)
            if self.fixed_count_radio and self.fixed_count_radio.isChecked(): self.fixed_count_radio.setChecked(False)
        elif is_sweep_list:
            if self.value_sweep_radio and self.value_sweep_radio.isChecked(): self.value_sweep_radio.setChecked(False)
            if self.fixed_count_radio and self.fixed_count_radio.isChecked(): self.fixed_count_radio.setChecked(False)
        elif is_count:
            if self.value_sweep_radio and self.value_sweep_radio.isChecked(): self.value_sweep_radio.setChecked(False)
            if self.value_list_radio and self.value_list_radio.isChecked(): self.value_list_radio.setChecked(False)
        self.adjustSize() # Adjust dialog size to content

    def _load_existing_data(self):
        if not self.existing_data: return
        data = self.existing_data

        if self.loop_display_name_input: self.loop_display_name_input.setText(data.get("display_name", ""))

        sweep_type = data.get("sweep_type")

        if sweep_type == "NumericRange":
            if self.value_sweep_radio: self.value_sweep_radio.setChecked(True)
            if self.sweep_loop_variable_name_input: self.sweep_loop_variable_name_input.setText(data.get("loop_variable_name", ""))
            if self.start_value_input: self.start_value_input.setText(str(data.get("start_value", "")))
            if self.stop_value_input: self.stop_value_input.setText(str(data.get("stop_value", "")))
            if self.step_value_input: self.step_value_input.setText(str(data.get("step_value", "")))
        elif sweep_type == "ValueList":
            if self.value_list_radio: self.value_list_radio.setChecked(True)
            if self.list_loop_variable_name_input: self.list_loop_variable_name_input.setText(data.get("loop_variable_name", ""))
            value_list = data.get("value_list", [])
            if self.value_list_input: self.value_list_input.setText(", ".join(map(str, value_list)))
        elif sweep_type == "FixedCount":
            if self.fixed_count_radio: self.fixed_count_radio.setChecked(True)
            if self.loop_count_spinbox: self.loop_count_spinbox.setValue(data.get("loop_count", 1))
            if self.count_loop_variable_name_input: self.count_loop_variable_name_input.setText(data.get("loop_variable_name", ""))
        else: # Default or old format (try to infer)
            if data.get("loop_count") is not None:
                 if self.fixed_count_radio: self.fixed_count_radio.setChecked(True)
                 if self.loop_count_spinbox: self.loop_count_spinbox.setValue(data.get("loop_count",1))
                 if self.count_loop_variable_name_input: self.count_loop_variable_name_input.setText(data.get("loop_variable_name", ""))
            elif data.get("start_value") is not None: # Assume NumericRange if start_value exists
                 if self.value_sweep_radio: self.value_sweep_radio.setChecked(True)
                 if self.sweep_loop_variable_name_input: self.sweep_loop_variable_name_input.setText(data.get("loop_variable_name", ""))
                 if self.start_value_input: self.start_value_input.setText(str(data.get("start_value", "")))
                 if self.stop_value_input: self.stop_value_input.setText(str(data.get("stop_value", "")))
                 if self.step_value_input: self.step_value_input.setText(str(data.get("step_value", "")))
            else: # Fallback if type cannot be determined
                 if self.value_sweep_radio: self.value_sweep_radio.setChecked(True)


    def get_loop_parameters(self) -> Optional[LoopActionItem]:
        item_id = self.existing_data.get("item_id") if self.existing_data else f"loop_{datetime.now().timestamp()}"
        display_name_text = self.loop_display_name_input.text().strip() if self.loop_display_name_input else ""

        is_sweep_range = self.value_sweep_radio.isChecked() if self.value_sweep_radio else False
        is_sweep_list = self.value_list_radio.isChecked() if self.value_list_radio else False
        is_count = self.fixed_count_radio.isChecked() if self.fixed_count_radio else False

        params: Dict[str, Any] = {
            "item_id": item_id,
            "action_type": "Loop",
            "display_name": display_name_text, # Keep user's display name if provided
            "looped_actions": self.existing_data.get("looped_actions", []) if self.existing_data else [],
            # Initialize all sweep/count params to None
            "sweep_type": None,
            "loop_variable_name": None,
            "start_value": None, "stop_value": None, "step_value": None,
            "value_list": None, "loop_count": None
        }

        auto_generated_display_name = ""

        if is_sweep_range:
            params["sweep_type"] = "NumericRange"
            var_name = self.sweep_loop_variable_name_input.text().strip() if self.sweep_loop_variable_name_input else ""
            start_str = self.start_value_input.text().strip() if self.start_value_input else ""
            stop_str = self.stop_value_input.text().strip() if self.stop_value_input else ""
            step_str = self.step_value_input.text().strip() if self.step_value_input else ""

            if not all([var_name, start_str, stop_str, step_str]):
                QMessageBox.warning(self, "Input Error", "For Numeric Range Sweep, all fields (Variable Name, Start, Stop, Step) must be filled.")
                return None
            try:
                params["loop_variable_name"] = var_name
                s_val, st_val, sp_val = float(start_str), float(stop_str), float(step_str)
                params["start_value"], params["stop_value"], params["step_value"] = s_val, st_val, sp_val
                if sp_val == 0:
                    QMessageBox.warning(self, "Input Error", "Step value cannot be zero for Numeric Range Sweep.")
                    return None
                if (sp_val > 0 and s_val > st_val) or (sp_val < 0 and s_val < st_val):
                    QMessageBox.warning(self, "Input Error", "Loop range and step direction mismatch for Numeric Range.")
                    return None
                auto_generated_display_name = f"Loop: {var_name} from {s_val} to {st_val} step {sp_val}"
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Start, Stop, and Step values must be valid numbers for Numeric Range.")
                return None
        
        elif is_sweep_list:
            params["sweep_type"] = "ValueList"
            var_name = self.list_loop_variable_name_input.text().strip() if self.list_loop_variable_name_input else ""
            list_str = self.value_list_input.text().strip() if self.value_list_input else ""
            if not var_name or not list_str:
                QMessageBox.warning(self, "Input Error", "For List of Values Sweep, Variable Name and Value List must be filled.")
                return None
            
            try:
                # Attempt to parse as numbers first, then fallback to strings
                parsed_list = []
                raw_values = [v.strip() for v in list_str.split(',') if v.strip()]
                if not raw_values:
                    QMessageBox.warning(self, "Input Error", "Value List cannot be empty.")
                    return None

                for val_str in raw_values:
                    try:
                        parsed_list.append(float(val_str)) # Try float
                    except ValueError:
                        try:
                            parsed_list.append(int(val_str)) # Try int
                        except ValueError:
                             parsed_list.append(val_str) # Fallback to string

                params["loop_variable_name"] = var_name
                params["value_list"] = parsed_list
                auto_generated_display_name = f"Loop: {var_name} over list ({len(parsed_list)} values)"
            except Exception as e: # Broad catch for parsing issues
                QMessageBox.warning(self, "Input Error", f"Error parsing Value List: {e}")
                return None

        elif is_count:
            params["sweep_type"] = "FixedCount"
            count = self.loop_count_spinbox.value() if self.loop_count_spinbox else 1
            params["loop_count"] = count
            var_name = self.count_loop_variable_name_input.text().strip() if self.count_loop_variable_name_input and self.count_loop_variable_name_input.text().strip() else None
            params["loop_variable_name"] = var_name
            var_part = f" ({var_name})" if var_name else ""
            auto_generated_display_name = f"Loop: {count} iterations{var_part}"
        else:
            QMessageBox.warning(self, "Input Error", "Please select a loop type.")
            return None
        
        if not display_name_text and auto_generated_display_name:
            params["display_name"] = auto_generated_display_name
        elif not display_name_text and not auto_generated_display_name: # Should not happen if one type is selected
            params["display_name"] = "Loop (Parameters Invalid)"


        return cast(LoopActionItem, params)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 1. 새 루프 정의 테스트
    dialog_new = LoopDefinitionDialog()
    if dialog_new.exec_() == QDialog.Accepted:
        new_loop_params = dialog_new.get_loop_parameters()
        if new_loop_params:
            print("New Loop Parameters:", new_loop_params)
        else:
            print("Failed to get new loop parameters (validation failed or dialog cancelled).")
    else:
        print("New Loop definition cancelled.")

    # 2. 기존 루프 데이터로 편집 테스트
    existing_data_sweep: LoopActionItem = {
        "item_id": "loop_123", "action_type": "Loop",
        "loop_variable_name": "Voltage", "start_value": 0.1, "stop_value": 1.0, "step_value": 0.1,
        "loop_count": None,
        "looped_actions": [], # 실제로는 내부 액션이 있을 수 있음
        "display_name": "Voltage Sweep 0.1-1.0V"
    }
    dialog_edit_sweep = LoopDefinitionDialog(existing_loop_data=existing_data_sweep)
    if dialog_edit_sweep.exec_() == QDialog.Accepted:
        updated_sweep_params = dialog_edit_sweep.get_loop_parameters()
        if updated_sweep_params:
            print("Updated Sweep Loop Parameters:", updated_sweep_params)
        else:
            print("Failed to get updated sweep loop parameters.")
    else:
        print("Edit Sweep Loop definition cancelled.")

    existing_data_count: LoopActionItem = {
        "item_id": "loop_456", "action_type": "Loop",
        "loop_variable_name": "Trial", "start_value": None, "stop_value": None, "step_value": None,
        "loop_count": 5,
        "looped_actions": [],
        "display_name": "Repeat 5 Trials"
    }
    dialog_edit_count = LoopDefinitionDialog(existing_loop_data=existing_data_count)
    if dialog_edit_count.exec_() == QDialog.Accepted:
        updated_count_params = dialog_edit_count.get_loop_parameters()
        if updated_count_params:
            print("Updated Count Loop Parameters:", updated_count_params)
        else:
            print("Failed to get updated count loop parameters.")
    else:
        print("Edit Count Loop definition cancelled.")

    # sys.exit(app.exec_()) # 테스트 시에는 이벤트 루프 실행 불필요