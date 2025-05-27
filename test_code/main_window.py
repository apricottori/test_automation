# main_window.py
import sys
import os
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget, QLabel, QMessageBox,
    QStyle, QLineEdit, QSizePolicy, QStyleFactory # QSizePolicy, QStyleFactory 추가
)
from PyQt5.QtCore import Qt, QSize, QStringListModel, pyqtSlot
from PyQt5.QtGui import QFont, QIcon

from core import constants
from core.register_map_backend import RegisterMap
from core.settings_manager import SettingsManager
from core.hardware_control import I2CDevice, Multimeter, Sourcemeter, Chamber
from core.results_manager import ResultsManager
from ui.tabs.settings_tab import SettingsTab
from ui.tabs.reg_viewer_tab import RegisterViewerTab
from ui.tabs.results_viewer_tab import ResultsViewerTab
from ui.tabs.sequence_controller_tab import SequenceControllerTab
from core.excel_exporter import ExcelExporter

import pandas as pd

class RegMapWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- 1. 비 UI 멤버 변수 및 핵심 매니저 객체 초기화 ---
        try:
            # SettingsManager는 config_file_path 인자 없이 생성 (사용자 제공 원본 기준)
            # 이는 settings_manager.py의 __init__이 config_file_path를 Optional로 받거나,
            # config_file_name만으로 내부 경로를 결정해야 함을 의미합니다.
            self.settings_manager = SettingsManager()
            self.results_manager = ResultsManager()
            self.register_map = RegisterMap()
            self.completer_model = QStringListModel()

            self.current_settings: Dict[str, Any] = {}
            self.i2c_device: Optional[I2CDevice] = None
            self.multimeter: Optional[Multimeter] = None
            self.sourcemeter: Optional[Sourcemeter] = None
            self.chamber: Optional[Chamber] = None
            self.current_json_file: Optional[str] = None # 사용자 제공 파일의 변수명

            # --- 2. UI 멤버 변수 None으로 명시적 선언 ---
            self.central_widget: Optional[QWidget] = None
            self.main_layout: Optional[QVBoxLayout] = None
            self.sample_number_input: Optional[QLineEdit] = None
            self.load_json_button: Optional[QPushButton] = None
            self.current_file_label: Optional[QLabel] = None # 사용자 제공 파일의 변수명
            self.tabs: Optional[QTabWidget] = None
            self.tab_settings_widget: Optional[SettingsTab] = None
            self.tab_reg_viewer_widget: Optional[RegisterViewerTab] = None
            self.tab_sequence_controller_widget: Optional[SequenceControllerTab] = None
            self.tab_results_viewer_widget: Optional[ResultsViewerTab] = None

        except Exception as e:
            print(f"FATAL ERROR during RegMapWindow non-UI member initialization: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            # QApplication 인스턴스가 존재할 때만 QMessageBox 사용
            app_instance = QApplication.instance()
            if app_instance:
                 QMessageBox.critical(self, "애플리케이션 초기화 오류",
                                     f"윈도우 내부 데이터 초기화 중 치명적 오류:\n{e}\n\n프로그램을 종료합니다.")
                 app_instance.quit()
            else:
                # QApplication이 아직 생성되지 않았거나 접근 불가능한 매우 예외적인 상황
                print("CRITICAL: QApplication instance not found during non-UI member init error handling.")
            sys.exit(1) # 프로그램 종료

        # --- 3. UI 생성 및 배치 ---
        try:
            self.setWindowTitle(constants.WINDOW_TITLE)
            self.setGeometry(100, 100,
                             constants.INITIAL_WINDOW_WIDTH,
                             constants.INITIAL_WINDOW_HEIGHT)
            self._apply_styles() # 사용자 제공 파일에 있는 메소드 호출
            print("DEBUG: _apply_styles() finished.")

            self.central_widget = QWidget(self)
            self.setCentralWidget(self.central_widget)
            print(f"DEBUG: central_widget created: {self.central_widget}")

            self.main_layout = QVBoxLayout() # 사용자 제공 파일 방식: QVBoxLayout() 후 setLayout
            if self.central_widget:
                self.central_widget.setLayout(self.main_layout)
            else:
                raise RuntimeError("Central widget is None after creation, cannot set layout.")
            print(f"DEBUG: main_layout created and set on central_widget: {self.main_layout}")

            if self.main_layout is None:
                raise RuntimeError("main_layout is explicitly None after QVBoxLayout() and setLayout().")

            self.main_layout.setContentsMargins(10, 10, 10, 10) # 사용자 제공 파일의 값
            self.main_layout.setSpacing(10) # 사용자 제공 파일의 값

            self._create_file_selection_area()
            print("DEBUG: _create_file_selection_area() finished.")

            self._create_and_integrate_tabs()
            print("DEBUG: _create_and_integrate_tabs() finished.")

        except Exception as e:
            print(f"FATAL ERROR during RegMapWindow UI setup: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            if self.central_widget:
                QMessageBox.critical(self, "애플리케이션 UI 오류",
                                     f"UI 생성 중 심각한 오류가 발생했습니다:\n{e}\n\n프로그램을 종료합니다.")
            app_instance = QApplication.instance()
            if app_instance:
                app_instance.quit()
            sys.exit(1)

        # --- 4. 애플리케이션 설정 로드 및 적용 (UI가 준비된 후에 호출) ---
        try:
            self._load_app_settings()
            print("DEBUG: _load_app_settings() finished.")
        except Exception as e:
            print(f"ERROR during _load_app_settings: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "설정 로드 오류", f"애플리케이션 설정 로드 중 오류:\n{e}")

        # --- 5. 설정 로드 후 UI 최종 업데이트 ---
        try:
            if self.tab_results_viewer_widget:
                excel_conf = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
                if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                    self.tab_results_viewer_widget.set_excel_export_config(excel_conf)

            if self.statusBar(): # statusBar()가 None이 아닐 때만 호출
                self.statusBar().showMessage("애플리케이션 준비 완료.")
            print("DEBUG: RegMapWindow __init__ completed successfully.")
        except Exception as e:
            print(f"ERROR during final UI update: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "UI 업데이트 오류", f"최종 UI 업데이트 중 오류:\n{e}")

    def _apply_styles(self):
        """애플리케이션의 기본 스타일시트를 적용합니다."""
        # 사용자 제공 파일의 스타일 적용 로직 유지
        app_font_family = getattr(constants, 'APP_FONT', '맑은 고딕')
        if sys.platform == "darwin":
            app_font_family = getattr(constants, 'APP_FONT_MACOS', 'Apple SD Gothic Neo')
        elif "linux" in sys.platform:
            app_font_family = getattr(constants, 'APP_FONT_LINUX', 'Noto Sans KR')
        app_font_size = getattr(constants, 'APP_FONT_SIZE', 14) # 사용자 제공 파일은 14pt
        base_style = f"""
            QMainWindow, QWidget {{
                font-family: '{app_font_family}', 'Arial', sans-serif; font-size: {app_font_size}pt;
                background-color: {getattr(constants, 'COLOR_BACKGROUND_MAIN', '#ECEFF1')};
                color: {getattr(constants, 'COLOR_TEXT_DARK', '#263238')};
            }}
            QTabWidget::pane {{
                border: 1px solid {getattr(constants, 'COLOR_BORDER_LIGHT', '#B0BEC5')};
                background: {getattr(constants, 'COLOR_BACKGROUND_LIGHT', '#FFFFFF')};
                border-radius: {getattr(constants, 'BORDER_RADIUS_WIDGET', 4)}px;
            }}
            QTabBar::tab {{
                background: {getattr(constants, 'COLOR_BACKGROUND_TAB_INACTIVE', '#B0BEC5')};
                border: 1px solid {getattr(constants, 'COLOR_BORDER_LIGHT', '#B0BEC5')}; border-bottom: none;
                padding: {getattr(constants, 'PADDING_TAB_Y', 8)}px {getattr(constants, 'PADDING_TAB_X', 15)}px;
                margin-right: 1px; border-top-left-radius: {getattr(constants, 'BORDER_RADIUS_TAB', 3)}px;
                border-top-right-radius: {getattr(constants, 'BORDER_RADIUS_TAB', 3)}px;
                color: {getattr(constants, 'COLOR_TEXT_MUTED', '#546E7A')};
                min-width: {getattr(constants, 'TAB_MIN_WIDTH_EX', 20)}ex; font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {getattr(constants, 'COLOR_BACKGROUND_LIGHT', '#FFFFFF')};
                color: {getattr(constants, 'COLOR_TEXT_DARK', '#263238')};
            }}
            QTabBar::tab:hover {{ background: {getattr(constants, 'COLOR_BACKGROUND_TAB_HOVER', '#CFD8DC')}; }}
            QPushButton {{
                background-color: {getattr(constants, 'COLOR_BUTTON_NORMAL_BG', '#0288D1')};
                border: 1px solid {getattr(constants, 'COLOR_BUTTON_NORMAL_BORDER', '#0277BD')};
                padding: {getattr(constants, 'PADDING_BUTTON_Y', 7)}px {getattr(constants, 'PADDING_BUTTON_X', 15)}px;
                border-radius: {getattr(constants, 'BORDER_RADIUS_BUTTON', 4)}px;
                color: {getattr(constants, 'COLOR_BUTTON_TEXT', '#FFFFFF')};
                min-height: {getattr(constants, 'BUTTON_MIN_HEIGHT', 30)}px;
            }}
            QPushButton:hover {{
                background-color: {getattr(constants, 'COLOR_BUTTON_HOVER_BG', '#0277BD')};
                border-color: {getattr(constants, 'COLOR_BUTTON_HOVER_BORDER', '#01579B')};
            }}
            QPushButton:pressed {{ background-color: {getattr(constants, 'COLOR_BUTTON_PRESSED_BG', '#01579B')}; }}
            QPushButton:disabled {{
                background-color: {getattr(constants, 'COLOR_BUTTON_DISABLED_BG', '#CFD8DC')};
                border-color: {getattr(constants, 'COLOR_BUTTON_DISABLED_BORDER', '#BDBDBD')};
                color: {getattr(constants, 'COLOR_BUTTON_DISABLED_TEXT', '#78909C')};
            }}
            QPushButton#loadJsonButton {{
                padding: {getattr(constants, 'LOAD_JSON_BUTTON_PADDING_Y', 4)}px {getattr(constants, 'LOAD_JSON_BUTTON_PADDING_X', 10)}px;
                min-height: {getattr(constants, 'LOAD_JSON_BUTTON_MIN_HEIGHT', 24)}px;
                background-color: #E0E0E0; color: #333333; border: 1px solid #BDBDBD;
            }}
            QPushButton#loadJsonButton:hover {{ background-color: #D0D0D0; border-color: #AAAAAA; }}
            QPushButton#loadJsonButton:pressed {{ background-color: #C0C0C0; }}
            QLineEdit, QComboBox, QListWidget, QTextEdit, QTableWidget, QDoubleSpinBox, QSpinBox {{
                border: 1px solid {getattr(constants, 'COLOR_BORDER_INPUT', '#90A4AE')};
                border-radius: {getattr(constants, 'BORDER_RADIUS_INPUT', 3)}px;
                padding: {getattr(constants, 'PADDING_INPUT', 5)}px;
                background-color: {getattr(constants, 'COLOR_BACKGROUND_INPUT', '#FFFFFF')};
                color: {getattr(constants, 'COLOR_TEXT_INPUT', '#000000')};
            }}
            QTableWidget {{
                gridline-color: {getattr(constants, 'COLOR_GRIDLINE', '#CFD8DC')};
                selection-background-color: {getattr(constants, 'COLOR_SELECTION_BACKGROUND', '#0288D1')};
                selection-color: {getattr(constants, 'COLOR_SELECTION_TEXT', '#FFFFFF')};
            }}
            QHeaderView::section {{
                background-color: {getattr(constants, 'COLOR_HEADER_BACKGROUND', '#E0E0E0')};
                padding: {getattr(constants, 'PADDING_HEADER', 5)}px;
                border: 1px solid {getattr(constants, 'COLOR_BORDER_HEADER', '#9E9E9E')};
                font-weight: bold; color: {getattr(constants, 'COLOR_TEXT_HEADER', '#000000')};
            }}
            QLabel {{ padding-bottom: 3px; }}
            QListWidget::item {{ padding: 4px; }}
            QListWidget::item:selected {{
                background-color: {getattr(constants, 'COLOR_SELECTION_BACKGROUND', '#0288D1')};
                color: {getattr(constants, 'COLOR_SELECTION_TEXT', '#FFFFFF')};
            }}
            QMessageBox {{ font-size: {app_font_size - 2}pt; }}
            QCompleter QAbstractItemView {{
                border: 1px solid {getattr(constants, 'COLOR_BORDER_INPUT', '#90A4AE')};
                background-color: {getattr(constants, 'COLOR_BACKGROUND_INPUT', '#FFFFFF')};
                color: {getattr(constants, 'COLOR_TEXT_INPUT', '#000000')};
                selection-background-color: {getattr(constants, 'COLOR_SELECTION_BACKGROUND', '#0288D1')};
                selection-color: {getattr(constants, 'COLOR_SELECTION_TEXT', '#FFFFFF')};
            }}
            QStackedWidget {{ background-color: transparent; }}
            QGroupBox {{
                font-weight: bold; border: 1px solid {getattr(constants, 'COLOR_BORDER_LIGHT', '#B0BEC5')};
                border-radius: {getattr(constants, 'BORDER_RADIUS_WIDGET', 4)}px; margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 5px 0 5px; left: 10px;
            }}
        """
        self.setStyleSheet(base_style)

    def _load_app_settings(self):
        """애플리케이션 설정을 로드하고, 하드웨어를 초기화하며, 관련 UI를 업데이트합니다."""
        # settings_manager가 None일 경우를 대비 (사용자 제공 코드에는 이 체크 없음)
        if self.settings_manager is None:
            print("ERROR_MW: SettingsManager is not initialized. Cannot load settings.")
            self.current_settings = {} # 빈 설정으로 초기화
            # 필요하다면 여기서 기본값으로 SettingsManager를 다시 생성 시도할 수 있음
            # self.settings_manager = SettingsManager() # 이 경우 config_file_path를 전달하지 않음
            # return # 또는 여기서 함수를 종료
        else:
            loaded_settings = self.settings_manager.load_settings()
            self.current_settings.update(loaded_settings) # 사용자 제공 코드 방식: update 사용

        self._initialize_hardware_from_settings() # 하드웨어 초기화 먼저 수행

        last_json_path = self.current_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY)
        if last_json_path and os.path.exists(last_json_path):
            self._process_loaded_json(last_json_path, auto_loaded=True)
        elif last_json_path:
            if self.statusBar(): self.statusBar().showMessage(f"자동 로드 실패: '{last_json_path}' 파일을 찾을 수 없습니다.", 5000)

        if self.tab_settings_widget:
            # SettingsTab에 populate_settings 메소드가 있다고 가정 (사용자 제공 코드에 호출 있음)
            if hasattr(self.tab_settings_widget, 'populate_settings'):
                self.tab_settings_widget.populate_settings(self.current_settings, self.i2c_device)
            else:
                # populate_settings가 없다면, SettingsTab의 load_settings를 직접 호출할 수 있음
                # 단, 이 경우 i2c_device를 전달하는 방식이 다를 수 있음
                if hasattr(self.tab_settings_widget, 'load_settings'):
                    self.tab_settings_widget.load_settings()
                if hasattr(self.tab_settings_widget, 'update_evb_status'): # EVB 상태 별도 업데이트 / 이름 수정
                    chip_id_to_display = self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, "N/A")
                    # Ensure chip_id_to_display is suitable for direct display or convert if necessary
                    status_msg_detail = chip_id_to_display
                    if self.i2c_device and self.i2c_device.is_opened and hasattr(self.i2c_device, 'chip_id') and self.i2c_device.chip_id:
                        # If connected, use the actual chip_id from the device, which should be an int
                        try:
                            if isinstance(self.i2c_device.chip_id, int):
                                status_msg_detail = f"ID: {self.i2c_device.chip_id:#04X} (connected)"
                            else:
                                status_msg_detail = f"ID: {self.i2c_device.chip_id} (connected, format error)"
                        except (TypeError, ValueError):
                            status_msg_detail = f"ID: {self.i2c_device.chip_id} (connected, format error)"
                        self.tab_settings_widget.update_evb_status(self.i2c_device is not None and self.i2c_device.is_opened, status_msg_detail)
                    elif chip_id_to_display:
                        # Don't try to format a string with hex format code
                        if isinstance(chip_id_to_display, int):
                            status_msg_detail = f"ID: {chip_id_to_display:#04X} (from settings)"
                        else:
                            status_msg_detail = f"ID: {chip_id_to_display} (from settings)"
                        self.tab_settings_widget.update_evb_status(self.i2c_device is not None and self.i2c_device.is_opened, status_msg_detail)


    def _clear_hardware_instances(self):
        """모든 하드웨어 인스턴스를 안전하게 닫고 None으로 설정합니다."""
        # 사용자 제공 코드의 로직 유지
        if self.i2c_device: self.i2c_device.close(); self.i2c_device = None
        if self.multimeter: self.multimeter.disconnect(); self.multimeter = None
        if self.sourcemeter: self.sourcemeter.disconnect(); self.sourcemeter = None
        if self.chamber:
            if hasattr(self.chamber, 'is_connected') and self.chamber.is_connected:
                if hasattr(self.chamber, 'stop_operation'): self.chamber.stop_operation()
                if hasattr(self.chamber, 'power_off'): self.chamber.power_off() # 사용자 제공 코드의 메소드
            if hasattr(self.chamber, 'disconnect'): self.chamber.disconnect()
            self.chamber = None
        print("DEBUG: Hardware instances cleared.")

    def _init_i2c_device(self):
        """I2C 장치를 설정값에 따라 초기화합니다."""
        chip_id_str_to_use = ""
        # SettingsTab UI의 현재 Chip ID 값을 우선적으로 사용
        if self.tab_settings_widget and hasattr(self.tab_settings_widget, 'chip_id_input') and self.tab_settings_widget.chip_id_input:
            chip_id_str_to_use = self.tab_settings_widget.chip_id_input.text().strip()
            if chip_id_str_to_use:
                print(f"DEBUG_MW: Using Chip ID from SettingsTab UI for _init_i2c_device: '{chip_id_str_to_use}'")

        # UI에서 가져온 Chip ID가 없으면 저장된 설정에서 가져옴
        if not chip_id_str_to_use:
            chip_id_str_to_use = self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, "")
            if chip_id_str_to_use:
                print(f"DEBUG_MW: Using Chip ID from saved current_settings for _init_i2c_device: '{chip_id_str_to_use}'")

        if chip_id_str_to_use:
            self.i2c_device = I2CDevice(chip_id_str=chip_id_str_to_use) # 새 인스턴스 생성
            if self.i2c_device and self.i2c_device.is_opened:
                print(f"DEBUG_MW: I2C device initialized and opened successfully with ID: {chip_id_str_to_use}")
                # change_port는 필요시 호출. 여기서는 EVB 연결 확인이 주 목적.
                # if hasattr(self.i2c_device, 'change_port'):
                #     if not self.i2c_device.change_port(0):
                #          print("Warning: I2C 포트 변경(0) 실패.")
            elif self.i2c_device and not self.i2c_device.is_opened:
                QMessageBox.warning(self, constants.MSG_TITLE_ERROR, f"I2C 장치(ID: {chip_id_str_to_use}) 연결 실패. EVB 상태를 확인하세요.")
                self.i2c_device = None # 연결 실패 시 명확히 None으로 설정
            elif not self.i2c_device: # I2CDevice 생성자에서 문제가 발생하여 None이 반환된 경우 (드문 경우)
                 QMessageBox.warning(self, constants.MSG_TITLE_ERROR, f"I2C 장치(ID: {chip_id_str_to_use}) 초기화 중 객체 생성 실패.")
                 self.i2c_device = None # 초기화 실패 시 명확히 None으로 설정
        else:
            print("Info_MW: Chip ID가 설정되지 않아 I2C 장치를 초기화하지 않습니다.")
            self.i2c_device = None # Chip ID 없으면 명확히 None으로 설정
            # 사용자에게 Chip ID가 없음을 알릴 수 있습니다.
            # QMessageBox.information(self, "알림", "Chip ID가 설정되지 않았습니다. Settings 탭에서 설정해주세요.")

    def _init_multimeter(self):
        """멀티미터를 설정값에 따라 초기화합니다."""
        # 사용자 제공 코드의 로직 유지 (키 이름 'multimeter_serial' 사용)
        if self.current_settings.get('multimeter_use'): # 키 직접 사용
            serial_num = self.current_settings.get('multimeter_serial')
            if serial_num:
                self.multimeter = Multimeter(serial_number_str=serial_num) # serial_number_str 사용
                if not self.multimeter.connect():
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Multimeter", serial_number=serial_num))
                    self.multimeter = None
            else:
                self.current_settings['multimeter_use'] = False
                print("Warning: Multimeter 시리얼 번호가 없어 사용할 수 없습니다. 설정에서 비활성화합니다.")
        else:
            self.multimeter = None

    def _init_sourcemeter(self):
        """소스미터를 설정값에 따라 초기화합니다."""
        # 사용자 제공 코드의 로직 유지 (키 이름 'sourcemeter_serial' 사용)
        if self.current_settings.get('sourcemeter_use'): # 키 직접 사용
            serial_num = self.current_settings.get('sourcemeter_serial')
            if serial_num:
                self.sourcemeter = Sourcemeter(serial_number_str=serial_num) # serial_number_str 사용
                if not self.sourcemeter.connect():
                     QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Sourcemeter", serial_number=serial_num))
                     self.sourcemeter = None
            else:
                self.current_settings['sourcemeter_use'] = False
                print("Warning: Sourcemeter 시리얼 번호가 없어 사용할 수 없습니다. 설정에서 비활성화합니다.")
        else:
            self.sourcemeter = None

    def _init_chamber(self):
        """챔버를 설정값에 따라 초기화합니다."""
        # 사용자 제공 코드의 로직 유지 (키 이름 'chamber_serial' 사용)
        if self.current_settings.get('chamber_use'): # 키 직접 사용
            serial_num = self.current_settings.get('chamber_serial')
            self.chamber = Chamber(serial_number_str=serial_num if serial_num else None) # serial_number_str 사용
            if not self.chamber.connect():
                 QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                    constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Chamber", serial_number=serial_num if serial_num else "N/A"))
        else:
            self.chamber = None

    def _initialize_hardware_from_settings(self): # 사용자 제공 코드에는 인자 없음
        """설정값을 기반으로 하드웨어 장치들을 (재)초기화합니다."""
        self._clear_hardware_instances()

        self._init_i2c_device()
        self._init_multimeter()
        self._init_sourcemeter()
        self._init_chamber()

        if self.tab_sequence_controller_widget:
            if hasattr(self.tab_sequence_controller_widget, 'update_hardware_instances'):
                self.tab_sequence_controller_widget.update_hardware_instances(
                    self.i2c_device, self.multimeter, self.sourcemeter, self.chamber
                )
        
        if self.tab_settings_widget and hasattr(self.tab_settings_widget, 'update_evb_status'): # 이름 수정
             message_detail = "Unknown" 
             if self.i2c_device and self.i2c_device.is_opened and hasattr(self.i2c_device, 'chip_id') and self.i2c_device.chip_id:
                 message_detail = f"ID: {self.i2c_device.chip_id:#04X}"
             elif self.tab_settings_widget and hasattr(self.tab_settings_widget, 'chip_id_input') and self.tab_settings_widget.chip_id_input: # SettingsTab의 chip_id_input이 public이라고 가정
                 chip_id_ui = self.tab_settings_widget.chip_id_input.text().strip()
                 if chip_id_ui : message_detail = f"Attempted ID: {chip_id_ui}"
                 elif self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY):
                      message_detail = f"Attempted ID from settings: {self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY)}"
             elif self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY):
                 message_detail = f"Attempted ID from settings: {self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY)}"
             
             self.tab_settings_widget.update_evb_status(self.i2c_device is not None and self.i2c_device.is_opened, message_detail)
        print("DEBUG: Hardware initialization from settings completed.")

    def _create_file_selection_area(self):
        """JSON 파일 선택 및 샘플 번호 입력 UI를 생성하고 멤버 변수에 할당합니다."""
        if self.main_layout is None:
            QMessageBox.critical(self, "UI 초기화 오류", "파일 선택 영역 UI 생성 실패 (main_layout is None).")
            raise RuntimeError("Cannot create file selection area: main_layout is None.")

        file_button_layout = QHBoxLayout()

        sample_label = QLabel(constants.SAMPLE_NUMBER_LABEL) # 사용자 제공 코드 순서
        self.sample_number_input = QLineEdit()
        if self.sample_number_input: # None 체크 추가
            self.sample_number_input.setPlaceholderText("e.g., SN001")
            self.sample_number_input.setFixedWidth(150) # 사용자 제공 코드의 값
            self.sample_number_input.setText(constants.DEFAULT_SAMPLE_NUMBER) # 사용자 제공 코드의 값

        file_button_layout.addWidget(sample_label)
        file_button_layout.addWidget(self.sample_number_input)
        file_button_layout.addSpacing(20) # 사용자 제공 코드의 값

        self.load_json_button = QPushButton() # 사용자 제공 코드: 아이콘/텍스트 설정은 이후
        self.load_json_button.setObjectName("loadJsonButton") # 사용자 제공 코드의 ID
        try:
            app_instance = QApplication.instance()
            if app_instance:
                 # 사용자 제공 코드에는 QStyle.SP_DialogOpenButton 사용
                 self.load_json_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogOpenButton))
            else:
                 if self.load_json_button: self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)
        except Exception as e:
            print(f"Warning: Could not set icon for load_json_button: {e}")
            if self.load_json_button: self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)

        if self.load_json_button and self.load_json_button.icon().isNull() and not self.load_json_button.text():
            self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)
        
        if self.load_json_button:
            self.load_json_button.setIconSize(QSize(16,16))
            self.load_json_button.setToolTip(constants.LOAD_JSON_TOOLTIP)
            self.load_json_button.clicked.connect(self.load_json_file_dialog) # 사용자 제공 코드의 메소드명
            file_button_layout.addWidget(self.load_json_button)

        self.current_file_label = QLabel(constants.NO_FILE_LOADED_LABEL) # 사용자 제공 코드의 변수명
        color_text_muted = getattr(constants, 'COLOR_TEXT_MUTED', '#777777')
        if self.current_file_label: # None 체크 추가
            self.current_file_label.setStyleSheet(f"QLabel {{ padding: 5px; font-style: italic; color: {color_text_muted}; }}")
        file_button_layout.addWidget(self.current_file_label)
        
        file_button_layout.addStretch()
        self.main_layout.addLayout(file_button_layout)

    def _create_and_integrate_tabs(self):
        """메인 기능 탭들을 생성하고 QTabWidget에 통합하며 멤버 변수에 할당합니다."""
        if self.main_layout is None:
            QMessageBox.critical(self, "UI 초기화 오류", "탭 UI 생성 실패 (main_layout is None).")
            raise RuntimeError("Cannot create tabs: main_layout is None.")

        self.tabs = QTabWidget()

        # Settings Tab
        # SettingsManager 인스턴스 전달 및 main_window_ref 추가
        self.tab_settings_widget = SettingsTab(
            settings_manager_instance=self.settings_manager, # 수정된 부분
            parent=self,
            main_window_ref=self # 추가된 부분 (SettingsTab이 이를 받는다고 가정)
        )
        if self.tab_settings_widget:
            self.tab_settings_widget.settings_changed_signal.connect(self._handle_settings_changed)
            if hasattr(self.tab_settings_widget, 'check_evb_connection_requested'): # Corrected signal name here
                self.tab_settings_widget.check_evb_connection_requested.connect(self._handle_evb_check_request)
            if hasattr(self.tab_settings_widget, 'reinitialize_hardware_requested'):
                 self.tab_settings_widget.reinitialize_hardware_requested.connect(self._initialize_hardware_from_settings)
            # Connect the new signal
            if hasattr(self.tab_settings_widget, 'instrument_enable_changed_signal'):
                self.tab_settings_widget.instrument_enable_changed_signal.connect(self._handle_instrument_enable_changed)

            self.tabs.addTab(self.tab_settings_widget, constants.TAB_SETTINGS_TITLE)
        
        # Register Viewer Tab
        self.tab_reg_viewer_widget = RegisterViewerTab(parent=self) # 사용자 제공 코드: register_map_instance 나중에 전달
        if self.tab_reg_viewer_widget:
            self.tabs.addTab(self.tab_reg_viewer_widget, constants.TAB_REG_VIEWER_TITLE)
            if self.tabs.indexOf(self.tab_reg_viewer_widget) != -1:
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False) 

        # Sequence Controller Tab
        try:
            self.tab_sequence_controller_widget = SequenceControllerTab(
                parent=self,
                register_map_instance=self.register_map,
                settings_instance=self.current_settings,
                completer_model_instance=self.completer_model,
                i2c_device_instance=self.i2c_device,
                multimeter_instance=self.multimeter,
                sourcemeter_instance=self.sourcemeter,
                chamber_instance=self.chamber,
                main_window_ref=self
            )
        except Exception as e_seq_tab:
            self.tab_sequence_controller_widget = None
            error_msg = f"CRITICAL ERROR instantiating SequenceControllerTab: {type(e_seq_tab).__name__} - {e_seq_tab}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Tab Initialization Warning",
                                 f"The '{constants.TAB_SEQUENCE_CONTROLLER_TITLE}' tab could not be initialized due to an error:\n{e_seq_tab}\n\n"
                                 "This tab will be unavailable. You can continue using other features of the application.")

        if self.tab_sequence_controller_widget:
            self.tab_sequence_controller_widget.new_measurement_signal.connect(self._handle_new_measurement_from_sequence) # 사용자 제공 코드의 슬롯명
            self.tab_sequence_controller_widget.sequence_status_changed_signal.connect(self._handle_sequence_status_changed) # 사용자 제공 코드의 슬롯명
            self.tabs.addTab(self.tab_sequence_controller_widget, constants.TAB_SEQUENCE_CONTROLLER_TITLE)
            if self.tabs.indexOf(self.tab_sequence_controller_widget) != -1:
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)
        else:
            print("ERROR: SequenceControllerTab widget is None after instantiation attempt. Tab will not be added.")
            placeholder_tab = QWidget()
            placeholder_layout = QVBoxLayout(placeholder_tab)
            error_label = QLabel(f"'{constants.TAB_SEQUENCE_CONTROLLER_TITLE}' tab failed to load.\nPlease check logs for details.")
            error_label.setAlignment(Qt.AlignCenter)
            placeholder_layout.addWidget(error_label)
            self.tabs.addTab(placeholder_tab, f"{constants.TAB_SEQUENCE_CONTROLLER_TITLE} (Error)")
            self.tabs.setTabEnabled(self.tabs.count() - 1, False)

        # Results Viewer Tab
        self.tab_results_viewer_widget = ResultsViewerTab(parent=self) # 사용자 제공 코드: results_manager_instance 나중에 전달 가능성
        if self.tab_results_viewer_widget:
             # 사용자 제공 코드에는 ResultsViewerTab 생성 시 results_manager 전달 안함.
             # 필요하다면 update 메소드 등으로 전달하거나, 여기서 전달.
             # 여기서는 ResultsViewerTab이 내부적으로 ResultsManager를 받거나,
             # 또는 다른 메소드를 통해 설정된다고 가정.
             # 이전 코드에서는 생성자에 전달했었음: ResultsViewerTab(results_manager_instance=self.results_manager, parent=self)
             # 사용자 제공 코드에 맞추려면, ResultsViewerTab이 results_manager를 어떻게 받는지 확인 필요.
             # 일단 생성자에서 받는다고 가정하고 수정.
            if hasattr(self.tab_results_viewer_widget, 'results_manager'): # results_manager 속성이 있다면 직접 할당
                self.tab_results_viewer_widget.results_manager = self.results_manager
            elif hasattr(self.tab_results_viewer_widget, 'set_results_manager'): # 설정 메소드가 있다면 호출
                self.tab_results_viewer_widget.set_results_manager(self.results_manager)


            excel_export_config = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
            if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                self.tab_results_viewer_widget.set_excel_export_config(excel_export_config)
            
            self.tab_results_viewer_widget.clear_results_requested_signal.connect(self._handle_clear_results)
            self.tab_results_viewer_widget.export_excel_requested_signal.connect(self._handle_export_excel)
            self.tabs.addTab(self.tab_results_viewer_widget, constants.TAB_RESULTS_TITLE)
            self._populate_results_viewer_ui()

        if self.main_layout and self.tabs:
            self.main_layout.addWidget(self.tabs)

    # get_current_sample_number, get_current_measurement_conditions 등 사용자 제공 코드의 메소드 유지
    def get_current_sample_number(self) -> str:
        if self.sample_number_input:
            return self.sample_number_input.text().strip()
        return constants.DEFAULT_SAMPLE_NUMBER

    def get_current_measurement_conditions(self) -> Dict[str, Any]:
        conditions: Dict[str, Any] = {}
        if self.sourcemeter and self.current_settings.get('sourcemeter_use'):
            if hasattr(self.sourcemeter, 'get_cached_set_voltage') and self.sourcemeter.get_cached_set_voltage() is not None: # type: ignore
                conditions[constants.EXCEL_COL_COND_SMU_V] = self.sourcemeter.get_cached_set_voltage() # type: ignore
            if hasattr(self.sourcemeter, 'get_cached_set_current') and self.sourcemeter.get_cached_set_current() is not None: # type: ignore
                conditions[constants.EXCEL_COL_COND_SMU_I] = self.sourcemeter.get_cached_set_current() # type: ignore
        
        if self.chamber and self.current_settings.get('chamber_use'):
            if hasattr(self.chamber, 'get_cached_target_temperature') and self.chamber.get_cached_target_temperature() is not None: # type: ignore
                conditions[constants.EXCEL_COL_COND_CHAMBER_T] = self.chamber.get_cached_target_temperature() # type: ignore
        return conditions

    def save_excel_export_config_to_settings(self, excel_config: List[Dict[str, Any]]):
        self.current_settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY] = excel_config
        if self.settings_manager and not self.settings_manager.save_settings(self.current_settings): # settings_manager None 체크
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, "Excel 내보내기 설정 저장에 실패했습니다.")

    @pyqtSlot()
    def _handle_evb_check_request(self): # 사용자 제공 코드의 슬롯명
        print("DEBUG_MW: EVB connection check requested by user.")
        if self.statusBar(): self.statusBar().showMessage("EVB 연결 상태 확인 중...", 2000)

        if self.i2c_device:
            self.i2c_device.close()
            self.i2c_device = None
            print("DEBUG_MW: Existing I2C device closed and cleared.")
        
        self._init_i2c_device() # 수정된 _init_i2c_device 호출

        if self.tab_settings_widget and hasattr(self.tab_settings_widget, 'update_evb_status'): # 이름 수정
            message_detail = ""
            attempted_chip_id_for_msg = ""
            # 메시지용 Chip ID 결정 (UI 우선, 다음 설정값)
            if self.tab_settings_widget and hasattr(self.tab_settings_widget, 'chip_id_input') and self.tab_settings_widget.chip_id_input:
                attempted_chip_id_for_msg = self.tab_settings_widget.chip_id_input.text().strip()
            if not attempted_chip_id_for_msg:
                attempted_chip_id_for_msg = self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, "N/A")


            if self.i2c_device and self.i2c_device.is_opened:
                actual_connected_id_str = "Unknown"
                if hasattr(self.i2c_device, 'chip_id') and self.i2c_device.chip_id is not None:
                    try:
                        if isinstance(self.i2c_device.chip_id, int):
                            actual_connected_id_str = f"{self.i2c_device.chip_id:#04X}"
                        else: # I2CDevice.chip_id가 int가 아닌 경우 (현재 로직상으로는 int여야 함)
                            actual_connected_id_str = str(self.i2c_device.chip_id)
                    except Exception as e_fmt:
                        print(f"Error formatting chip_id for EVB status: {e_fmt}")
                        actual_connected_id_str = str(self.i2c_device.chip_id) + " (format err)"
                message_detail = f"ID: {actual_connected_id_str} (Connected)"
            else:
                # 연결 실패 또는 장치 없음
                status_reason = "연결 실패"
                if not attempted_chip_id_for_msg or attempted_chip_id_for_msg == "N/A":
                    status_reason = "Chip ID 없음"
                elif self.i2c_device is None and chip_id_str_to_use: # _init_i2c_device에서 ID는 있었으나 인스턴스 생성 실패
                    status_reason = "초기화 실패"

                message_detail = f"Attempted ID: {attempted_chip_id_for_msg} ({status_reason})"
            
            is_actually_connected = self.i2c_device is not None and self.i2c_device.is_opened
            self.tab_settings_widget.update_evb_status(is_actually_connected, message_detail)
            print(f"DEBUG_MW: Sent to SettingsTab.update_evb_status: connected={is_actually_connected}, msg='{message_detail}'")

        if self.tab_sequence_controller_widget and hasattr(self.tab_sequence_controller_widget, 'update_hardware_instances'):
            self.tab_sequence_controller_widget.update_hardware_instances(
                self.i2c_device, self.multimeter, self.sourcemeter, self.chamber
            )
        if self.statusBar(): self.statusBar().showMessage("EVB 연결 상태 확인 완료.", 3000)

    @pyqtSlot(dict)
    def _handle_settings_changed(self, new_settings_from_tab: dict):
        self.current_settings.update(new_settings_from_tab)
        if self.settings_manager and self.settings_manager.save_settings(self.current_settings): # settings_manager None 체크
            QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, constants.MSG_SETTINGS_SAVED)
            self._initialize_hardware_from_settings()
            
            if self.tab_settings_widget:
                if hasattr(self.tab_settings_widget, 'populate_settings'):
                    self.tab_settings_widget.populate_settings(self.current_settings, self.i2c_device)
                else: # Fallback if populate_settings is not available
                    if hasattr(self.tab_settings_widget, 'load_settings'): self.tab_settings_widget.load_settings()
                    if hasattr(self.tab_settings_widget, 'update_evb_status'):
                        chip_id_to_display = self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, "N/A")
                        # Ensure chip_id_to_display is suitable for direct display or convert if necessary
                        status_msg_detail = chip_id_to_display
                        if self.i2c_device and self.i2c_device.is_opened and hasattr(self.i2c_device, 'chip_id') and self.i2c_device.chip_id:
                            # If connected, use the actual chip_id from the device, which should be an int
                            try:
                                if isinstance(self.i2c_device.chip_id, int):
                                    status_msg_detail = f"ID: {self.i2c_device.chip_id:#04X} (connected)"
                                else:
                                    status_msg_detail = f"ID: {self.i2c_device.chip_id} (connected, format error)"
                            except (TypeError, ValueError):
                                status_msg_detail = f"ID: {self.i2c_device.chip_id} (connected, format error)"
                        elif chip_id_to_display:
                            # Don't try to format a string with hex format code
                            if isinstance(chip_id_to_display, int):
                                status_msg_detail = f"ID: {chip_id_to_display:#04X} (from settings)"
                            else:
                                status_msg_detail = f"ID: {chip_id_to_display} (from settings)"
                        else:
                            status_msg_detail = "Chip ID not set in settings"
                        self.tab_settings_widget.update_evb_status(self.i2c_device is not None and self.i2c_device.is_opened, status_msg_detail)


            if self.tab_sequence_controller_widget:
                if hasattr(self.tab_sequence_controller_widget, 'update_settings'):
                     self.tab_sequence_controller_widget.update_settings(self.current_settings)

            if self.tab_results_viewer_widget:
                if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                    excel_conf = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
                    self.tab_results_viewer_widget.set_excel_export_config(excel_conf)
        elif self.settings_manager: # save_settings가 False를 반환한 경우
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_SETTINGS_SAVE_FAILED)
        else: # settings_manager가 None인 경우
             QMessageBox.critical(self, "Error", "SettingsManager is not initialized. Cannot save settings.")


    @pyqtSlot()
    def _handle_clear_results(self):
        reply = QMessageBox.question(self, "결과 초기화", "모든 측정 결과를 삭제하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.results_manager: self.results_manager.clear_results() # None 체크
            self._populate_results_viewer_ui()
            if self.tab_sequence_controller_widget and \
               hasattr(self.tab_sequence_controller_widget, 'execution_log_textedit') and \
               self.tab_sequence_controller_widget.execution_log_textedit is not None:
                self.tab_sequence_controller_widget.execution_log_textedit.append("--- 모든 측정 결과가 초기화되었습니다. ---")

    @pyqtSlot(str, list) # sheet_definitions 타입이 List[ExcelSheetConfig] 여야 함
    def _handle_export_excel(self, file_path: str, sheet_definitions: List[Dict[str,Any]]):
        if not self.results_manager:
            QMessageBox.critical(self, "Error", "ResultsManager is not initialized.")
            return

        results_df = self.results_manager.get_results_dataframe()
        if results_df.empty:
            QMessageBox.information(self, "No Data", "내보낼 결과 데이터가 없습니다.")
            return

        exporter = ExcelExporter(results_df)
        # sheet_definitions가 List[ExcelSheetConfig] 타입이라고 가정.
        # ExcelExportSettingsDialog.get_final_sheet_configs()가 이 타입을 반환해야 함.
        if exporter.export_to_excel(file_path, sheet_definitions): 
            QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, f"결과가 '{file_path}'에 저장되었습니다.")
        else:
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, "Excel 파일 저장에 실패했습니다. 로그를 확인하세요.")

    @pyqtSlot(str, object, str, dict) # sample_number 타입 변경 (object -> str) 사용자 제공 코드 기준
    def _handle_new_measurement_from_sequence(self, variable_name: str, value: object, sample_number: str, conditions: Dict[str, Any]):
        if self.results_manager: # None 체크
            self.results_manager.add_measurement(variable_name, value, sample_number, conditions)
        self._populate_results_viewer_ui()

    @pyqtSlot(bool)
    def _handle_sequence_status_changed(self, is_running: bool):
        if self.statusBar():
            if is_running:
                self.statusBar().showMessage("시퀀스 실행 중...")
            else:
                self.statusBar().showMessage("시퀀스 완료/중단됨.", 3000)
                if self.tab_reg_viewer_widget and self.tabs and self.tabs.isTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget)):
                     if self.register_map:
                        # populate_table에 register_map 인자가 필요하다면 전달
                        if hasattr(self.tab_reg_viewer_widget, 'populate_table') and callable(getattr(self.tab_reg_viewer_widget, 'populate_table')):
                            try: # populate_table 시그니처에 따라 호출
                                self.tab_reg_viewer_widget.populate_table(self.register_map)
                            except TypeError:
                                self.tab_reg_viewer_widget.populate_table() # 인자 없이 호출 시도 (호환성)


    def load_json_file_dialog(self): # 사용자 제공 코드의 메소드명
        options = QFileDialog.Options()
        start_dir = os.path.expanduser("~")
        if self.current_settings and constants.SETTINGS_LAST_JSON_PATH_KEY in self.current_settings:
            last_path = self.current_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY, "")
            if last_path and os.path.exists(os.path.dirname(last_path)):
                start_dir = os.path.dirname(last_path)
            elif last_path:
                 start_dir = os.path.dirname(last_path)
                 if not start_dir: start_dir = os.path.expanduser("~")

        fileName, _ = QFileDialog.getOpenFileName(self,
                                                  constants.FILE_SELECT_DIALOG_TITLE,
                                                  start_dir,
                                                  constants.JSON_FILES_FILTER,
                                                  options=options)
        if fileName:
            self._process_loaded_json(fileName, auto_loaded=False)

    def _process_loaded_json(self, file_path: str, auto_loaded: bool = False):
        # 사용자 제공 코드의 로직 유지 (UI 요소 None 체크 강화)
        ui_ready = True
        missing_elements = []
        required_ui_elements = [
            'current_file_label', 'tabs', 'tab_reg_viewer_widget',
            'tab_sequence_controller_widget', 'completer_model', 'settings_manager' # settings_manager 추가
        ]
        for elem_name in required_ui_elements:
            if not hasattr(self, elem_name) or getattr(self, elem_name) is None:
                ui_ready = False
                missing_elements.append(elem_name)
        
        if not ui_ready:
            error_message = f"UI 요소 또는 매니저({', '.join(missing_elements)})가 준비되지 않아 JSON 파일을 처리할 수 없습니다."
            if self.statusBar():
                self.statusBar().showMessage(f"Critical Error: {error_message}", 7000)
            QMessageBox.critical(self, "초기화 오류", error_message)
            return

        try:
            load_success, errors = self.register_map.load_from_json_file(file_path) # register_map 사용
            
            if load_success:
                self.current_json_file = file_path
                if self.current_file_label: self.current_file_label.setText(constants.FILE_LOADED_LABEL_PREFIX + os.path.basename(self.current_json_file))

                if not auto_loaded:
                    self.current_settings[constants.SETTINGS_LAST_JSON_PATH_KEY] = self.current_json_file
                    self.settings_manager.save_settings(self.current_settings) # settings_manager 사용
                
                if self.tab_reg_viewer_widget: # RegisterViewerTab에 register_map 전달
                    if hasattr(self.tab_reg_viewer_widget, 'update_register_map'):
                        self.tab_reg_viewer_widget.update_register_map(self.register_map)
                    if hasattr(self.tab_reg_viewer_widget, 'populate_table'):
                        self.tab_reg_viewer_widget.populate_table(self.register_map) # Pass self.register_map
                if self.tabs and self.tab_reg_viewer_widget: self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), True)

                if self.completer_model: # completer_model None 체크
                    field_ids = self.register_map.get_all_field_ids()
                    self.completer_model.setStringList(field_ids)
                
                if self.tab_sequence_controller_widget:
                    if hasattr(self.tab_sequence_controller_widget, 'update_register_map'):
                        self.tab_sequence_controller_widget.update_register_map(self.register_map)
                if self.tabs and self.tab_sequence_controller_widget: self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), True)

                if not auto_loaded:
                    QMessageBox.information(self, constants.MSG_TITLE_SUCCESS,
                                            constants.MSG_JSON_LOAD_SUCCESS.format(filename=os.path.basename(self.current_json_file)))
                if self.statusBar(): self.statusBar().showMessage(f"'{os.path.basename(self.current_json_file)}' 로드 완료.", 3000)
            else:
                if self.current_file_label:
                    self.current_file_label.setText(f"로드 실패: {os.path.basename(file_path)}")
                
                if self.tabs:
                    if self.tab_reg_viewer_widget: self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False)
                    if self.tab_sequence_controller_widget: self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)
                if self.completer_model: self.completer_model.setStringList([])
                
                error_details = "\n".join(errors) if errors else "알 수 없는 파싱 오류입니다."
                if not auto_loaded:
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        f"{constants.MSG_JSON_LOAD_FAIL_PARSE.format(filename=os.path.basename(file_path))}\n\n세부 정보:\n{error_details}")
                else:
                    if self.statusBar(): self.statusBar().showMessage(f"자동 로드 실패 ({os.path.basename(file_path)}): 파싱 오류.", 5000)

        except Exception as e:
            if hasattr(self, 'current_file_label') and self.current_file_label:
                 self.current_file_label.setText(f"로드 중 예외 발생: {os.path.basename(file_path)}")
            if hasattr(self, 'tabs') and self.tabs:
                if hasattr(self, 'tab_reg_viewer_widget') and self.tab_reg_viewer_widget and self.tabs.indexOf(self.tab_reg_viewer_widget) != -1:
                     self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False)
                if hasattr(self, 'tab_sequence_controller_widget') and self.tab_sequence_controller_widget and self.tabs.indexOf(self.tab_sequence_controller_widget) != -1:
                     self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)
            if hasattr(self, 'completer_model') and self.completer_model:
                self.completer_model.setStringList([])
            
            error_message = constants.MSG_JSON_LOAD_FAIL_GENERIC.format(error=str(e))
            if not auto_loaded:
                QMessageBox.critical(self, constants.MSG_TITLE_ERROR, error_message)
            else:
                if self.statusBar(): self.statusBar().showMessage(f"자동 로드 중 예외 ({os.path.basename(file_path)}).", 5000)
            import traceback
            traceback.print_exc()

    def _populate_results_viewer_ui(self):
        """ResultsViewerTab의 테이블을 현재 결과 데이터로 채웁니다."""
        if self.tab_results_viewer_widget is None:
            return
        if self.results_manager: # results_manager None 체크
            df = self.results_manager.get_results_dataframe()
            self.tab_results_viewer_widget.populate_table(df)

    def closeEvent(self, event):
        """애플리케이션 종료 시 호출됩니다."""
        # 사용자 제공 코드의 로직 유지
        if self.tab_sequence_controller_widget:
            player_thread = getattr(self.tab_sequence_controller_widget, 'sequence_player_thread', None)
            if player_thread and player_thread.isRunning():
                self.tab_sequence_controller_widget.request_stop_sequence()
                if not player_thread.wait(2000):
                    print("Warning: Sequence thread did not finish in time during application close.")
            elif player_thread:
                player_thread.quit()
                player_thread.wait(100)

        if self.i2c_device: self.i2c_device.close()
        if self.multimeter: self.multimeter.disconnect()
        if self.sourcemeter: self.sourcemeter.disconnect()
        if self.chamber:
            if hasattr(self.chamber, 'is_connected') and self.chamber.is_connected:
                if hasattr(self.chamber, 'stop_operation'): self.chamber.stop_operation()
                if hasattr(self.chamber, 'power_off'): self.chamber.power_off()
            if hasattr(self.chamber, 'disconnect'): self.chamber.disconnect()

        event.accept()

    # New slot to handle instrument enable/disable changes
    @pyqtSlot(str, bool)
    def _handle_instrument_enable_changed(self, instrument_type: str, enabled: bool):
        print(f"DEBUG_MW: _handle_instrument_enable_changed: Instrument '{instrument_type}' state: {enabled}")
        
        # Update overall SequenceControllerTab enabled state
        if self.tabs and self.tab_sequence_controller_widget:
            current_settings = self.settings_manager.load_settings() # Get fresh settings
            dmm_on = current_settings.get(constants.SETTINGS_MULTIMETER_USE_KEY, False)
            smu_on = current_settings.get(constants.SETTINGS_SOURCEMETER_USE_KEY, False)
            chamber_on = current_settings.get(constants.SETTINGS_CHAMBER_USE_KEY, False)
            
            any_instrument_on = dmm_on or smu_on or chamber_on
            reg_map_loaded = bool(self.register_map and self.register_map.logical_fields_map) # Check if regmap is loaded and has fields
            
            # Main Sequence Tab is enabled if any instrument is on AND a register map is loaded.
            # Or, if you want to allow sequence editing even without a regmap for some cases (e.g. delay only sequences),
            # you might change this logic, e.g., main_seq_tab_should_be_enabled = any_instrument_on or reg_map_loaded (if you want it enabled if either is true)
            # For now, let's stick to: it must have an instrument AND a regmap to be useful for most instrument actions.
            # However, the user wants the tab active if ANY instrument is active, regardless of regmap for now.
            main_seq_tab_should_be_enabled = any_instrument_on
            if not reg_map_loaded and any_instrument_on:
                 print("DEBUG_MW: An instrument is enabled, but no register map is loaded. Sequence tab will be enabled, but I2C actions might fail.")
            # If no instrument is selected, the main sequence tab should be disabled if it was only enabled due to instruments.
            # If it was enabled due to a loaded regmap (for I2C actions), it should remain enabled if regmap is still loaded.
            # This simplifies to: enable if any instrument OR regmap is loaded.
            # Let's refine: Enable if (any instrument is on) OR (regmap is loaded and NO instruments are on, allowing I2C/Delay only sequences)
            # For now, let's try: Enable if any instrument is on. If no instruments are on, its state depends on whether a regmap is loaded (for I2C/Delay).

            if any_instrument_on:
                main_seq_tab_should_be_enabled = True
            elif reg_map_loaded: # No instruments, but regmap is loaded (allow I2C/Delay)
                main_seq_tab_should_be_enabled = True 
            else: # No instruments and no regmap
                main_seq_tab_should_be_enabled = False

            seq_tab_idx = self.tabs.indexOf(self.tab_sequence_controller_widget)
            if seq_tab_idx != -1:
                print(f"DEBUG_MW: Main Sequence Tab current enabled: {self.tabs.isTabEnabled(seq_tab_idx)}, calculated should be: {main_seq_tab_should_be_enabled} (any_instr_on: {any_instrument_on}, regmap_loaded: {reg_map_loaded})")
                self.tabs.setTabEnabled(seq_tab_idx, main_seq_tab_should_be_enabled)

        # Propagate to SequenceControllerTab to manage its internal (ActionInputPanel) tabs
        if self.tab_sequence_controller_widget and hasattr(self.tab_sequence_controller_widget, 'set_instrument_tab_enabled'):
            self.tab_sequence_controller_widget.set_instrument_tab_enabled(instrument_type, enabled)
        else:
            print(f"DEBUG_MW: SequenceControllerTab or set_instrument_tab_enabled method not found.")

if __name__ == '__main__':
    print("main_window.py is not intended to be run directly. Run main_app.py instead.")
    sys.exit()