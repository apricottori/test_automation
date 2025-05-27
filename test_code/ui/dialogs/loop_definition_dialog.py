# ui/dialogs/loop_definition_dialog.py
import sys
from typing import List, Tuple, Dict, Any, Optional, cast, Literal
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QWidget, QSpinBox, QDoubleSpinBox, QGroupBox,
    QRadioButton # QRadioButton 추가
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
        self.value_sweep_radio: Optional[QRadioButton] = None
        self.fixed_count_radio: Optional[QRadioButton] = None
        
        self.sweep_params_group: Optional[QGroupBox] = None
        self.loop_variable_name_input: Optional[QLineEdit] = None
        self.start_value_input: Optional[QLineEdit] = None # QDoubleSpinBox 대신 QLineEdit + QDoubleValidator 사용
        self.stop_value_input: Optional[QLineEdit] = None
        self.step_value_input: Optional[QLineEdit] = None

        self.count_params_group: Optional[QGroupBox] = None 
        self.loop_count_spinbox: Optional[QSpinBox] = None

        self.button_box: Optional[QDialogButtonBox] = None
        self._double_validator = QDoubleValidator() # 유효성 검사기

        self._init_ui()
        self._connect_signals()
        if self.existing_data:
            self._load_existing_data()
        else:
            if self.value_sweep_radio: self.value_sweep_radio.setChecked(True) # 기본 선택
        self._update_ui_for_loop_type()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.loop_display_name_input = QLineEdit()
        self.loop_display_name_input.setPlaceholderText("e.g., Temperature Sweep 25-85C")
        form_layout.addRow("Loop Display Name (Optional):", self.loop_display_name_input)

        # --- Loop Type Selection --- 
        loop_type_group = QGroupBox("Loop Type")
        loop_type_layout = QVBoxLayout(loop_type_group)
        self.value_sweep_radio = QRadioButton("Variable Value Sweep")
        self.fixed_count_radio = QRadioButton("Fixed Number of Iterations")
        loop_type_layout.addWidget(self.value_sweep_radio)
        loop_type_layout.addWidget(self.fixed_count_radio)
        form_layout.addRow(loop_type_group)

        # --- Value Sweep Parameters --- 
        self.sweep_params_group = QGroupBox("Value Sweep Parameters")
        sweep_layout = QFormLayout(self.sweep_params_group)
        self.loop_variable_name_input = QLineEdit()
        self.loop_variable_name_input.setPlaceholderText("e.g., Temperature, VDD_Voltage (no spaces)")
        self.start_value_input = QLineEdit(); self.start_value_input.setValidator(self._double_validator)
        self.stop_value_input = QLineEdit(); self.stop_value_input.setValidator(self._double_validator)
        self.step_value_input = QLineEdit(); self.step_value_input.setValidator(self._double_validator)
        sweep_layout.addRow("Loop Variable Name:", self.loop_variable_name_input)
        sweep_layout.addRow("Start Value:", self.start_value_input)
        sweep_layout.addRow("Stop Value:", self.stop_value_input)
        sweep_layout.addRow("Step Value:", self.step_value_input)
        form_layout.addRow(self.sweep_params_group)

        # --- Fixed Count Parameters --- 
        self.count_params_group = QGroupBox("Fixed Count Parameters")
        count_layout = QFormLayout(self.count_params_group)
        self.loop_count_spinbox = QSpinBox()
        self.loop_count_spinbox.setMinimum(1)
        self.loop_count_spinbox.setMaximum(1000000) # 충분히 큰 값
        self.loop_count_spinbox.setValue(10)
        count_layout.addRow("Number of Iterations:", self.loop_count_spinbox)
        form_layout.addRow(self.count_params_group)
        
        main_layout.addLayout(form_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(self.button_box)

    def _connect_signals(self):
        if self.value_sweep_radio: self.value_sweep_radio.toggled.connect(self._update_ui_for_loop_type)
        if self.fixed_count_radio: self.fixed_count_radio.toggled.connect(self._update_ui_for_loop_type)
        if self.button_box: 
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)

    def _update_ui_for_loop_type(self):
        is_sweep = self.value_sweep_radio.isChecked() if self.value_sweep_radio else False
        is_count = self.fixed_count_radio.isChecked() if self.fixed_count_radio else False

        if self.sweep_params_group: self.sweep_params_group.setEnabled(is_sweep)
        if self.count_params_group: self.count_params_group.setEnabled(is_count)
        
        # 만약 라디오 버튼이 서로 배타적으로 동작하지 않는다면, 한쪽이 선택될 때 다른 쪽을 해제
        if is_sweep and self.fixed_count_radio and self.fixed_count_radio.isChecked():
            self.fixed_count_radio.setChecked(False)
        elif is_count and self.value_sweep_radio and self.value_sweep_radio.isChecked():
            self.value_sweep_radio.setChecked(False)

    def _load_existing_data(self):
        if not self.existing_data: return
        data = self.existing_data

        if self.loop_display_name_input: self.loop_display_name_input.setText(data.get("display_name", ""))

        is_count_loop = data.get("loop_count") is not None
        if self.value_sweep_radio: self.value_sweep_radio.setChecked(not is_count_loop)
        if self.fixed_count_radio: self.fixed_count_radio.setChecked(is_count_loop)

        if not is_count_loop: # Value Sweep
            if self.loop_variable_name_input: self.loop_variable_name_input.setText(data.get("loop_variable_name", ""))
            if self.start_value_input: self.start_value_input.setText(str(data.get("start_value", "")))
            if self.stop_value_input: self.stop_value_input.setText(str(data.get("stop_value", "")))
            if self.step_value_input: self.step_value_input.setText(str(data.get("step_value", "")))
        else: # Fixed Count
            if self.loop_count_spinbox: self.loop_count_spinbox.setValue(data.get("loop_count", 1))
            # Count 기반 루프일 때 Variable Name은 선택사항이 될 수 있음 (단순 반복용)
            if self.loop_variable_name_input: self.loop_variable_name_input.setText(data.get("loop_variable_name", "")) 


    def get_loop_parameters(self) -> Optional[LoopActionItem]:
        item_id = self.existing_data.get("item_id") if self.existing_data else f"loop_{datetime.now().timestamp()}"
        display_name = self.loop_display_name_input.text().strip() if self.loop_display_name_input else ""

        is_sweep = self.value_sweep_radio.isChecked() if self.value_sweep_radio else False
        is_count = self.fixed_count_radio.isChecked() if self.fixed_count_radio else False

        params: Dict[str, Any] = {
            "item_id": item_id,
            "action_type": "Loop", # Literal["Loop"]
            "display_name": display_name,
            "looped_actions": self.existing_data.get("looped_actions", []) if self.existing_data else [] # 내부 액션은 유지
        }

        if is_sweep:
            var_name = self.loop_variable_name_input.text().strip() if self.loop_variable_name_input else ""
            start_str = self.start_value_input.text().strip() if self.start_value_input else ""
            stop_str = self.stop_value_input.text().strip() if self.stop_value_input else ""
            step_str = self.step_value_input.text().strip() if self.step_value_input else ""

            if not all([var_name, start_str, stop_str, step_str]):
                QMessageBox.warning(self, "Input Error", "For Value Sweep, all fields (Variable Name, Start, Stop, Step) must be filled.")
                return None
            try:
                params["loop_variable_name"] = var_name
                params["start_value"] = float(start_str)
                params["stop_value"] = float(stop_str)
                params["step_value"] = float(step_str)
                if params["step_value"] == 0:
                    QMessageBox.warning(self, "Input Error", "Step value cannot be zero for Value Sweep.")
                    return None
                # 추가적인 범위 검증 (start < stop if step > 0 등)
                if (params["step_value"] > 0 and params["start_value"] > params["stop_value"]) or \
                   (params["step_value"] < 0 and params["start_value"] < params["stop_value"]):
                    QMessageBox.warning(self, "Input Error", "Loop range and step direction mismatch.")
                    return None

            except ValueError:
                QMessageBox.warning(self, "Input Error", "Start, Stop, and Step values must be valid numbers.")
                return None
            params["loop_count"] = None # 스윕 루프에서는 loop_count 사용 안 함
        
        elif is_count:
            count = self.loop_count_spinbox.value() if self.loop_count_spinbox else 1
            params["loop_count"] = count
            # 횟수 기반 루프에서도 변수명은 가질 수 있음 (예: 반복 카운터로 사용)
            params["loop_variable_name"] = self.loop_variable_name_input.text().strip() if self.loop_variable_name_input and self.loop_variable_name_input.text().strip() else None
            params["start_value"] = None
            params["stop_value"] = None
            params["step_value"] = None
        else:
            QMessageBox.warning(self, "Input Error", "Please select a loop type (Value Sweep or Fixed Count).")
            return None
        
        if not display_name: # 표시 이름 자동 생성 (선택적)
            if is_sweep and params.get("loop_variable_name"):
                params["display_name"] = f"Loop: {params['loop_variable_name']} from {params['start_value']} to {params['stop_value']} step {params['step_value']}"
            elif is_count:
                var_part = f" ({params['loop_variable_name']})" if params.get("loop_variable_name") else ""
                params["display_name"] = f"Loop: {params['loop_count']} iterations{var_part}"
            else:
                params["display_name"] = "Loop (Parameters Undefined)"

        # LoopActionItem 타입으로 캐스팅하여 반환 (mypy 등 타입 검사기 만족용)
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