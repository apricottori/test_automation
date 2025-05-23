# ui/tabs/settings_tab.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QCheckBox,
    QPushButton, QSpacerItem, QSizePolicy, QGroupBox, QHBoxLayout,
    QApplication, QStyle,QMessageBox,QMainWindow
)
from PyQt5.QtCore import pyqtSignal, Qt, QSize,pyqtSlot
from PyQt5.QtGui import QIcon
from typing import Optional, Dict, Any # Tuple 제거, Any 추가

# --- 수정된 임포트 경로 ---
from core import constants # UI 문자열, 스타일 상수 등을 위해
from core.hardware_control import I2CDevice # I2CDevice 타입 힌팅용

class SettingsTab(QWidget):
    """
    "Settings" 탭의 UI 및 로직을 담당하는 클래스입니다.
    Chip ID, 장비 사용 여부 및 시리얼 번호, 실행 옵션 설정을 관리합니다.
    설정 변경 시 settings_changed_signal을 발생시켜 메인 윈도우에 알립니다.
    """
    settings_changed_signal = pyqtSignal(dict) # 현재 UI의 설정 값들을 담아 발생

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(15, 15, 15, 15)
        self._main_layout.setSpacing(20) # 그룹박스 간 간격

        # UI 멤버 변수 선언 (타입 힌팅 포함)
        self.chip_id_input: Optional[QLineEdit] = None
        self.mm_use_checkbox: Optional[QCheckBox] = None
        self.mm_serial_input: Optional[QLineEdit] = None
        self.sm_use_checkbox: Optional[QCheckBox] = None
        self.sm_serial_input: Optional[QLineEdit] = None
        self.chamber_use_checkbox: Optional[QCheckBox] = None
        self.chamber_serial_input: Optional[QLineEdit] = None
        self.error_halts_sequence_checkbox: Optional[QCheckBox] = None
        self.save_button: Optional[QPushButton] = None
        
        # EVB 연결 확인용 UI 요소
        self.evb_status_label: Optional[QLabel] = None
        self.check_evb_button: Optional[QPushButton] = None
        
        # RegMapWindow로부터 전달받을 i2c_device 인스턴스
        self._i2c_device_ref: Optional[I2CDevice] = None

        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        """Settings 탭의 UI 요소들을 생성하고 배치합니다."""

        # --- Chip ID and EVB Status Group ---
        chip_config_group = QGroupBox("Chip & EVB Configuration")
        chip_config_layout = QGridLayout(chip_config_group)

        chip_id_label = QLabel(constants.SETTINGS_CHIP_ID_LABEL)
        self.chip_id_input = QLineEdit()
        self.chip_id_input.setPlaceholderText("e.g., 0x18 or 24")
        chip_config_layout.addWidget(chip_id_label, 0, 0)
        chip_config_layout.addWidget(self.chip_id_input, 0, 1)

        evb_status_title_label = QLabel("<b>EVB 연결 상태:</b>")
        self.evb_status_label = QLabel("확인 필요") # 초기 상태
        self.evb_status_label.setStyleSheet("padding: 3px; font-style: italic;")
        
        self.check_evb_button = QPushButton("EVB 연결 확인")
        try:
            app_instance = QApplication.instance()
            if app_instance:
                self.check_evb_button.setIcon(app_instance.style().standardIcon(QStyle.SP_BrowserReload))
        except Exception as e:
            print(f"Warning (SettingsTab): Could not set icon for check_evb_button: {e}")

        chip_config_layout.addWidget(evb_status_title_label, 1, 0)
        chip_config_layout.addWidget(self.evb_status_label, 1, 1)
        chip_config_layout.addWidget(self.check_evb_button, 2, 0, 1, 2) # 버튼은 두 컬럼에 걸쳐 배치

        self._main_layout.addWidget(chip_config_group)


        # --- Instrument Settings Group ---
        instrument_group = QGroupBox("Instrument Configuration")
        instrument_layout = QGridLayout(instrument_group)
        instrument_layout.setSpacing(10)

        self.mm_use_checkbox = QCheckBox(constants.SETTINGS_USE_MULTIMETER_LABEL)
        mm_serial_label = QLabel(constants.SETTINGS_MULTIMETER_SERIAL_LABEL)
        self.mm_serial_input = QLineEdit()
        self.mm_serial_input.setPlaceholderText("e.g., SERIAL_MM_123 or GPIB0::22::INSTR")
        self.mm_serial_input.setEnabled(False)
        instrument_layout.addWidget(self.mm_use_checkbox, 0, 0, 1, 2)
        instrument_layout.addWidget(mm_serial_label, 1, 0)
        instrument_layout.addWidget(self.mm_serial_input, 1, 1)

        self.sm_use_checkbox = QCheckBox(constants.SETTINGS_USE_SOURCEMETER_LABEL)
        sm_serial_label = QLabel(constants.SETTINGS_SOURCEMETER_SERIAL_LABEL)
        self.sm_serial_input = QLineEdit()
        self.sm_serial_input.setPlaceholderText("e.g., SERIAL_SM_456 or GPIB0::24::INSTR")
        self.sm_serial_input.setEnabled(False)
        instrument_layout.addWidget(self.sm_use_checkbox, 2, 0, 1, 2)
        instrument_layout.addWidget(sm_serial_label, 3, 0)
        instrument_layout.addWidget(self.sm_serial_input, 3, 1)

        self.chamber_use_checkbox = QCheckBox(constants.SETTINGS_USE_CHAMBER_LABEL)
        chamber_serial_label = QLabel(constants.SETTINGS_CHAMBER_SERIAL_LABEL)
        self.chamber_serial_input = QLineEdit()
        self.chamber_serial_input.setPlaceholderText("e.g., SERIAL_CH_789 (Optional)")
        self.chamber_serial_input.setEnabled(False)
        instrument_layout.addWidget(self.chamber_use_checkbox, 4, 0, 1, 2)
        instrument_layout.addWidget(chamber_serial_label, 5, 0)
        instrument_layout.addWidget(self.chamber_serial_input, 5, 1)

        self._main_layout.addWidget(instrument_group)

        # --- Execution Settings Group ---
        execution_group = QGroupBox("Execution Options")
        execution_layout = QVBoxLayout(execution_group)

        self.error_halts_sequence_checkbox = QCheckBox("오류 발생 시 시퀀스 자동 중단 (Halt sequence on error)")
        execution_layout.addWidget(self.error_halts_sequence_checkbox)
        
        self._main_layout.addWidget(execution_group)


        # --- Save Button ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton(constants.SETTINGS_SAVE_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance:
                app_style = app_instance.style()
                if app_style:
                    self.save_button.setIcon(app_style.standardIcon(QStyle.SP_DialogSaveButton))
                    self.save_button.setIconSize(QSize(16,16))
        except Exception as e:
            print(f"Warning: Could not set icon for save button in SettingsTab: {e}")

        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        self._main_layout.addLayout(button_layout)

        self._main_layout.addStretch(1)

    def _connect_signals(self):
        """UI 요소들의 시그널을 내부 슬롯이나 외부 시그널에 연결합니다."""
        if self.mm_use_checkbox and self.mm_serial_input:
            self.mm_use_checkbox.toggled.connect(self.mm_serial_input.setEnabled)
        if self.sm_use_checkbox and self.sm_serial_input:
            self.sm_use_checkbox.toggled.connect(self.sm_serial_input.setEnabled)
        if self.chamber_use_checkbox and self.chamber_serial_input:
            self.chamber_use_checkbox.toggled.connect(self.chamber_serial_input.setEnabled)

        if self.save_button:
            self.save_button.clicked.connect(self._on_save_button_clicked)
        
        if self.check_evb_button:
            self.check_evb_button.clicked.connect(self._check_evb_status_manually)

    def _on_save_button_clicked(self):
        """Save 버튼 클릭 시 현재 UI의 설정 값들을 모아 시그널을 발생시킵니다."""
        current_ui_settings = {
            "chip_id": self.chip_id_input.text().strip() if self.chip_id_input else "",
            "multimeter_use": self.mm_use_checkbox.isChecked() if self.mm_use_checkbox else False,
            "multimeter_serial": self.mm_serial_input.text().strip() if self.mm_serial_input else "",
            "sourcemeter_use": self.sm_use_checkbox.isChecked() if self.sm_use_checkbox else False,
            "sourcemeter_serial": self.sm_serial_input.text().strip() if self.sm_serial_input else "",
            "chamber_use": self.chamber_use_checkbox.isChecked() if self.chamber_use_checkbox else False,
            "chamber_serial": self.chamber_serial_input.text().strip() if self.chamber_serial_input else "",
            "error_halts_sequence": self.error_halts_sequence_checkbox.isChecked() if self.error_halts_sequence_checkbox else False
        }
        self.settings_changed_signal.emit(current_ui_settings)
        print("SettingsTab: settings_changed_signal emitted.")

    def populate_settings(self, settings_data: dict, i2c_device: Optional[I2CDevice] = None):
        """
        외부(RegMapWindow)로부터 받은 설정 데이터와 I2C 장치 인스턴스로 UI 요소들을 채웁니다.
        """
        if self.chip_id_input:
            self.chip_id_input.setText(settings_data.get('chip_id', ''))

        mm_use = settings_data.get('multimeter_use', False)
        if self.mm_use_checkbox: self.mm_use_checkbox.setChecked(mm_use)
        if self.mm_serial_input:
            self.mm_serial_input.setText(settings_data.get('multimeter_serial', ''))
            self.mm_serial_input.setEnabled(mm_use)

        sm_use = settings_data.get('sourcemeter_use', False)
        if self.sm_use_checkbox: self.sm_use_checkbox.setChecked(sm_use)
        if self.sm_serial_input:
            self.sm_serial_input.setText(settings_data.get('sourcemeter_serial', ''))
            self.sm_serial_input.setEnabled(sm_use)

        ch_use = settings_data.get('chamber_use', False)
        if self.chamber_use_checkbox: self.chamber_use_checkbox.setChecked(ch_use)
        if self.chamber_serial_input:
            self.chamber_serial_input.setText(settings_data.get('chamber_serial', ''))
            self.chamber_serial_input.setEnabled(ch_use)
        
        if self.error_halts_sequence_checkbox:
            self.error_halts_sequence_checkbox.setChecked(settings_data.get('error_halts_sequence', False))
        
        # EVB 상태 업데이트
        self.update_evb_status_display(i2c_device, settings_data.get('chip_id', ''))
            
        print("SettingsTab: UI populated with settings and EVB status updated.")

    def update_evb_status_display(self, i2c_device: Optional[I2CDevice], chip_id_from_settings: Optional[str]):
        """EVB 연결 상태 레이블을 업데이트합니다."""
        self._i2c_device_ref = i2c_device # 참조 저장
        
        if not self.evb_status_label:
            return

        if not chip_id_from_settings or not chip_id_from_settings.strip():
            self.evb_status_label.setText("<font color='orange'>칩 ID 미설정</font>")
            self.evb_status_label.setToolTip("설정에서 Chip ID를 입력해주세요.")
            return

        if self._i2c_device_ref and self._i2c_device_ref.is_opened:
            port_info = ""
            if hasattr(self._i2c_device_ref.evb_instance, 'port_name') and self._i2c_device_ref.evb_instance.port_name:
                 port_info = f" (Port: {self._i2c_device_ref.evb_instance.port_name})"
            elif hasattr(self._i2c_device_ref.evb_instance, 'device_path') and self._i2c_device_ref.evb_instance.device_path: # 일부 EVB 라이브러리 속성
                 port_info = f" (Path: {self._i2c_device_ref.evb_instance.device_path})"

            self.evb_status_label.setText(f"<font color='green'>연결됨 (ID: {chip_id_from_settings}){port_info}</font>")
            self.evb_status_label.setToolTip(f"EVB가 Chip ID {chip_id_from_settings}로 연결되었습니다.{port_info}")
        elif self._i2c_device_ref and not self._i2c_device_ref.is_opened and self._i2c_device_ref.chip_id != 0 : # 초기화 시도했으나 실패
            self.evb_status_label.setText(f"<font color='red'>연결 실패 (ID: {chip_id_from_settings})</font>")
            self.evb_status_label.setToolTip("EVB 연결에 실패했습니다. 장치 연결 상태 및 Chip ID를 확인하세요.")
        else: # i2c_device가 None이거나, chip_id가 설정되었지만 아직 초기화 시도 전일 수 있음
            self.evb_status_label.setText("<font color='orange'>연결 안됨 / 확인 필요</font>")
            self.evb_status_label.setToolTip("EVB 연결 상태를 확인하려면 'EVB 연결 확인' 버튼을 누르거나 설정을 저장하세요.")

    @pyqtSlot()
    def _check_evb_status_manually(self):
        """'EVB 연결 확인' 버튼 클릭 시 호출됩니다."""
        print("SettingsTab: Manual EVB status check requested.")
        # RegMapWindow에 EVB 재초기화 및 상태 업데이트 요청
        # 가장 간단한 방법은 settings_changed_signal을 현재 설정 그대로 다시 발생시키는 것.
        # 그러면 RegMapWindow의 _handle_settings_changed -> _initialize_hardware_from_settings ->
        # populate_settings(..., self.i2c_device) 경로를 통해 상태가 업데이트됨.
        if self.chip_id_input and self.mm_use_checkbox and self.sm_use_checkbox and self.chamber_use_checkbox and self.error_halts_sequence_checkbox:
            current_ui_settings = {
                "chip_id": self.chip_id_input.text().strip(),
                "multimeter_use": self.mm_use_checkbox.isChecked(),
                "multimeter_serial": self.mm_serial_input.text().strip() if self.mm_serial_input else "",
                "sourcemeter_use": self.sm_use_checkbox.isChecked(),
                "sourcemeter_serial": self.sm_serial_input.text().strip() if self.sm_serial_input else "",
                "chamber_use": self.chamber_use_checkbox.isChecked(),
                "chamber_serial": self.chamber_serial_input.text().strip() if self.chamber_serial_input else "",
                "error_halts_sequence": self.error_halts_sequence_checkbox.isChecked()
            }
            # 설정을 실제로 변경하지 않고 상태만 업데이트하기 위해,
            # RegMapWindow에 직접 요청하는 메서드를 두는 것이 더 깔끔할 수 있습니다.
            # 여기서는 일단 settings_changed_signal을 통해 간접적으로 업데이트를 유도합니다.
            # (주의: 이 방식은 설정을 "저장"하는 효과도 가집니다.)
            # 더 나은 방법: RegMapWindow에 EVB 상태만 새로고침하는 슬롯을 만들고, SettingsTab에서 해당 슬롯을 호출.
            # 여기서는 일단 현재 구조에서 가장 간단한 방법으로 진행.
            
            # 메인 윈도우 참조를 통해 직접 하드웨어 재초기화 및 UI 업데이트 요청
            parent_window = self.window()
            if parent_window and hasattr(parent_window, '_initialize_hardware_from_settings') and hasattr(parent_window, 'current_settings'):
                print("SettingsTab: Requesting hardware re-initialization via parent window.")
                # 현재 UI의 chip_id를 main_window의 current_settings에 반영 후 재초기화
                parent_window.current_settings['chip_id'] = self.chip_id_input.text().strip() if self.chip_id_input else ""
                parent_window._initialize_hardware_from_settings() # 하드웨어 재초기화
                self.update_evb_status_display(parent_window.i2c_device, parent_window.current_settings.get('chip_id')) # 상태 표시 업데이트
                QMessageBox.information(self, "EVB 상태 확인", "EVB 연결 상태를 다시 확인했습니다.")
            else:
                QMessageBox.warning(self, "오류", "EVB 상태를 직접 확인할 수 없습니다. 설정을 저장하여 상태를 갱신하세요.")
        else:
            QMessageBox.warning(self, "오류", "UI 요소가 아직 준비되지 않았습니다.")


# --- 이 모듈을 직접 실행하여 테스트하기 위한 코드 ---
if __name__ == '__main__':
    import sys
    
    # 테스트를 위해 core.constants를 직접 참조하도록 가정
    try:
        from core import constants as test_constants_module
    except ImportError:
        class MockCoreConstants: # 테스트용 Mock
            SETTINGS_CHIP_ID_LABEL = "Chip ID (Hex) (Mock):"
            SETTINGS_USE_MULTIMETER_LABEL = "Use Multimeter (Mock)"
            SETTINGS_MULTIMETER_SERIAL_LABEL = "Multimeter Serial (Mock):"
            SETTINGS_USE_SOURCEMETER_LABEL = "Use Sourcemeter (Mock)"
            SETTINGS_SOURCEMETER_SERIAL_LABEL = "Sourcemeter Serial (Mock):"
            SETTINGS_USE_CHAMBER_LABEL = "Use Chamber (Mock)"
            SETTINGS_CHAMBER_SERIAL_LABEL = "Chamber Serial (Mock):"
            SETTINGS_SAVE_BUTTON_TEXT = "Save Settings (Mock)"
        constants = MockCoreConstants()

    app = QApplication(sys.argv)

    # Mock I2CDevice for testing
    class MockI2CDevice:
        def __init__(self, chip_id_str=""):
            self.chip_id_str = chip_id_str
            self.is_opened = False
            self.chip_id = 0
            self.evb_instance = None
            if chip_id_str:
                try:
                    self.chip_id = int(chip_id_str, 16) if chip_id_str.startswith("0x") else int(chip_id_str)
                    if self.chip_id_str == "0x18" or self.chip_id_str == "24": # 특정 ID만 연결 성공 가정
                        self.is_opened = True
                        self.evb_instance = type('obj', (object,), {'port_name': 'COM_TEST'})() # Mock evb_instance
                        print(f"MockI2CDevice: Opened for {chip_id_str}")
                    else:
                        print(f"MockI2CDevice: Failed to open for {chip_id_str}")
                except ValueError:
                    print(f"MockI2CDevice: Invalid chip_id {chip_id_str}")
        def close(self):
            self.is_opened = False
            print(f"MockI2CDevice: Closed for {self.chip_id_str}")

    # Mock RegMapWindow for testing SettingsTab in isolation
    class MockRegMapWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.i2c_device: Optional[I2CDevice] = None
            self.current_settings = { # 초기 current_settings 모의
                "chip_id": "0x18", # 초기값
                 # ... 기타 설정들
            } 
            self.settings_tab = SettingsTab(self)
            self.setCentralWidget(self.settings_tab)
            self.setWindowTitle("SettingsTab Test with Mock Window")
            self.setGeometry(300, 300, 500, 450)
            
            # 초기 EVB 상태 반영
            self._initialize_hardware_from_settings() # RegMapWindow의 메서드 호출 모방
            self.settings_tab.populate_settings(self.current_settings, self.i2c_device)
            
            # SettingsTab의 시그널 연결
            self.settings_tab.settings_changed_signal.connect(self._handle_settings_changed_mock)

        @pyqtSlot(dict)
        def _handle_settings_changed_mock(self, new_settings: dict):
            print("MockRegMapWindow: Settings changed signal received.")
            self.current_settings.update(new_settings)
            # 실제라면 여기서 settings_manager.save_settings 호출
            print(f"MockRegMapWindow: Current settings updated to: {self.current_settings}")
            self._initialize_hardware_from_settings() # 하드웨어 재초기화
            # populate_settings를 다시 호출하여 EVB 상태 포함 UI 업데이트
            self.settings_tab.populate_settings(self.current_settings, self.i2c_device) 


        def _initialize_hardware_from_settings(self): # RegMapWindow의 메서드 모방
            print("MockRegMapWindow: Initializing hardware...")
            if self.i2c_device:
                self.i2c_device.close()
            
            chip_id = self.current_settings.get("chip_id")
            if chip_id:
                self.i2c_device = MockI2CDevice(chip_id_str=chip_id)
            else:
                self.i2c_device = None
            print(f"MockRegMapWindow: i2c_device is now: {self.i2c_device} (Opened: {self.i2c_device.is_opened if self.i2c_device else 'N/A'})")


    # 테스트 실행
    mock_window = MockRegMapWindow()
    mock_window.show()
    
    sys.exit(app.exec_())