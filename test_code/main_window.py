# main_window.py
import sys
import os
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget, QLabel, QMessageBox,
    QStyle, QLineEdit
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

import pandas as pd

class RegMapWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- 1. 비 UI 멤버 변수 및 핵심 매니저 객체 초기화 ---
        try:
            self.settings_manager = SettingsManager()
            self.results_manager = ResultsManager()
            self.register_map = RegisterMap()
            self.completer_model = QStringListModel()

            self.current_settings: Dict[str, Any] = {}
            self.i2c_device: Optional[I2CDevice] = None
            self.multimeter: Optional[Multimeter] = None
            self.sourcemeter: Optional[Sourcemeter] = None
            self.chamber: Optional[Chamber] = None
            self.current_json_file: Optional[str] = None

            # --- 2. UI 멤버 변수 None으로 명시적 선언 ---
            self.central_widget: Optional[QWidget] = None
            self.main_layout: Optional[QVBoxLayout] = None
            self.sample_number_input: Optional[QLineEdit] = None
            self.load_json_button: Optional[QPushButton] = None
            self.current_file_label: Optional[QLabel] = None
            self.tabs: Optional[QTabWidget] = None
            self.tab_settings_widget: Optional[SettingsTab] = None
            self.tab_reg_viewer_widget: Optional[RegisterViewerTab] = None
            self.tab_sequence_controller_widget: Optional[SequenceControllerTab] = None
            self.tab_results_viewer_widget: Optional[ResultsViewerTab] = None

        except Exception as e:
            print(f"FATAL ERROR during RegMapWindow non-UI member initialization: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            if QApplication.instance():
                 QMessageBox.critical(self, "애플리케이션 초기화 오류",
                                     f"윈도우 내부 데이터 초기화 중 치명적 오류:\n{e}\n\n프로그램을 종료합니다.")
                 QApplication.instance().quit()
            else:
                print("CRITICAL: QApplication instance not found during non-UI member init error handling.")
            sys.exit(1) # 프로그램 종료
            # return # sys.exit 이후 도달하지 않음

        # --- 3. UI 생성 및 배치 ---
        try:
            self.setWindowTitle(constants.WINDOW_TITLE)
            self.setGeometry(100, 100,
                             constants.INITIAL_WINDOW_WIDTH,
                             constants.INITIAL_WINDOW_HEIGHT)
            self._apply_styles()
            print("DEBUG: _apply_styles() finished.")

            self.central_widget = QWidget(self)
            self.setCentralWidget(self.central_widget)
            print(f"DEBUG: central_widget created: {self.central_widget}")

            self.main_layout = QVBoxLayout()
            if self.central_widget:
                self.central_widget.setLayout(self.main_layout)
            else: # 일반적으로 발생해서는 안 됨
                raise RuntimeError("Central widget is None after creation, cannot set layout.")
            print(f"DEBUG: main_layout created and set on central_widget: {self.main_layout}")
            
            if self.main_layout is None: # 이전 오류 수정 사항 반영
                raise RuntimeError("main_layout is explicitly None after QVBoxLayout() and setLayout().")

            self.main_layout.setContentsMargins(10, 10, 10, 10)
            self.main_layout.setSpacing(10)

            self._create_file_selection_area()
            print("DEBUG: _create_file_selection_area() finished.")

            self._create_and_integrate_tabs() # 내부에서 SettingsTab 생성
            print("DEBUG: _create_and_integrate_tabs() finished.")

        except Exception as e:
            print(f"FATAL ERROR during RegMapWindow UI setup: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            if self.central_widget: # 최소한 central_widget이라도 있어야 메시지 박스 표시 가능
                QMessageBox.critical(self, "애플리케이션 UI 오류",
                                     f"UI 생성 중 심각한 오류가 발생했습니다:\n{e}\n\n프로그램을 종료합니다.")
            if QApplication.instance():
                QApplication.instance().quit()
            sys.exit(1) # 오류 발생 시 프로그램 종료
            # return # sys.exit 이후 도달하지 않음

        # --- 4. 애플리케이션 설정 로드 및 적용 (UI가 준비된 후에 호출) ---
        try:
            self._load_app_settings() # 내부에서 _initialize_hardware_from_settings 호출
            print("DEBUG: _load_app_settings() finished.")
        except Exception as e:
            print(f"ERROR during _load_app_settings: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "설정 로드 오류", f"애플리케이션 설정 로드 중 오류:\n{e}")

        # --- 5. 설정 로드 후 UI 최종 업데이트 ---
        try:
            # SettingsTab의 populate_settings는 _load_app_settings 또는 _handle_settings_changed에서 호출됨
            # 여기서는 다른 탭들만 초기화
            if self.tab_results_viewer_widget:
                excel_conf = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
                if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                    self.tab_results_viewer_widget.set_excel_export_config(excel_conf)

            self.statusBar().showMessage("애플리케이션 준비 완료.")
            print("DEBUG: RegMapWindow __init__ completed successfully.")
        except Exception as e:
            print(f"ERROR during final UI update: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "UI 업데이트 오류", f"최종 UI 업데이트 중 오류:\n{e}")

    def _apply_styles(self):
        """애플리케이션의 기본 스타일시트를 적용합니다."""
        app_font_family = getattr(constants, 'APP_FONT', '맑은 고딕')
        if sys.platform == "darwin":
            app_font_family = getattr(constants, 'APP_FONT_MACOS', 'Apple SD Gothic Neo')
        elif "linux" in sys.platform:
            app_font_family = getattr(constants, 'APP_FONT_LINUX', 'Noto Sans KR')
        app_font_size = getattr(constants, 'APP_FONT_SIZE', 14)
        # 스타일시트 문자열은 가독성을 위해 여러 줄로 작성
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
        loaded_settings = self.settings_manager.load_settings()
        self.current_settings.update(loaded_settings)
        
        self._initialize_hardware_from_settings() # 하드웨어 초기화 먼저 수행

        last_json_path = self.current_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY)
        if last_json_path and os.path.exists(last_json_path):
            self._process_loaded_json(last_json_path, auto_loaded=True)
        elif last_json_path: # 경로가 있으나 파일이 없는 경우
            if self.statusBar(): self.statusBar().showMessage(f"자동 로드 실패: '{last_json_path}' 파일을 찾을 수 없습니다.", 5000)
        
        # SettingsTab UI 채우기 (하드웨어 초기화 및 JSON 로드 시도 후)
        if self.tab_settings_widget:
            self.tab_settings_widget.populate_settings(self.current_settings, self.i2c_device)

    def _clear_hardware_instances(self):
        """모든 하드웨어 인스턴스를 안전하게 닫고 None으로 설정합니다."""
        if self.i2c_device: self.i2c_device.close(); self.i2c_device = None
        if self.multimeter: self.multimeter.disconnect(); self.multimeter = None
        if self.sourcemeter: self.sourcemeter.disconnect(); self.sourcemeter = None
        if self.chamber:
            if hasattr(self.chamber, 'is_connected') and self.chamber.is_connected:
                if hasattr(self.chamber, 'stop_operation'): self.chamber.stop_operation()
                if hasattr(self.chamber, 'power_off'): self.chamber.power_off()
            if hasattr(self.chamber, 'disconnect'): self.chamber.disconnect()
            self.chamber = None
        print("DEBUG: Hardware instances cleared.")

    def _init_i2c_device(self):
        """I2C 장치를 설정값에 따라 초기화합니다."""
        chip_id = self.current_settings.get('chip_id', "")
        if chip_id:
            self.i2c_device = I2CDevice(chip_id_str=chip_id)
            if self.i2c_device and self.i2c_device.is_opened:
                if hasattr(self.i2c_device, 'change_port'): # 포트 변경 시도
                    if not self.i2c_device.change_port(0):
                         print("Warning: I2C 포트 변경(0) 실패.")
            elif self.i2c_device and not self.i2c_device.is_opened: # 객체는 생성되었으나 열리지 않음
                QMessageBox.warning(self, constants.MSG_TITLE_ERROR, f"I2C 장치(ID: {chip_id}) 연결 실패. EVB 상태를 확인하세요.")
                self.i2c_device = None # 연결 실패 시 None으로 설정
            elif not self.i2c_device: # I2CDevice 객체 생성 자체가 실패한 경우 (예: raonpy 로드 실패)
                 QMessageBox.warning(self, constants.MSG_TITLE_ERROR, f"I2C 장치(ID: {chip_id}) 초기화 실패 (객체 생성 실패).")
                 # self.i2c_device는 이미 None일 것임
        else:
            print("Info: Chip ID가 설정되지 않아 I2C 장치를 초기화하지 않습니다.")
            self.i2c_device = None # 명시적으로 None 설정

    def _init_multimeter(self):
        """멀티미터를 설정값에 따라 초기화합니다."""
        if self.current_settings.get('multimeter_use'):
            serial_num = self.current_settings.get('multimeter_serial')
            if serial_num:
                self.multimeter = Multimeter(serial_number_str=serial_num)
                if not self.multimeter.connect():
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Multimeter", serial_number=serial_num))
                    self.multimeter = None
            else: # 시리얼 번호가 없으면 사용 비활성화
                self.current_settings['multimeter_use'] = False
                # UI 업데이트는 _handle_settings_changed 또는 _load_app_settings의 마지막 부분에서 일괄 처리
                print("Warning: Multimeter 시리얼 번호가 없어 사용할 수 없습니다. 설정에서 비활성화합니다.")
        else:
            self.multimeter = None


    def _init_sourcemeter(self):
        """소스미터를 설정값에 따라 초기화합니다."""
        if self.current_settings.get('sourcemeter_use'):
            serial_num = self.current_settings.get('sourcemeter_serial')
            if serial_num:
                self.sourcemeter = Sourcemeter(serial_number_str=serial_num)
                if not self.sourcemeter.connect():
                     QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Sourcemeter", serial_number=serial_num))
                     self.sourcemeter = None
            else: # 시리얼 번호가 없으면 사용 비활성화
                self.current_settings['sourcemeter_use'] = False
                print("Warning: Sourcemeter 시리얼 번호가 없어 사용할 수 없습니다. 설정에서 비활성화합니다.")
        else:
            self.sourcemeter = None

    def _init_chamber(self):
        """챔버를 설정값에 따라 초기화합니다."""
        if self.current_settings.get('chamber_use'):
            serial_num = self.current_settings.get('chamber_serial')
            # Chamber는 시리얼 번호가 선택 사항일 수 있음 (Chamber 클래스 구현에 따라 다름)
            self.chamber = Chamber(serial_number_str=serial_num if serial_num else None)
            if not self.chamber.connect():
                 QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                    constants.MSG_DEVICE_CONNECTION_FAILED.format(device_name="Chamber", serial_number=serial_num if serial_num else "N/A"))
                 # 연결 실패 시 self.chamber를 None으로 할지, 아니면 연결 안 된 객체로 둘지 결정 필요
                 # 여기서는 연결 안 된 객체로 두되, 사용 시 is_connected 등을 확인해야 함
        else:
            self.chamber = None

    def _initialize_hardware_from_settings(self):
        """설정값을 기반으로 하드웨어 장치들을 (재)초기화합니다."""
        self._clear_hardware_instances() # 기존 인스턴스 정리

        self._init_i2c_device()
        self._init_multimeter()
        self._init_sourcemeter()
        self._init_chamber()

        # SequenceControllerTab에 업데이트된 하드웨어 인스턴스 전달
        if self.tab_sequence_controller_widget:
            if hasattr(self.tab_sequence_controller_widget, 'update_hardware_instances'):
                self.tab_sequence_controller_widget.update_hardware_instances(
                    self.i2c_device, self.multimeter, self.sourcemeter, self.chamber
                )
        
        # SettingsTab의 EVB 상태 표시 업데이트
        if self.tab_settings_widget and hasattr(self.tab_settings_widget, 'update_evb_status_display'):
             self.tab_settings_widget.update_evb_status_display(self.i2c_device, self.current_settings.get('chip_id'))
        print("DEBUG: Hardware initialization from settings completed.")


    def _create_file_selection_area(self):
        """JSON 파일 선택 및 샘플 번호 입력 UI를 생성하고 멤버 변수에 할당합니다."""
        if self.main_layout is None: # 명시적으로 None 확인
            QMessageBox.critical(self, "UI 초기화 오류", "파일 선택 영역 UI 생성 실패 (main_layout is None).")
            raise RuntimeError("Cannot create file selection area: main_layout is None.")

        file_button_layout = QHBoxLayout()

        sample_label = QLabel(constants.SAMPLE_NUMBER_LABEL)
        self.sample_number_input = QLineEdit()
        self.sample_number_input.setPlaceholderText("e.g., SN001")
        self.sample_number_input.setFixedWidth(150)
        self.sample_number_input.setText(constants.DEFAULT_SAMPLE_NUMBER)

        file_button_layout.addWidget(sample_label)
        file_button_layout.addWidget(self.sample_number_input)
        file_button_layout.addSpacing(20)

        self.load_json_button = QPushButton()
        self.load_json_button.setObjectName("loadJsonButton")
        try:
            app_instance = QApplication.instance()
            if app_instance:
                 self.load_json_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogOpenButton))
            else: # Fallback if QApplication.instance() is None (should not happen in normal execution)
                 if self.load_json_button: self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)
        except Exception as e: # Catch any exception during icon setting
            print(f"Warning: Could not set icon for load_json_button: {e}")
            if self.load_json_button: self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)

        # 아이콘 설정 실패 시 텍스트라도 보이도록 보장
        if self.load_json_button and self.load_json_button.icon().isNull() and not self.load_json_button.text():
            self.load_json_button.setText(constants.LOAD_JSON_BUTTON_TEXT)
        
        if self.load_json_button: # QPushButton이 성공적으로 생성되었는지 확인
            self.load_json_button.setIconSize(QSize(16,16)) # 아이콘 크기 설정
            self.load_json_button.setToolTip(constants.LOAD_JSON_TOOLTIP)
            self.load_json_button.clicked.connect(self.load_json_file_dialog)
            file_button_layout.addWidget(self.load_json_button)

        self.current_file_label = QLabel(constants.NO_FILE_LOADED_LABEL)
        color_text_muted = getattr(constants, 'COLOR_TEXT_MUTED', '#777777') # 기본값 제공
        self.current_file_label.setStyleSheet(f"QLabel {{ padding: 5px; font-style: italic; color: {color_text_muted}; }}")
        file_button_layout.addWidget(self.current_file_label)
        
        file_button_layout.addStretch() # 버튼들을 왼쪽으로 밀착
        self.main_layout.addLayout(file_button_layout)

    def _create_and_integrate_tabs(self):
        """메인 기능 탭들을 생성하고 QTabWidget에 통합하며 멤버 변수에 할당합니다."""
        if self.main_layout is None: # 명시적으로 None 확인
            QMessageBox.critical(self, "UI 초기화 오류", "탭 UI 생성 실패 (main_layout is None).")
            raise RuntimeError("Cannot create tabs: main_layout is None.")

        self.tabs = QTabWidget()

        # Settings Tab
        self.tab_settings_widget = SettingsTab(parent=self) # SettingsTab 인스턴스 생성
        if self.tab_settings_widget:
            # populate_settings는 _load_app_settings 또는 _handle_settings_changed에서 i2c_device와 함께 호출됨
            self.tab_settings_widget.settings_changed_signal.connect(self._handle_settings_changed)
            self.tabs.addTab(self.tab_settings_widget, constants.TAB_SETTINGS_TITLE)
        
        # Register Viewer Tab
        self.tab_reg_viewer_widget = RegisterViewerTab(parent=self)
        if self.tab_reg_viewer_widget:
            self.tabs.addTab(self.tab_reg_viewer_widget, constants.TAB_REG_VIEWER_TITLE)
            # 초기에는 Register Map이 로드되지 않았으므로 비활성화
            if self.tabs.indexOf(self.tab_reg_viewer_widget) != -1: # 위젯이 실제로 추가되었는지 확인
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False) 

        # Sequence Controller Tab
        self.tab_sequence_controller_widget = SequenceControllerTab(
            parent=self,
            register_map_instance=self.register_map,
            settings_instance=self.current_settings, # 초기 설정 전달
            completer_model_instance=self.completer_model, 
            i2c_device_instance=self.i2c_device, # 초기 하드웨어 인스턴스 전달
            multimeter_instance=self.multimeter,
            sourcemeter_instance=self.sourcemeter,
            chamber_instance=self.chamber,
            main_window_ref=self # RegMapWindow 자신을 참조로 전달
        )
        if self.tab_sequence_controller_widget:
            self.tab_sequence_controller_widget.new_measurement_signal.connect(self._handle_new_measurement_from_sequence)
            self.tab_sequence_controller_widget.sequence_status_changed_signal.connect(self._handle_sequence_status_changed)
            self.tabs.addTab(self.tab_sequence_controller_widget, constants.TAB_SEQUENCE_CONTROLLER_TITLE)
            if self.tabs.indexOf(self.tab_sequence_controller_widget) != -1:
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)

        # Results Viewer Tab
        self.tab_results_viewer_widget = ResultsViewerTab(parent=self)
        if self.tab_results_viewer_widget:
            # 초기 Excel 내보내기 설정 (current_settings에서 가져옴)
            excel_export_config = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
            if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                self.tab_results_viewer_widget.set_excel_export_config(excel_export_config)
            
            self.tab_results_viewer_widget.clear_results_requested_signal.connect(self._handle_clear_results)
            self.tab_results_viewer_widget.export_excel_requested_signal.connect(self._handle_export_excel)
            self.tabs.addTab(self.tab_results_viewer_widget, constants.TAB_RESULTS_TITLE)
            self._populate_results_viewer_ui() # 초기 데이터 표시 (비어있을 수 있음)

        self.main_layout.addWidget(self.tabs)

    def get_current_sample_number(self) -> str:
        """현재 입력된 샘플 번호를 반환합니다."""
        if self.sample_number_input:
            return self.sample_number_input.text().strip()
        return constants.DEFAULT_SAMPLE_NUMBER # 기본값 반환

    def get_current_measurement_conditions(self) -> Dict[str, Any]:
        """현재 측정 조건을 딕셔너리 형태로 반환합니다."""
        conditions: Dict[str, Any] = {}
        if self.sourcemeter and self.current_settings.get('sourcemeter_use'):
            if hasattr(self.sourcemeter, 'get_cached_set_voltage') and self.sourcemeter.get_cached_set_voltage() is not None:
                conditions[constants.EXCEL_COL_COND_SMU_V] = self.sourcemeter.get_cached_set_voltage()
            if hasattr(self.sourcemeter, 'get_cached_set_current') and self.sourcemeter.get_cached_set_current() is not None:
                conditions[constants.EXCEL_COL_COND_SMU_I] = self.sourcemeter.get_cached_set_current()
        
        if self.chamber and self.current_settings.get('chamber_use'):
            if hasattr(self.chamber, 'get_cached_target_temperature') and self.chamber.get_cached_target_temperature() is not None:
                conditions[constants.EXCEL_COL_COND_CHAMBER_T] = self.chamber.get_cached_target_temperature()
        return conditions

    def save_excel_export_config_to_settings(self, excel_config: List[Dict[str, Any]]):
        """Excel 내보내기 설정을 저장합니다."""
        self.current_settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY] = excel_config
        if not self.settings_manager.save_settings(self.current_settings):
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, "Excel 내보내기 설정 저장에 실패했습니다.")

    @pyqtSlot(dict)
    def _handle_settings_changed(self, new_settings_from_tab: dict):
        """SettingsTab에서 설정 변경 시그널을 받아 처리합니다."""
        self.current_settings.update(new_settings_from_tab)
        if self.settings_manager.save_settings(self.current_settings):
            QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, constants.MSG_SETTINGS_SAVED)
            self._initialize_hardware_from_settings() # 하드웨어 재초기화
            
            # SettingsTab UI 업데이트 (populate_settings 호출로 EVB 상태 포함)
            if self.tab_settings_widget:
                self.tab_settings_widget.populate_settings(self.current_settings, self.i2c_device)

            # SequenceControllerTab에 변경된 설정 및 하드웨어 인스턴스 업데이트
            if self.tab_sequence_controller_widget:
                if hasattr(self.tab_sequence_controller_widget, 'update_settings'):
                     self.tab_sequence_controller_widget.update_settings(self.current_settings)
                # update_hardware_instances는 _initialize_hardware_from_settings 내부에서 이미 호출됨

            # ResultsViewerTab에 변경된 Excel 설정 업데이트
            if self.tab_results_viewer_widget:
                if hasattr(self.tab_results_viewer_widget, 'set_excel_export_config'):
                    excel_conf = self.current_settings.get(constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY, [])
                    self.tab_results_viewer_widget.set_excel_export_config(excel_conf)
        else:
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_SETTINGS_SAVE_FAILED)

    @pyqtSlot()
    def _handle_clear_results(self):
        """ResultsViewerTab에서 결과 초기화 요청을 처리합니다."""
        reply = QMessageBox.question(self, "결과 초기화", "모든 측정 결과를 삭제하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.results_manager.clear_results()
            self._populate_results_viewer_ui() # UI 업데이트
            # 시퀀스 컨트롤러 탭의 로그에도 알림 (선택적)
            if self.tab_sequence_controller_widget and \
               hasattr(self.tab_sequence_controller_widget, 'execution_log_textedit') and \
               self.tab_sequence_controller_widget.execution_log_textedit is not None:
                self.tab_sequence_controller_widget.execution_log_textedit.append("--- 모든 측정 결과가 초기화되었습니다. ---")

    @pyqtSlot(str, list)
    def _handle_export_excel(self, file_path: str, sheet_definitions: List[Dict[str,Any]]):
        """ResultsViewerTab에서 Excel 내보내기 요청을 처리합니다."""
        if self.results_manager.export_to_excel(file_path, sheet_definitions):
            QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, f"결과가 '{file_path}'에 저장되었습니다.")
        else:
            QMessageBox.warning(self, constants.MSG_TITLE_ERROR, "Excel 파일 저장에 실패했습니다. 로그를 확인하세요.")

    @pyqtSlot(str, object, str, dict)
    def _handle_new_measurement_from_sequence(self, variable_name: str, value: object, sample_number: str, conditions: Dict[str, Any]):
        """SequenceControllerTab에서 새로운 측정 결과 시그널을 받아 처리합니다."""
        self.results_manager.add_measurement(variable_name, value, sample_number, conditions)
        self._populate_results_viewer_ui() # 결과 테이블 업데이트

    @pyqtSlot(bool)
    def _handle_sequence_status_changed(self, is_running: bool):
        """SequenceControllerTab에서 시퀀스 실행 상태 변경 시그널을 받아 처리합니다."""
        if self.statusBar(): # 상태바가 존재하면 메시지 표시
            if is_running:
                self.statusBar().showMessage("시퀀스 실행 중...")
            else:
                self.statusBar().showMessage("시퀀스 완료/중단됨.", 3000) # 3초 후 메시지 사라짐
                # 시퀀스 종료 후 Register Viewer 탭의 값들을 현재 값으로 갱신
                if self.tab_reg_viewer_widget and self.tabs and self.tabs.isTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget)):
                     if self.register_map: # RegisterMap 인스턴스가 유효한지 확인
                        self.tab_reg_viewer_widget.populate_table(self.register_map)

    def load_json_file_dialog(self):
        """JSON 레지스터 맵 파일 선택 다이얼로그를 엽니다."""
        options = QFileDialog.Options()
        # 마지막으로 사용한 경로 또는 사용자 홈 디렉토리에서 시작
        start_dir = os.path.expanduser("~") # 기본값
        if self.current_settings and constants.SETTINGS_LAST_JSON_PATH_KEY in self.current_settings:
            last_path = self.current_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY, "")
            if last_path and os.path.exists(os.path.dirname(last_path)): # 경로의 디렉토리가 존재하면
                start_dir = os.path.dirname(last_path)
            elif last_path: # 파일은 없지만 경로 문자열이 있다면 (예: 파일이 삭제된 경우)
                 start_dir = os.path.dirname(last_path) # 디렉토리만이라도 사용 시도
                 if not start_dir: start_dir = os.path.expanduser("~") # 그것도 안되면 홈으로

        fileName, _ = QFileDialog.getOpenFileName(self,
                                                  constants.FILE_SELECT_DIALOG_TITLE,
                                                  start_dir, # 시작 디렉토리
                                                  constants.JSON_FILES_FILTER,
                                                  options=options)
        if fileName:
            self._process_loaded_json(fileName, auto_loaded=False) # 수동 로드는 auto_loaded=False

    def _process_loaded_json(self, file_path: str, auto_loaded: bool = False):
        """선택된 JSON 파일을 로드하고 처리합니다."""
        # UI 요소들이 정상적으로 생성되었는지 먼저 확인
        ui_ready = True
        missing_elements = []
        required_ui_elements = [
            'current_file_label', 'tabs', 'tab_reg_viewer_widget',
            'tab_sequence_controller_widget', 'completer_model'
        ]
        for elem_name in required_ui_elements:
            if not hasattr(self, elem_name) or getattr(self, elem_name) is None:
                ui_ready = False
                missing_elements.append(elem_name)
        
        if not ui_ready:
            error_message = f"UI 요소 ({', '.join(missing_elements)})가 준비되지 않아 JSON 파일을 처리할 수 없습니다."
            if self.statusBar(): # 상태바가 있다면 메시지 표시
                self.statusBar().showMessage(f"Critical Error: {error_message}", 7000)
            QMessageBox.critical(self, "초기화 오류", error_message)
            return

        try:
            load_success, errors = self.register_map.load_from_json_file(file_path)
            
            if load_success:
                self.current_json_file = file_path
                self.current_file_label.setText(constants.FILE_LOADED_LABEL_PREFIX + os.path.basename(self.current_json_file))

                if not auto_loaded: # 사용자가 직접 파일을 선택한 경우에만 경로 저장
                    self.current_settings[constants.SETTINGS_LAST_JSON_PATH_KEY] = self.current_json_file
                    self.settings_manager.save_settings(self.current_settings)
                
                # Register Viewer 탭 업데이트 및 활성화
                self.tab_reg_viewer_widget.populate_table(self.register_map)
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), True)

                # 자동완성 모델 업데이트
                field_ids = self.register_map.get_all_field_ids()
                self.completer_model.setStringList(field_ids)
                
                # Sequence Controller 탭 업데이트 및 활성화
                if hasattr(self.tab_sequence_controller_widget, 'update_register_map'):
                    self.tab_sequence_controller_widget.update_register_map(self.register_map)
                self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), True)

                if not auto_loaded: # 수동 로드 시에만 성공 메시지 표시
                    QMessageBox.information(self, constants.MSG_TITLE_SUCCESS,
                                            constants.MSG_JSON_LOAD_SUCCESS.format(filename=os.path.basename(self.current_json_file)))
                if self.statusBar(): self.statusBar().showMessage(f"'{os.path.basename(self.current_json_file)}' 로드 완료.", 3000)
            else: # 로드 실패 (파싱 오류 등)
                if self.current_file_label: # current_file_label이 None이 아닌지 확인
                    self.current_file_label.setText(f"로드 실패: {os.path.basename(file_path)}")
                
                # 관련 탭들 비활성화
                if self.tab_reg_viewer_widget:
                    self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False)
                if self.tab_sequence_controller_widget:
                    self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)
                if self.completer_model: # completer_model이 None이 아닌지 확인
                    self.completer_model.setStringList([]) # 자동완성 목록 비우기
                
                error_details = "\n".join(errors) if errors else "알 수 없는 파싱 오류입니다."
                if not auto_loaded: # 수동 로드 실패 시에만 경고 메시지 표시
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR,
                                        f"{constants.MSG_JSON_LOAD_FAIL_PARSE.format(filename=os.path.basename(file_path))}\n\n세부 정보:\n{error_details}")
                else: # 자동 로드 실패는 상태바에만 표시
                    if self.statusBar(): self.statusBar().showMessage(f"자동 로드 실패 ({os.path.basename(file_path)}): 파싱 오류.", 5000)

        except Exception as e: # JSON 로드 과정에서 예기치 않은 오류 발생 시
            # UI 요소가 None일 수 있으므로 hasattr로 안전하게 접근
            if hasattr(self, 'current_file_label') and self.current_file_label:
                 self.current_file_label.setText(f"로드 중 예외 발생: {os.path.basename(file_path)}")
            if hasattr(self, 'tabs') and self.tabs: # tabs 객체가 생성되었는지 확인
                if hasattr(self, 'tab_reg_viewer_widget') and self.tab_reg_viewer_widget:
                     self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_reg_viewer_widget), False)
                if hasattr(self, 'tab_sequence_controller_widget') and self.tab_sequence_controller_widget:
                     self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_sequence_controller_widget), False)
            if hasattr(self, 'completer_model') and self.completer_model:
                self.completer_model.setStringList([])
            
            error_message = constants.MSG_JSON_LOAD_FAIL_GENERIC.format(error=str(e))
            if not auto_loaded:
                QMessageBox.critical(self, constants.MSG_TITLE_ERROR, error_message)
            else:
                if self.statusBar(): self.statusBar().showMessage(f"자동 로드 중 예외 ({os.path.basename(file_path)}).", 5000)
            import traceback
            traceback.print_exc() # 콘솔에 스택 트레이스 출력

    def _populate_results_viewer_ui(self):
        """ResultsViewerTab의 테이블을 현재 결과 데이터로 채웁니다."""
        if self.tab_results_viewer_widget is None: # 위젯이 아직 생성되지 않았으면 아무것도 안 함
            return
            
        df = self.results_manager.get_results_dataframe()
        self.tab_results_viewer_widget.populate_table(df)

    def closeEvent(self, event):
        """애플리케이션 종료 시 호출됩니다."""
        # 시퀀스 플레이어 스레드가 실행 중이면 정지 시도
        if self.tab_sequence_controller_widget: # 위젯이 생성되었는지 확인
            player_thread = getattr(self.tab_sequence_controller_widget, 'sequence_player_thread', None)
            if player_thread and player_thread.isRunning():
                self.tab_sequence_controller_widget.request_stop_sequence()
                if not player_thread.wait(2000): # 2초간 스레드 종료 대기
                    print("Warning: Sequence thread did not finish in time during application close.")
            elif player_thread: # 스레드는 있지만 실행 중이 아닐 때 (이미 종료된 경우 등)
                player_thread.quit() # 혹시 모를 정리
                player_thread.wait(100) # 짧게 대기

        # 하드웨어 연결 해제
        if self.i2c_device: self.i2c_device.close()
        if self.multimeter: self.multimeter.disconnect()
        if self.sourcemeter: self.sourcemeter.disconnect()
        if self.chamber:
            # Chamber 객체가 존재하고, 연결되어 있으며, 관련 메서드가 있는지 확인 후 호출
            if hasattr(self.chamber, 'is_connected') and self.chamber.is_connected:
                if hasattr(self.chamber, 'stop_operation'): self.chamber.stop_operation()
                if hasattr(self.chamber, 'power_off'): self.chamber.power_off()
            if hasattr(self.chamber, 'disconnect'): self.chamber.disconnect()

        event.accept() # 종료 이벤트 수락