# ui/tabs/sequence_controller_tab.py
import sys
import os
from typing import List, Tuple, Dict, Any, Optional, ForwardRef

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QPushButton, QSplitter, QMessageBox, QApplication, QStyle,
    QInputDialog, QDialog
)
from PyQt5.QtCore import Qt, QSize, QStringListModel, QThread, pyqtSignal, pyqtSlot, QStandardPaths
from PyQt5.QtGui import QFont, QIcon

# --- 코어 모듈 임포트 ---
from core import constants
from core.register_map_backend import RegisterMap
from core.hardware_control import I2CDevice, Multimeter, Sourcemeter, Chamber
from core.sequence_io_manager import SequenceIOManager
from core.sequence_player import SequencePlayer

# --- UI 위젯 및 다이얼로그 임포트 ---
from ui.widgets.action_input_panel import ActionInputPanel
from ui.dialogs.loop_definition_dialog import LoopDefinitionDialog
from ui.widgets.saved_sequence_panel import SavedSequencePanel

# --- 타입 힌팅을 위한 Forward Reference ---
if sys.version_info >= (3, 9):
    RegMapWindowType = ForwardRef('main_window.RegMapWindow')
else:
    RegMapWindowType = 'main_window.RegMapWindow'


class SequenceControllerTab(QWidget):
    new_measurement_signal = pyqtSignal(str, object, str, dict)
    sequence_status_changed_signal = pyqtSignal(bool)

    def __init__(self,
                 parent: Optional[QWidget] = None,
                 register_map_instance: Optional[RegisterMap] = None,
                 settings_instance: Optional[Dict[str, Any]] = None,
                 completer_model_instance: Optional[QStringListModel] = None,
                 i2c_device_instance: Optional[I2CDevice] = None,
                 multimeter_instance: Optional[Multimeter] = None,
                 sourcemeter_instance: Optional[Sourcemeter] = None,
                 chamber_instance: Optional[Chamber] = None,
                 main_window_ref: Optional[RegMapWindowType] = None
                 ):
        super().__init__(parent)
        self._ui_setup_successful = True 

        try:
            # 멤버 변수 초기화
            self._main_splitter: Optional[QSplitter] = None
            self.action_input_panel: Optional[ActionInputPanel] = None
            self.add_to_seq_button: Optional[QPushButton] = None
            self.define_loop_button: Optional[QPushButton] = None
            self.saved_sequence_panel: Optional[SavedSequencePanel] = None
            self.play_seq_button: Optional[QPushButton] = None
            self.stop_seq_button: Optional[QPushButton] = None
            self.sequence_list_widget: Optional[QListWidget] = None
            self.remove_from_seq_button: Optional[QPushButton] = None
            self.clear_seq_button: Optional[QPushButton] = None
            self.execution_log_textedit: Optional[QTextEdit] = None

            # 의존성 주입
            self.register_map = register_map_instance
            self.current_settings = settings_instance if settings_instance is not None else {}
            self.completer_model = completer_model_instance if completer_model_instance else QStringListModel(self)
            self.main_window_ref = main_window_ref
            self.i2c_device = i2c_device_instance
            self.multimeter = multimeter_instance
            self.sourcemeter = sourcemeter_instance
            self.chamber = chamber_instance
            self.sequence_player_thread: Optional[QThread] = None
            self.sequence_player: Optional[SequencePlayer] = None
            self.sequence_io_manager = SequenceIOManager()
            self.saved_sequences_dir: str = self._setup_saved_sequences_directory()

            # UI 구성
            # 1. SequenceControllerTab 자체의 메인 레이아웃 설정 (단 한번만!)
            main_container_layout = QVBoxLayout()
            self.setLayout(main_container_layout) # 여기서 메인 레이아웃 설정
            main_container_layout.setContentsMargins(8, 10, 8, 8)

            # 2. _setup_main_layout에서 스플리터 등을 메인 레이아웃에 추가
            self._setup_main_layout() 

            if self._ui_setup_successful: self._create_left_panel()
            if self._ui_setup_successful: self._create_right_panel()
            
            if not self._ui_setup_successful:
                self._show_ui_creation_error_state()
                return

            self._connect_signals()

            if self.action_input_panel:
                self.action_input_panel.update_completer_model(self.completer_model)
                self.action_input_panel.update_settings(self.current_settings)
                self.action_input_panel.update_register_map(self.register_map)
            elif self._ui_setup_successful:
                print("ERROR_SCT: self.action_input_panel is None after successful UI panel creation.")
                self._ui_setup_successful = False
                self._show_ui_creation_error_state()
                return

            if self._main_splitter and self._ui_setup_successful:
                QApplication.processEvents() 
                initial_width = self.width() if self.width() > 100 else 1000 
                self._main_splitter.setSizes([int(initial_width * 0.45), int(initial_width * 0.55)])
        
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Unhandled exception during SequenceControllerTab.__init__: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False
            if hasattr(self, '_show_ui_creation_error_state'):
                try:
                    self._show_ui_creation_error_state()
                except Exception as e_show_error:
                    print(f"CRITICAL_ERROR_SCT: Exception during _show_ui_creation_error_state after __init__ failure: {e_show_error}")
                    current_layout = self.layout()
                    if current_layout:
                        while current_layout.count():
                            item = current_layout.takeAt(0)
                            if item.widget(): item.widget().deleteLater()
                            elif item.layout(): item.layout().deleteLater()
                    try:
                        fallback_layout = QVBoxLayout() 
                        self.setLayout(fallback_layout) 
                        fallback_label = QLabel("탭 초기화 중 복구 불가능한 오류 발생.", self)
                        fallback_layout.addWidget(fallback_label)
                        self.setEnabled(False)
                    except Exception as final_except:
                         print(f"CRITICAL_ERROR_SCT: Final attempt to set error UI failed: {final_except}")

    def _show_ui_creation_error_state(self):
        current_layout = self.layout()
        if current_layout is not None:
            while current_layout.count() > 0:
                item = current_layout.takeAt(0)
                if item is None: continue
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                else: 
                    layout_item = item.layout()
                    if layout_item:
                        while layout_item.count() > 0:
                            sub_item = layout_item.takeAt(0)
                            if sub_item.widget():
                                sub_item.widget().setParent(None)
                                sub_item.widget().deleteLater()
                            elif sub_item.layout():
                                sub_item.layout().deleteLater()
                        layout_item.deleteLater()
            # self.setLayout(None) # 기존 레이아웃 제거

        # 새 오류 레이아웃 설정
        # self.setLayout(None) # 기존 레이아웃을 확실히 제거
        error_layout = QVBoxLayout() # 새 레이아웃 생성
        self.setLayout(error_layout) # 여기서 새 레이아웃 설정 (이전에 None으로 설정했다면 문제 없음)
        
        error_label = QLabel("Test Sequence Controller 탭 초기화 실패.\n"
                             "PyQt5/Python 환경 또는 코드 오류일 수 있습니다.\n"
                             "애플리케이션 로그를 확인하세요.", self)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
        error_layout.addWidget(error_label)
        
        print("ERROR_SCT: UI Creation Failed. Tab content replaced with error message.")
        self.setEnabled(False)

    def _setup_saved_sequences_directory(self) -> str:
        app_name_for_folder = getattr(constants, 'APP_NAME_FOR_FOLDER', 'TestAutomationApp')
        app_data_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not app_data_path:
            app_data_path = os.path.join(os.path.expanduser("~"), f".{app_name_for_folder}")
        sequences_dir = os.path.join(app_data_path, constants.SAVED_SEQUENCES_DIR_NAME)
        try:
            os.makedirs(sequences_dir, exist_ok=True)
            return sequences_dir
        except OSError as e:
            alt_dir = os.path.join(os.getcwd(), constants.SAVED_SEQUENCES_DIR_NAME)
            try:
                os.makedirs(alt_dir, exist_ok=True)
                QMessageBox.warning(self, "경로 오류", f"기본 경로({sequences_dir}) 생성 실패: {e}\n대체 경로 사용: {alt_dir}")
                return alt_dir
            except OSError as e2:
                QMessageBox.critical(self, "치명적 경로 오류", f"모든 시퀀스 저장 경로 생성 실패: {e2}\n현재 작업 디렉토리 사용: {os.getcwd()}")
                return os.getcwd()

    def _setup_main_layout(self):
        # __init__에서 이미 self.setLayout()이 호출되었으므로, 여기서는 self.layout()을 가져와 사용
        main_container_layout = self.layout()
        if main_container_layout is None: # __init__에서 레이아웃 설정이 실패한 경우 (방어 코드)
            print("CRITICAL_ERROR_SCT: Main layout not set in __init__ before _setup_main_layout.")
            self._ui_setup_successful = False
            main_container_layout = QVBoxLayout() # 임시 레이아웃이라도 설정 시도
            self.setLayout(main_container_layout) # 여기서라도 설정
            # return # 더 이상 진행 불가

        # main_container_layout.setContentsMargins(8, 10, 8, 8) # 이미 __init__에서 설정됨
        try:
            self._main_splitter = QSplitter(Qt.Horizontal, self)
            main_container_layout.addWidget(self._main_splitter)
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Failed to create or add QSplitter: {e}")
            self._ui_setup_successful = False

    def _create_left_panel(self):
        if not self._main_splitter: self._ui_setup_successful = False; return
        if not self._ui_setup_successful: return

        left_panel_widget = QWidget(self) 
        left_panel_layout = QVBoxLayout() 
        left_panel_widget.setLayout(left_panel_layout)
        left_panel_layout.setSpacing(10)
        left_panel_layout.setContentsMargins(0,0,0,0)

        try:
            self.action_input_panel = ActionInputPanel(self.completer_model, self.current_settings, self.register_map, parent=left_panel_widget)
            if not self.action_input_panel : raise RuntimeError("ActionInputPanel creation failed.")
            left_panel_layout.addWidget(self.action_input_panel)

            action_buttons_layout = QHBoxLayout()
            self.add_to_seq_button = QPushButton(constants.SEQ_ADD_BUTTON_TEXT, left_panel_widget)
            try: self.add_to_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowRight)); self.add_to_seq_button.setIconSize(QSize(16,16))
            except Exception as e: print(f"Warning_SCT: Icon for add_to_seq_button: {e}")
            action_buttons_layout.addWidget(self.add_to_seq_button)
            self.define_loop_button = QPushButton(constants.DEFINE_LOOP_BUTTON_TEXT, left_panel_widget)
            try: self.define_loop_button.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
            except Exception as e: print(f"Warning_SCT: Icon for define_loop_button: {e}")
            action_buttons_layout.addWidget(self.define_loop_button)
            left_panel_layout.addLayout(action_buttons_layout)

            self.saved_sequence_panel = SavedSequencePanel(self.sequence_io_manager, self.saved_sequences_dir, parent=left_panel_widget)
            if not self.saved_sequence_panel: raise RuntimeError("SavedSequencePanel creation failed.")
            left_panel_layout.addWidget(self.saved_sequence_panel)
            
            left_panel_layout.addStretch(1)

            play_stop_button_layout = QHBoxLayout()
            self.play_seq_button = QPushButton(constants.SEQ_PLAY_BUTTON_TEXT, left_panel_widget)
            try: self.play_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_MediaPlay))
            except Exception as e: print(f"Warning_SCT: Icon for play_seq_button: {e}")
            
            self.stop_seq_button = QPushButton(constants.SEQ_STOP_BUTTON_TEXT, left_panel_widget)
            try: self.stop_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_MediaStop))
            except Exception as e: print(f"Warning_SCT: Icon for stop_seq_button: {e}")
            
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
            else: raise RuntimeError("Stop sequence button creation failed.")

            play_stop_button_layout.addWidget(self.play_seq_button)
            play_stop_button_layout.addWidget(self.stop_seq_button)
            left_panel_layout.addLayout(play_stop_button_layout)
            
            self._main_splitter.addWidget(left_panel_widget)
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_left_panel: {e}")
            self._ui_setup_successful = False


    def _create_right_panel(self):
        if not self._main_splitter: self._ui_setup_successful = False; return
        if not self._ui_setup_successful : return

        right_panel_widget = QWidget(self)
        right_panel_layout = QVBoxLayout()
        right_panel_widget.setLayout(right_panel_layout)
        right_panel_layout.setSpacing(10)
        right_panel_layout.setContentsMargins(0,0,0,0)

        seq_list_label = QLabel(constants.SEQ_LIST_LABEL, right_panel_widget)
        right_panel_layout.addWidget(seq_list_label)

        try:
            self.sequence_list_widget = QListWidget(right_panel_widget)
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during QListWidget creation: {e}")
            self._ui_setup_successful = False
            return 

        if not self.sequence_list_widget or not bool(self.sequence_list_widget):
            print(f"CRITICAL_ERROR_SCT: QListWidget creation failed or object is invalid. Object: {self.sequence_list_widget}")
            self._ui_setup_successful = False
            return

        font_monospace = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        log_font_size = getattr(constants, 'LOG_FONT_SIZE', 10)
        self.sequence_list_widget.setFont(QFont(font_monospace, log_font_size))
        self.sequence_list_widget.setAlternatingRowColors(True)
        right_panel_layout.addWidget(self.sequence_list_widget)

        try:
            list_management_buttons_layout = QHBoxLayout()
            self.remove_from_seq_button = QPushButton(constants.SEQ_REMOVE_BUTTON_TEXT, right_panel_widget)
            try: self.remove_from_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon)); self.remove_from_seq_button.setIconSize(QSize(16,16))
            except Exception as e: print(f"Warning_SCT: Icon for remove_from_seq_button: {e}")
            list_management_buttons_layout.addWidget(self.remove_from_seq_button)

            self.clear_seq_button = QPushButton(constants.SEQ_CLEAR_BUTTON_TEXT, right_panel_widget)
            try: self.clear_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogResetButton))
            except Exception as e: print(f"Warning_SCT: Icon for clear_seq_button: {e}")
            list_management_buttons_layout.addWidget(self.clear_seq_button)
            right_panel_layout.addLayout(list_management_buttons_layout)

            exec_log_label = QLabel(constants.SEQ_LOG_LABEL, right_panel_widget)
            right_panel_layout.addWidget(exec_log_label)
            self.execution_log_textedit = QTextEdit(right_panel_widget)
            self.execution_log_textedit.setReadOnly(True)
            self.execution_log_textedit.setFont(QFont(font_monospace, log_font_size))
            self.execution_log_textedit.setLineWrapMode(QTextEdit.NoWrap)
            right_panel_layout.addWidget(self.execution_log_textedit)
            self._main_splitter.addWidget(right_panel_widget)
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_right_panel (after SLW creation): {e}")
            self._ui_setup_successful = False

    def _connect_signals(self):
        if not self._ui_setup_successful: return

        if self.add_to_seq_button: self.add_to_seq_button.clicked.connect(self._add_item_from_action_panel)
        else: print("Error_SCT: add_to_seq_button is None, cannot connect.")
        if self.define_loop_button: self.define_loop_button.clicked.connect(self._handle_define_loop)
        if self.play_seq_button: self.play_seq_button.clicked.connect(self.play_sequence)
        if self.stop_seq_button: self.stop_seq_button.clicked.connect(self.request_stop_sequence)
        if self.clear_seq_button: self.clear_seq_button.clicked.connect(self.clear_sequence_list_and_log)
        if self.remove_from_seq_button: self.remove_from_seq_button.clicked.connect(self.remove_selected_item_with_warning)
        if self.saved_sequence_panel:
            self.saved_sequence_panel.load_sequence_to_editor_requested.connect(self._load_items_to_sequence_list)
            self.saved_sequence_panel.save_current_sequence_as_requested.connect(self._handle_save_current_sequence_as)
        else: print("Error_SCT: saved_sequence_panel is None, cannot connect its signals.")

    @pyqtSlot()
    def _add_item_from_action_panel(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.action_input_panel:
            QMessageBox.critical(self, "오류", "액션 입력 패널이 준비되지 않았습니다."); return
        if not self.sequence_list_widget or not bool(self.sequence_list_widget): # bool() 체크 추가
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다. (self.sequence_list_widget is invalid)"); return

        action_data = self.action_input_panel.get_current_action_string_and_prefix()
        if action_data:
            _prefix, full_action_str, _params_dict = action_data
            self.sequence_list_widget.addItem(full_action_str)
            self.action_input_panel.clear_input_fields()

    @pyqtSlot()
    def _handle_define_loop(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.sequence_list_widget or not bool(self.sequence_list_widget):
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다."); return
        selected_items_widgets = self.sequence_list_widget.selectedItems()
        if not selected_items_widgets:
            QMessageBox.information(self, "루프 정의", "루프에 포함할 아이템을 선택하세요."); return

        target_actions_data: List[Tuple[int, str, Dict[str, str]]] = []
        temp_player_for_parsing = SequencePlayer([], {}, self.register_map, None, None, None, None, None, self)
        for item_widget in selected_items_widgets:
            original_index = self.sequence_list_widget.row(item_widget)
            item_text = item_widget.text().lstrip()
            action_prefix, params_dict = temp_player_for_parsing._parse_sequence_item(item_text)
            if action_prefix and action_prefix not in [constants.SEQ_PREFIX_LOOP_START, constants.SEQ_PREFIX_LOOP_END] and not self._is_item_in_loop(original_index):
                target_actions_data.append((original_index, action_prefix, params_dict))
        temp_player_for_parsing.deleteLater()
        if not target_actions_data:
            QMessageBox.warning(self, "루프 정의 오류", "유효한 루프 대상 액션이 없거나 이미 루프의 일부입니다."); return

        dialog = LoopDefinitionDialog(target_actions_data, self)
        if dialog.exec_() == QDialog.Accepted:
            loop_params = dialog.get_loop_parameters()
            if loop_params:
                loop_start_str = "; ".join([f"{k}={v}" for k, v in loop_params.items()])
                self.sequence_list_widget.insertItem(self.sequence_list_widget.row(selected_items_widgets[0]), f"{constants.SEQ_PREFIX_LOOP_START}: {loop_start_str}")
                for i in range(len(selected_items_widgets)):
                    item_to_indent = self.sequence_list_widget.item(self.sequence_list_widget.row(selected_items_widgets[0]) + 1 + i)
                    if not item_to_indent.text().startswith("  "): item_to_indent.setText("  " + item_to_indent.text())
                self.sequence_list_widget.insertItem(self.sequence_list_widget.row(selected_items_widgets[-1]) + 1, "  " + constants.SEQ_PREFIX_LOOP_END)

    def _is_item_in_loop(self, item_index: int) -> bool:
        if not self.sequence_list_widget or not bool(self.sequence_list_widget): return False
        loop_level = 0
        for i in range(item_index + 1):
            item_text = self.sequence_list_widget.item(i).text().strip()
            if item_text.startswith(constants.SEQ_PREFIX_LOOP_START): loop_level += 1
            elif item_text.startswith(constants.SEQ_PREFIX_LOOP_END):
                if loop_level > 0: loop_level -= 1
            if i == item_index and not item_text.startswith(constants.SEQ_PREFIX_LOOP_START) and not item_text.startswith(constants.SEQ_PREFIX_LOOP_END):
                return loop_level > 0
        return False

    @pyqtSlot(list)
    def _load_items_to_sequence_list(self, items: List[str]):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.sequence_list_widget or not bool(self.sequence_list_widget):
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다."); return
        if self.sequence_list_widget.count() > 0:
            if QMessageBox.question(self, "시퀀스 로드", "현재 시퀀스를 지우고 로드하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.No:
                return
        self.sequence_list_widget.clear()
        self.sequence_list_widget.addItems(items)
        if self.execution_log_textedit: self.execution_log_textedit.clear(); self.execution_log_textedit.append(f"--- '{items[0].split(':')[0]}...' 시퀀스 로드됨 ---" if items else "--- 빈 시퀀스 로드됨 ---")

    @pyqtSlot(str)
    def _handle_save_current_sequence_as(self, requested_name_without_ext: str):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.sequence_list_widget or not bool(self.sequence_list_widget) or not self.saved_sequence_panel:
            QMessageBox.critical(self, "오류", "필수 UI 요소가 초기화되지 않았습니다."); return
        current_items = [self.sequence_list_widget.item(i).text() for i in range(self.sequence_list_widget.count())]
        if not current_items:
            QMessageBox.information(self, "시퀀스 저장", "저장할 아이템이 없습니다."); return
        if self.saved_sequence_panel.save_sequence_to_file_requested_by_controller(current_items, requested_name_without_ext):
            QMessageBox.information(self, "저장 성공", f"'{requested_name_without_ext}{constants.SEQUENCE_FILE_EXTENSION}' 저장 완료.")

    @pyqtSlot()
    def remove_selected_item_with_warning(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.sequence_list_widget or not bool(self.sequence_list_widget):
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다."); return
        selected_items = self.sequence_list_widget.selectedItems()
        if not selected_items: QMessageBox.information(self, "삭제 오류", "삭제할 아이템을 선택하세요."); return
        warn_loop = any(item.text().strip().startswith((constants.SEQ_PREFIX_LOOP_START, constants.SEQ_PREFIX_LOOP_END)) or self._is_item_in_loop(self.sequence_list_widget.row(item)) for item in selected_items)
        if warn_loop and QMessageBox.question(self, "루프 수정 경고", "루프 관련 아이템 삭제 시 구조가 손상될 수 있습니다. 계속하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
            return
        for index in sorted([self.sequence_list_widget.row(item) for item in selected_items], reverse=True):
            self.sequence_list_widget.takeItem(index)

    @pyqtSlot()
    def clear_sequence_list_and_log(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if self.sequence_list_widget: self.sequence_list_widget.clear()
        if self.execution_log_textedit: self.execution_log_textedit.clear()
        QMessageBox.information(self, "초기화", "시퀀스 목록 및 로그가 초기화되었습니다.")

    @pyqtSlot()
    def play_sequence(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if self.sequence_player_thread and self.sequence_player_thread.isRunning():
            QMessageBox.information(self, constants.MSG_TITLE_INFO, "시퀀스가 이미 실행 중입니다."); return
        if not self.sequence_list_widget or self.sequence_list_widget.count() == 0:
            QMessageBox.information(self, constants.MSG_TITLE_INFO, constants.MSG_SEQUENCE_EMPTY); return
        if self.execution_log_textedit: self.execution_log_textedit.clear()
        items_to_play = [self.sequence_list_widget.item(i).text() for i in range(self.sequence_list_widget.count())]
        sample_num = self.main_window_ref.get_current_sample_number() if self.main_window_ref and hasattr(self.main_window_ref, 'get_current_sample_number') else constants.DEFAULT_SAMPLE_NUMBER
        self.sequence_player = SequencePlayer(items_to_play, self.current_settings, self.register_map, self.i2c_device, self.multimeter, self.sourcemeter, self.chamber, sample_num, self.main_window_ref, None)
        self.sequence_player_thread = QThread(self)
        self.sequence_player.moveToThread(self.sequence_player_thread)
        self.sequence_player.log_message_signal.connect(self._handle_log_message)
        self.sequence_player.measurement_result_signal.connect(self.new_measurement_signal)
        self.sequence_player.sequence_finished_signal.connect(self._handle_sequence_finished)
        self.sequence_player_thread.started.connect(self.sequence_player.run_sequence)
        self.sequence_player.sequence_finished_signal.connect(self.sequence_player_thread.quit)
        self.sequence_player.destroyed.connect(self._on_player_destroyed)
        self.sequence_player_thread.finished.connect(self.sequence_player.deleteLater)
        self.sequence_player_thread.finished.connect(self.sequence_player_thread.deleteLater)
        self.sequence_player_thread.finished.connect(self._on_thread_actually_finished)
        if self.play_seq_button: self.play_seq_button.setEnabled(False)
        if self.stop_seq_button: self.stop_seq_button.setEnabled(True)
        self.sequence_status_changed_signal.emit(True)
        self.sequence_player_thread.start()

    @pyqtSlot()
    def request_stop_sequence(self):
        if not self._ui_setup_successful: return 
        if self.sequence_player and self.sequence_player_thread and self.sequence_player_thread.isRunning():
            self.sequence_player.request_stop_flag = True
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
            if self.execution_log_textedit: self.execution_log_textedit.append("--- 시퀀스 중단 요청 중... ---")
        else:
            if self.play_seq_button: self.play_seq_button.setEnabled(True)
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)

    @pyqtSlot(str)
    def _handle_log_message(self, message: str):
        if self.execution_log_textedit: self.execution_log_textedit.append(message)

    @pyqtSlot(bool, str)
    def _handle_sequence_finished(self, success_flag: bool, message: str):
        if self.execution_log_textedit: self.execution_log_textedit.append(f"--- {message} ---")
        msg_box_func = QMessageBox.information if success_flag else QMessageBox.warning
        msg_box_func(self, "시퀀스 실행 결과", f"시퀀스 실행이 {'완료' if success_flag else '실패/중단'}되었습니다.\n{message}")
        if self.play_seq_button: self.play_seq_button.setEnabled(True)
        if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
        self.sequence_status_changed_signal.emit(False)

    @pyqtSlot()
    def _on_thread_actually_finished(self):
        print("Info_SCT: QThread actually finished.")
        self.sequence_player = None; self.sequence_player_thread = None
        if self.play_seq_button: self.play_seq_button.setEnabled(True)
        if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
        print("Info_SCT: Player and Thread references cleared.")

    @pyqtSlot()
    def _on_player_destroyed(self): print("Info_SCT: SequencePlayer object destroyed.")

    def update_hardware_instances(self, i2c_dev, mm_dev, sm_dev, ch_dev):
        self.i2c_device, self.multimeter, self.sourcemeter, self.chamber = i2c_dev, mm_dev, sm_dev, ch_dev

    def update_register_map(self, new_register_map):
        self.register_map = new_register_map
        if self.completer_model: self.completer_model.setStringList(self.register_map.get_all_field_ids() if self.register_map else [])
        if self.action_input_panel: self.action_input_panel.update_completer_model(self.completer_model); self.action_input_panel.update_register_map(self.register_map)

    def update_settings(self, new_settings):
        self.current_settings = new_settings if new_settings is not None else {}
        if self.action_input_panel: self.action_input_panel.update_settings(self.current_settings)