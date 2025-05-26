# ui/tabs/settings_tab.py
import sys
from typing import Dict, Any, Optional, Callable, cast, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QCheckBox, QMessageBox, QApplication, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt

# --- 코어 모듈 임포트 ---
from core import constants
from core.settings_manager import SettingsManager
from core.hardware_control import I2CDevice # EVB 연결 확인용

if TYPE_CHECKING:
    from main_window import RegMapWindow


class SettingsTab(QWidget):
    settings_changed_signal = pyqtSignal(dict)
    check_evb_connection_requested = pyqtSignal()
    reinitialize_hardware_requested = pyqtSignal(dict)

    def __init__(self,
                 settings_manager_instance: SettingsManager,
                 parent: Optional[QWidget] = None,
                 main_window_ref: Optional['RegMapWindow'] = None
                 ):
        super().__init__(parent)
        self.settings_manager = settings_manager_instance
        self.main_window_ref = main_window_ref # 메인 윈도우 참조
        self.current_settings: Dict[str, Any] = {}

        # UI 멤버 변수 선언 (타입 힌트 포함)
        self.chip_id_input: Optional[QLineEdit] = None
        self.evb_status_label: Optional[QLabel] = None
        self.check_evb_button: Optional[QPushButton] = None

        self.use_multimeter_checkbox: Optional[QCheckBox] = None
        self.multimeter_serial_label: Optional[QLabel] = None
        self.multimeter_serial_input: Optional[QLineEdit] = None

        self.use_sourcemeter_checkbox: Optional[QCheckBox] = None
        self.sourcemeter_serial_label: Optional[QLabel] = None
        self.sourcemeter_serial_input: Optional[QLineEdit] = None

        self.use_chamber_checkbox: Optional[QCheckBox] = None
        self.chamber_serial_label: Optional[QLabel] = None
        self.chamber_serial_input: Optional[QLineEdit] = None

        self.error_halts_sequence_checkbox: Optional[QCheckBox] = None
        self.save_settings_button: Optional[QPushButton] = None

        self._init_ui()
        self.load_settings()

    def _init_ui(self) -> None:
        """UI 요소들을 초기화하고 레이아웃을 설정합니다."""
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop) # 위쪽 정렬

        # EVB 상태 그룹
        evb_group_box = self._create_evb_status_group()
        main_layout.addWidget(evb_group_box)

        # 계측기 설정 그룹
        instrument_group_box = self._create_instrument_settings_group()
        main_layout.addWidget(instrument_group_box)

        # 실행 옵션 그룹
        execution_group_box = self._create_execution_options_group()
        main_layout.addWidget(execution_group_box)

        # 설정 저장 버튼
        self.save_settings_button = QPushButton(constants.SETTINGS_SAVE_BUTTON_TEXT, self)
        if self.save_settings_button: # None 체크
            self.save_settings_button.clicked.connect(self._save_settings_and_notify)
            main_layout.addWidget(self.save_settings_button, 0, Qt.AlignCenter) # 가운데 정렬

        main_layout.addStretch(1) # 하단에 공간 추가

    def _create_evb_status_group(self) -> QGroupBox:
        """EVB 상태 및 칩 ID 설정 그룹 박스를 생성합니다."""
        evb_group_box = QGroupBox(constants.SETTINGS_EVB_STATUS_GROUP_TITLE, self)
        layout = QGridLayout(evb_group_box)
        layout.setColumnStretch(1, 1) # 입력 필드가 남은 공간을 차지하도록

        # Chip ID
        chip_id_label = QLabel(constants.SETTINGS_CHIP_ID_LABEL, evb_group_box)
        self.chip_id_input = QLineEdit(evb_group_box)
        self.chip_id_input.setPlaceholderText("e.g., 0x18")
        layout.addWidget(chip_id_label, 0, 0)
        layout.addWidget(self.chip_id_input, 0, 1)

        # EVB Connection Status
        evb_status_text_label = QLabel(constants.SETTINGS_EVB_STATUS_LABEL_TEXT, evb_group_box)
        self.evb_status_label = QLabel("Unknown", evb_group_box) # 초기 상태
        self.evb_status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(evb_status_text_label, 1, 0)
        layout.addWidget(self.evb_status_label, 1, 1)

        # Check EVB Connection Button
        self.check_evb_button = QPushButton(constants.SETTINGS_EVB_BTN_CHECK_TEXT, evb_group_box)
        if self.check_evb_button: # None 체크
             self.check_evb_button.clicked.connect(self.check_evb_connection_requested.emit)
        layout.addWidget(self.check_evb_button, 2, 0, 1, 2, Qt.AlignCenter) # 버튼을 가운데 정렬

        return evb_group_box

    def _create_instrument_settings_group(self) -> QGroupBox:
        """계측기 설정 그룹 박스를 생성합니다."""
        instrument_group_box = QGroupBox(constants.SETTINGS_INSTRUMENT_GROUP_TITLE, self)
        layout = QGridLayout(instrument_group_box)
        layout.setColumnStretch(1, 1) # 입력 필드가 남은 공간을 차지하도록

        current_row = 0

        # Multimeter
        self.use_multimeter_checkbox = QCheckBox(constants.SETTINGS_USE_MULTIMETER_LABEL, instrument_group_box)
        self.multimeter_serial_label = QLabel(constants.SETTINGS_MULTIMETER_SERIAL_LABEL, instrument_group_box)
        self.multimeter_serial_input = QLineEdit(instrument_group_box)
        self.multimeter_serial_input.setPlaceholderText("e.g., USB0::...")

        layout.addWidget(self.use_multimeter_checkbox, current_row, 0, 1, 2) # 체크박스는 2열 차지
        current_row += 1
        layout.addWidget(self.multimeter_serial_label, current_row, 0)
        layout.addWidget(self.multimeter_serial_input, current_row, 1)
        current_row += 1

        if self.use_multimeter_checkbox: # None 체크
            self.use_multimeter_checkbox.toggled.connect(self.multimeter_serial_label.setEnabled)
            self.use_multimeter_checkbox.toggled.connect(self.multimeter_serial_input.setEnabled)

        # Sourcemeter
        self.use_sourcemeter_checkbox = QCheckBox(constants.SETTINGS_USE_SOURCEMETER_LABEL, instrument_group_box)
        self.sourcemeter_serial_label = QLabel(constants.SETTINGS_SOURCEMETER_SERIAL_LABEL, instrument_group_box)
        self.sourcemeter_serial_input = QLineEdit(instrument_group_box)
        self.sourcemeter_serial_input.setPlaceholderText("e.g., GPIB0::24::INSTR")

        layout.addWidget(self.use_sourcemeter_checkbox, current_row, 0, 1, 2) # 체크박스는 2열 차지
        current_row += 1
        layout.addWidget(self.sourcemeter_serial_label, current_row, 0)
        layout.addWidget(self.sourcemeter_serial_input, current_row, 1)
        current_row += 1

        if self.use_sourcemeter_checkbox: # None 체크
            self.use_sourcemeter_checkbox.toggled.connect(self.sourcemeter_serial_label.setEnabled)
            self.use_sourcemeter_checkbox.toggled.connect(self.sourcemeter_serial_input.setEnabled)

        # Chamber
        self.use_chamber_checkbox = QCheckBox(constants.SETTINGS_USE_CHAMBER_LABEL, instrument_group_box)
        self.chamber_serial_label = QLabel(constants.SETTINGS_CHAMBER_SERIAL_LABEL, instrument_group_box)
        self.chamber_serial_input = QLineEdit(instrument_group_box)
        self.chamber_serial_input.setPlaceholderText("e.g., COM3 or GPIB0::1::INSTR")

        layout.addWidget(self.use_chamber_checkbox, current_row, 0, 1, 2) # 체크박스는 2열 차지
        current_row += 1
        layout.addWidget(self.chamber_serial_label, current_row, 0)
        layout.addWidget(self.chamber_serial_input, current_row, 1)
        # current_row += 1 # 마지막 요소이므로 row 증가 불필요

        if self.use_chamber_checkbox: # None 체크
            self.use_chamber_checkbox.toggled.connect(self.chamber_serial_label.setEnabled)
            self.use_chamber_checkbox.toggled.connect(self.chamber_serial_input.setEnabled)

        # 초기 상태 설정 (UI 요소가 모두 생성된 후)
        if self.multimeter_serial_label: self.multimeter_serial_label.setEnabled(False)
        if self.multimeter_serial_input: self.multimeter_serial_input.setEnabled(False)
        if self.sourcemeter_serial_label: self.sourcemeter_serial_label.setEnabled(False)
        if self.sourcemeter_serial_input: self.sourcemeter_serial_input.setEnabled(False)
        if self.chamber_serial_label: self.chamber_serial_label.setEnabled(False)
        if self.chamber_serial_input: self.chamber_serial_input.setEnabled(False)

        return instrument_group_box

    def _create_execution_options_group(self) -> QGroupBox:
        """실행 옵션 그룹 박스를 생성합니다."""
        execution_group_box = QGroupBox(constants.SETTINGS_EXECUTION_GROUP_TITLE, self)
        layout = QVBoxLayout(execution_group_box) # 간단한 옵션이므로 QVBoxLayout 사용

        self.error_halts_sequence_checkbox = QCheckBox(constants.SETTINGS_ERROR_HALTS_SEQUENCE_LABEL, execution_group_box)
        if self.error_halts_sequence_checkbox: # None 체크
            layout.addWidget(self.error_halts_sequence_checkbox)

        return execution_group_box

    def load_settings(self) -> None:
        """설정 파일에서 설정을 로드하여 UI에 반영합니다."""
        self.current_settings = self.settings_manager.load_settings()

        if self.chip_id_input:
            self.chip_id_input.setText(self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, ""))

        if self.use_multimeter_checkbox:
            use_mm = self.current_settings.get(constants.SETTINGS_MULTIMETER_USE_KEY, False)
            self.use_multimeter_checkbox.setChecked(use_mm)
            if self.multimeter_serial_label: self.multimeter_serial_label.setEnabled(use_mm)
            if self.multimeter_serial_input:
                self.multimeter_serial_input.setEnabled(use_mm)
                self.multimeter_serial_input.setText(self.current_settings.get(constants.SETTINGS_MULTIMETER_SERIAL_KEY, ""))

        if self.use_sourcemeter_checkbox:
            use_sm = self.current_settings.get(constants.SETTINGS_SOURCEMETER_USE_KEY, False)
            self.use_sourcemeter_checkbox.setChecked(use_sm)
            if self.sourcemeter_serial_label: self.sourcemeter_serial_label.setEnabled(use_sm)
            if self.sourcemeter_serial_input:
                self.sourcemeter_serial_input.setEnabled(use_sm)
                self.sourcemeter_serial_input.setText(self.current_settings.get(constants.SETTINGS_SOURCEMETER_SERIAL_KEY, ""))

        if self.use_chamber_checkbox:
            use_ch = self.current_settings.get(constants.SETTINGS_CHAMBER_USE_KEY, False)
            self.use_chamber_checkbox.setChecked(use_ch)
            if self.chamber_serial_label: self.chamber_serial_label.setEnabled(use_ch)
            if self.chamber_serial_input:
                self.chamber_serial_input.setEnabled(use_ch)
                self.chamber_serial_input.setText(self.current_settings.get(constants.SETTINGS_CHAMBER_SERIAL_KEY, ""))

        if self.error_halts_sequence_checkbox:
            self.error_halts_sequence_checkbox.setChecked(self.current_settings.get(constants.SETTINGS_ERROR_HALTS_SEQUENCE_KEY, True))

        # EVB 상태는 로드 시 직접 업데이트하지 않고, 사용자가 버튼을 누르거나 프로그램 시작 시 업데이트
        self.update_evb_status(False, "Press 'Check EVB Connection'") # 초기 메시지

    def _save_settings(self) -> bool:
        """현재 UI의 설정 값들을 current_settings에 저장하고 파일로 저장합니다."""
        if not self.chip_id_input or \
           not self.use_multimeter_checkbox or not self.multimeter_serial_input or \
           not self.use_sourcemeter_checkbox or not self.sourcemeter_serial_input or \
           not self.use_chamber_checkbox or not self.chamber_serial_input or \
           not self.error_halts_sequence_checkbox:
            QMessageBox.critical(self, constants.MSG_TITLE_ERROR, "UI 요소가 올바르게 초기화되지 않았습니다.")
            return False

        self.current_settings[constants.SETTINGS_CHIP_ID_KEY] = self.chip_id_input.text().strip()

        self.current_settings[constants.SETTINGS_MULTIMETER_USE_KEY] = self.use_multimeter_checkbox.isChecked()
        self.current_settings[constants.SETTINGS_MULTIMETER_SERIAL_KEY] = self.multimeter_serial_input.text().strip()

        self.current_settings[constants.SETTINGS_SOURCEMETER_USE_KEY] = self.use_sourcemeter_checkbox.isChecked()
        self.current_settings[constants.SETTINGS_SOURCEMETER_SERIAL_KEY] = self.sourcemeter_serial_input.text().strip()

        self.current_settings[constants.SETTINGS_CHAMBER_USE_KEY] = self.use_chamber_checkbox.isChecked()
        self.current_settings[constants.SETTINGS_CHAMBER_SERIAL_KEY] = self.chamber_serial_input.text().strip()

        self.current_settings[constants.SETTINGS_ERROR_HALTS_SEQUENCE_KEY] = self.error_halts_sequence_checkbox.isChecked()

        if self.settings_manager.save_settings(self.current_settings):
            QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, constants.MSG_SETTINGS_SAVED)
            return True
        else:
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_SETTINGS_SAVE_FAILED)
            return False

    def _save_settings_and_notify(self) -> None:
        """설정을 저장하고, 변경 사항을 알리며, 필요한 경우 하드웨어 재초기화를 요청합니다."""
        # 기존 설정을 복사해둠 (변경 여부 비교용)
        old_settings_copy = self.current_settings.copy()

        if self._save_settings(): # UI의 현재 값을 current_settings에 업데이트하고 파일에 저장
            self.settings_changed_signal.emit(self.current_settings)

            # 하드웨어 관련 설정이 변경되었는지 확인
            hw_related_keys = [
                constants.SETTINGS_CHIP_ID_KEY,
                constants.SETTINGS_MULTIMETER_USE_KEY, constants.SETTINGS_MULTIMETER_SERIAL_KEY,
                constants.SETTINGS_SOURCEMETER_USE_KEY, constants.SETTINGS_SOURCEMETER_SERIAL_KEY,
                constants.SETTINGS_CHAMBER_USE_KEY, constants.SETTINGS_CHAMBER_SERIAL_KEY
            ]
            
            requires_reinitialization = False
            for key in hw_related_keys:
                if old_settings_copy.get(key) != self.current_settings.get(key):
                    requires_reinitialization = True
                    break
            
            if requires_reinitialization:
                reply = QMessageBox.question(self, "하드웨어 재초기화",
                                             "하드웨어 관련 설정이 변경되었습니다.\n"
                                             "변경된 설정을 적용하려면 하드웨어를 재초기화해야 합니다.\n"
                                             "지금 재초기화하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.reinitialize_hardware_requested.emit(self.current_settings)


    def update_evb_status(self, is_connected: bool, message: str = "") -> None:
        """EVB 연결 상태를 UI에 업데이트합니다."""
        if self.evb_status_label: # None 체크
            if is_connected:
                self.evb_status_label.setText(f"Connected ({message})")
                self.evb_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.evb_status_label.setText(f"Disconnected ({message})")
                self.evb_status_label.setStyleSheet("color: red; font-weight: bold;")

    def get_current_settings(self) -> Dict[str, Any]:
        """현재 로드되거나 저장된 설정을 반환합니다."""
        # UI의 현재 상태를 반영하기 위해 _save_settings와 유사한 로직으로 current_settings를 한번 더 업데이트 할 수 있으나,
        # 일반적으로는 load_settings 후 또는 _save_settings 후의 current_settings를 사용합니다.
        # 여기서는 _save_settings가 호출될 때 current_settings가 업데이트되므로, 그 값을 사용합니다.
        # 만약 저장하지 않고 현재 UI의 값을 바로 가져가야 한다면, 아래와 같이 UI에서 직접 읽어야 합니다.
        
        # 현재 UI의 값을 즉시 반영하여 반환하는 경우:
        temp_settings: Dict[str, Any] = {}
        if self.chip_id_input: temp_settings[constants.SETTINGS_CHIP_ID_KEY] = self.chip_id_input.text().strip()
        
        if self.use_multimeter_checkbox and self.multimeter_serial_input:
            temp_settings[constants.SETTINGS_MULTIMETER_USE_KEY] = self.use_multimeter_checkbox.isChecked()
            temp_settings[constants.SETTINGS_MULTIMETER_SERIAL_KEY] = self.multimeter_serial_input.text().strip()
        
        if self.use_sourcemeter_checkbox and self.sourcemeter_serial_input:
            temp_settings[constants.SETTINGS_SOURCEMETER_USE_KEY] = self.use_sourcemeter_checkbox.isChecked()
            temp_settings[constants.SETTINGS_SOURCEMETER_SERIAL_KEY] = self.sourcemeter_serial_input.text().strip()

        if self.use_chamber_checkbox and self.chamber_serial_input:
            temp_settings[constants.SETTINGS_CHAMBER_USE_KEY] = self.use_chamber_checkbox.isChecked()
            temp_settings[constants.SETTINGS_CHAMBER_SERIAL_KEY] = self.chamber_serial_input.text().strip()
            
        if self.error_halts_sequence_checkbox:
            temp_settings[constants.SETTINGS_ERROR_HALTS_SEQUENCE_KEY] = self.error_halts_sequence_checkbox.isChecked()
            
        # last_json_path 등 UI에 직접 매핑되지 않지만 유지해야 하는 설정은 self.current_settings에서 가져옴
        temp_settings[constants.SETTINGS_LAST_JSON_PATH_KEY] = self.current_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY, "")
        temp_settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY] = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
        
        return temp_settings

if __name__ == '__main__':
    # 이 파일 단독 실행을 위한 테스트 코드
    app = QApplication(sys.argv)
    
    # SettingsManager 목업 또는 실제 인스턴스 필요
    # 여기서는 간단히 Dict로 대체
    mock_settings_manager = SettingsManager(config_file_path=constants.DEFAULT_CONFIG_FILE)

    main_window = QWidget() # SettingsTab의 부모가 될 수 있는 QWidget 목업
    tab = SettingsTab(settings_manager_instance=mock_settings_manager, parent=main_window)
    tab.show()
    sys.exit(app.exec_())