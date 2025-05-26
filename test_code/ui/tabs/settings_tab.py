# ui/tabs/settings_tab.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, Dict, Any

from core import constants
from core.hardware_control import I2CDevice

class SettingsTab(QWidget):
    settings_changed_signal = pyqtSignal(dict)
    evb_check_requested_signal = pyqtSignal() # EVB 연결 확인 요청 시그널

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # UI 멤버 변수 선언
        self.chip_id_input: Optional[QLineEdit] = None
        self.multimeter_use_checkbox: Optional[QCheckBox] = None
        self.multimeter_serial_input: Optional[QLineEdit] = None
        self.sourcemeter_use_checkbox: Optional[QCheckBox] = None
        self.sourcemeter_serial_input: Optional[QLineEdit] = None
        self.chamber_use_checkbox: Optional[QCheckBox] = None
        self.chamber_serial_input: Optional[QLineEdit] = None
        self.error_halts_sequence_checkbox: Optional[QCheckBox] = None
        self.save_settings_button: Optional[QPushButton] = None

        # EVB 상태 관련 UI 요소
        self.evb_status_label: Optional[QLabel] = None
        self.evb_check_button: Optional[QPushButton] = None

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        # EVB 상태 및 칩 ID 그룹
        evb_group = QGroupBox(constants.SETTINGS_EVB_STATUS_GROUP_TITLE)
        evb_layout = QGridLayout()

        self.chip_id_input = QLineEdit()
        self.chip_id_input.setPlaceholderText("e.g., 0x18 or 24")
        evb_layout.addWidget(QLabel(constants.SETTINGS_CHIP_ID_LABEL), 0, 0)
        evb_layout.addWidget(self.chip_id_input, 0, 1)

        self.evb_status_label = QLabel(constants.SETTINGS_EVB_STATUS_LABEL_TEXT + " Unknown")
        self.evb_status_label.setStyleSheet("QLabel { padding-top: 5px; }")
        evb_layout.addWidget(self.evb_status_label, 1, 0, 1, 2) # Span 2 columns

        self.evb_check_button = QPushButton(constants.SETTINGS_EVB_BTN_CHECK_TEXT)
        self.evb_check_button.clicked.connect(self.evb_check_requested_signal.emit)
        evb_layout.addWidget(self.evb_check_button, 2, 0, 1, 2) # Span 2 columns

        evb_group.setLayout(evb_layout)
        main_layout.addWidget(evb_group)

        # 계측기 설정 그룹 (기존 로직 유지)
        instrument_group = QGroupBox(constants.SETTINGS_INSTRUMENT_GROUP_TITLE)
        instrument_layout = QGridLayout()
        # ... (멀티미터, 소스미터, 챔버 설정 UI 요소들 추가) ...
        # 예시:
        self.multimeter_use_checkbox = QCheckBox(constants.SETTINGS_USE_MULTIMETER_LABEL)
        self.multimeter_serial_input = QLineEdit()
        instrument_layout.addWidget(self.multimeter_use_checkbox, 0, 0)
        instrument_layout.addWidget(QLabel(constants.SETTINGS_MULTIMETER_SERIAL_LABEL), 1, 0)
        instrument_layout.addWidget(self.multimeter_serial_input, 1, 1)
        # ... (다른 계측기들도 유사하게) ...
        instrument_group.setLayout(instrument_layout)
        main_layout.addWidget(instrument_group)

        # 실행 옵션 그룹 (기존 로직 유지)
        execution_group = QGroupBox(constants.SETTINGS_EXECUTION_GROUP_TITLE)
        execution_layout = QVBoxLayout()
        self.error_halts_sequence_checkbox = QCheckBox(constants.SETTINGS_ERROR_HALTS_SEQUENCE_LABEL)
        execution_layout.addWidget(self.error_halts_sequence_checkbox)
        execution_group.setLayout(execution_layout)
        main_layout.addWidget(execution_group)

        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.save_settings_button = QPushButton(constants.SETTINGS_SAVE_BUTTON_TEXT)
        self.save_settings_button.clicked.connect(self._on_save_settings)
        main_layout.addWidget(self.save_settings_button, alignment=Qt.AlignRight)

        self.setLayout(main_layout)

    def populate_settings(self, settings_data: Dict[str, Any], i2c_device_instance: Optional[I2CDevice]):
        # 기존 설정 값들 UI에 채우는 로직
        if self.chip_id_input: self.chip_id_input.setText(str(settings_data.get(constants.SETTINGS_CHIP_ID_KEY, "")))
        # ... (다른 설정 값들도 UI에 채우기) ...
        if self.error_halts_sequence_checkbox: self.error_halts_sequence_checkbox.setChecked(settings_data.get(constants.SETTINGS_ERROR_HALTS_SEQUENCE_KEY, False))

        # EVB 상태 업데이트
        self.update_evb_status_display(i2c_device_instance, settings_data.get(constants.SETTINGS_CHIP_ID_KEY))

    def update_evb_status_display(self, i2c_device: Optional[I2CDevice], chip_id: Optional[str]):
        if not self.evb_status_label:
            return

        status_text = constants.SETTINGS_EVB_STATUS_LABEL_TEXT # "EVB Connection Status:"
        style_sheet_red = "QLabel { color: red; font-weight: bold; }"
        style_sheet_green = "QLabel { color: green; font-weight: bold; }"
        style_sheet_orange = "QLabel { color: orange; }"

        current_chip_id = chip_id if chip_id else (self.chip_id_input.text() if self.chip_id_input else None)

        if current_chip_id:
            if i2c_device and i2c_device.is_opened:
                status_text += f" Connected (Chip ID: {current_chip_id})"
                self.evb_status_label.setStyleSheet(style_sheet_green)
            elif i2c_device and not i2c_device.is_opened:
                status_text += f" Connection Failed (Chip ID: {current_chip_id})"
                self.evb_status_label.setStyleSheet(style_sheet_red)
            else: # i2c_device is None (초기화 안됨 또는 실패)
                status_text += f" Not Initialized (Chip ID: {current_chip_id})"
                self.evb_status_label.setStyleSheet(style_sheet_red)
        else:
            status_text += " Chip ID not set"
            self.evb_status_label.setStyleSheet(style_sheet_orange)
        self.evb_status_label.setText(status_text)

    def _on_save_settings(self):
        # UI에서 현재 설정 값들을 읽어와서 딕셔너리로 만듦
        current_ui_settings = {
            constants.SETTINGS_CHIP_ID_KEY: self.chip_id_input.text() if self.chip_id_input else "",
            # ... (다른 설정 값들도 읽어오기) ...
            constants.SETTINGS_ERROR_HALTS_SEQUENCE_KEY: self.error_halts_sequence_checkbox.isChecked() if self.error_halts_sequence_checkbox else False,
        }
        self.settings_changed_signal.emit(current_ui_settings)

    def get_current_chip_id_input(self) -> Optional[str]:
        """SettingsTab의 Chip ID 입력 필드 값을 반환합니다."""
        if self.chip_id_input:
            return self.chip_id_input.text().strip()
        return None