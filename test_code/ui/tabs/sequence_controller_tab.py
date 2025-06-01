# ui/tabs/sequence_controller_tab.py
import sys
import os
from typing import List, Tuple, Dict, Any, Optional, ForwardRef, Union, cast
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QPushButton, QSplitter, QMessageBox, QApplication, QStyle,
    QInputDialog, QDialog, QStyledItemDelegate, QStyleOptionViewItem,
    QTreeWidget, QTreeWidgetItem, QMenu, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QStringListModel, QThread, pyqtSignal, pyqtSlot, QStandardPaths, QModelIndex, QMimeData, QPoint, QTimer
from PyQt5.QtGui import QFont, QIcon, QPainter, QDragEnterEvent, QDragMoveEvent, QDropEvent

# --- 코어 모듈 임포트 ---
from core import constants
from core.register_map_backend import RegisterMap
from core.hardware_control import I2CDevice, Multimeter, Sourcemeter, Chamber
from core.sequence_io_manager import SequenceIOManager
from core.sequence_player import SequencePlayer
from core.data_models import SequenceItem, SimpleActionItem, LoopActionItem

# --- UI 위젯 및 다이얼로그 임포트 ---
from ui.widgets.action_input_panel import ActionInputPanel
from ui.dialogs.loop_definition_dialog import LoopDefinitionDialog
from ui.widgets.saved_sequence_panel import SavedSequencePanel

# --- 타입 힌팅을 위한 Forward Reference ---
if sys.version_info >= (3, 9):
    RegMapWindowType = ForwardRef('main_window.RegMapWindow')
else:
    RegMapWindowType = 'main_window.RegMapWindow'


class SequenceListItemDelegate(QStyledItemDelegate): 
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex): 
        super().paint(painter, option, index)


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
            self.update_action_button: Optional[QPushButton] = None
            self.saved_sequence_panel: Optional[SavedSequencePanel] = None
            self.play_seq_button: Optional[QPushButton] = None
            self.stop_seq_button: Optional[QPushButton] = None
            self.sequence_list_widget: Optional[QTreeWidget] = None
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
            
            # SequenceIOManager 초기화 시 saved_sequences_dir 전달
            self.saved_sequences_dir: str = self._setup_saved_sequences_directory()
            self.sequence_io_manager = SequenceIOManager(sequences_dir=self.saved_sequences_dir)

            # UI 구성
            main_container_layout = QVBoxLayout()
            self.setLayout(main_container_layout) 
            main_container_layout.setContentsMargins(8, 10, 8, 8)

            self._setup_main_layout(main_container_layout) 

            print(f"DEBUG_SCT: __init__ - After _setup_main_layout, self._main_splitter is {self._main_splitter}, _ui_setup_successful is {self._ui_setup_successful}")

            splitter_for_panels = self._main_splitter

            if self._ui_setup_successful:
                if splitter_for_panels is not None:
                    print(f"DEBUG_SCT: __init__ - Before _create_left_panel, splitter_for_panels is {splitter_for_panels}, self._main_splitter is {self._main_splitter}")
                    self._create_left_panel(splitter_for_panels)
                else:
                    print(f"CRITICAL_ERROR_SCT: __init__ - splitter_for_panels (from self._main_splitter) is None before _create_left_panel. _ui_setup_successful was {self._ui_setup_successful}. Marking as failed.")
                    self._ui_setup_successful = False
            
            if self._ui_setup_successful: 
                if splitter_for_panels is not None:
                    print(f"DEBUG_SCT: __init__ - Before _create_right_panel, splitter_for_panels is {splitter_for_panels}, self._main_splitter is {self._main_splitter}")
                    self._create_right_panel(splitter_for_panels)
                else:
                    print(f"CRITICAL_ERROR_SCT: __init__ - splitter_for_panels (from self._main_splitter) is None before _create_right_panel. _ui_setup_successful was {self._ui_setup_successful}. Marking as failed.")
                    self._ui_setup_successful = False
            
            if not self._ui_setup_successful:
                self._show_ui_creation_error_state()
                return 

            self._connect_signals()

            if self.action_input_panel:
                self.action_input_panel.update_completer_model(self.completer_model)
                self.action_input_panel.update_settings(self.current_settings)
                self.action_input_panel.update_register_map(self.register_map)
            elif self._ui_setup_successful: 
                print("ERROR_SCT: self.action_input_panel is None after successful UI panel creation marked.")
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
            try:
                self._show_ui_creation_error_state()
            except Exception as e_show_error:
                print(f"CRITICAL_ERROR_SCT: Exception during _show_ui_creation_error_state after __init__ failure: {e_show_error}")
                current_layout = self.layout()
                if current_layout:
                    while current_layout.count():
                        item = current_layout.takeAt(0)
                        if item and item.widget(): item.widget().deleteLater()
                        elif item and item.layout(): item.layout().deleteLater() 
                try:
                    fallback_layout = QVBoxLayout()
                    self.setLayout(fallback_layout)
                    fallback_label = QLabel("탭 초기화 중 복구 불가능한 치명적 오류 발생.\n애플리케이션 로그를 확인하세요.", self)
                    fallback_label.setAlignment(Qt.AlignCenter)
                    fallback_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
                    fallback_layout.addWidget(fallback_label)
                    self.setEnabled(False)
                except Exception as final_except:
                     print(f"CRITICAL_ERROR_SCT: Final attempt to set error UI failed: {final_except}")


    def _show_ui_creation_error_state(self):
        print("DEBUG_SCT: Entering _show_ui_creation_error_state")
        
        error_label = QLabel("Test Sequence Controller 탭 초기화 실패.\n"
                             "PyQt5/Python 환경 또는 코드 오류일 수 있습니다.\n"
                             "애플리케이션 로그를 확인하세요.", self)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")

        current_layout = self.layout()
        if current_layout is not None:
            print(f"DEBUG_SCT: Clearing existing layout {current_layout}.")
            while current_layout.count():
                item = current_layout.takeAt(0)
                if item is None: continue
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                else:
                    layout_item = item.layout()
                    if layout_item:
                        while layout_item.count():
                            sub_item = layout_item.takeAt(0)
                            if sub_item and sub_item.widget():
                                sub_item.widget().setParent(None)
                                sub_item.widget().deleteLater()
                            elif sub_item and sub_item.layout():
                                sub_item.layout().deleteLater()
                        layout_item.deleteLater()
            try:
                current_layout.addWidget(error_label)
                print(f"DEBUG_SCT: Added error label to existing (cleared) layout {current_layout}.")
            except RuntimeError as e_add_widget: 
                print(f"DEBUG_SCT: Failed to add widget to existing layout ({e_add_widget}). Trying to set a new layout.")
                self.setLayout(None) 
                new_error_layout = QVBoxLayout()
                new_error_layout.addWidget(error_label)
                try:
                    self.setLayout(new_error_layout)
                    print(f"DEBUG_SCT: Set new error_layout {new_error_layout} after previous attempt failed.")
                except Exception as e_set_layout:
                    print(f"CRITICAL_ERROR_SCT: Failed to set new error_layout: {e_set_layout}. Widget state might be invalid.")
                    error_label.setParent(self) 
                    error_label.show()
        else: 
            print(f"DEBUG_SCT: No existing layout. Creating new layout for error message.")
            new_error_layout = QVBoxLayout()
            new_error_layout.addWidget(error_label)
            try:
                self.setLayout(new_error_layout)
                print(f"DEBUG_SCT: Set new error_layout {new_error_layout}.")
            except Exception as e_set_layout:
                print(f"CRITICAL_ERROR_SCT: Failed to set new error_layout: {e_set_layout}. Widget state might be invalid.")
                error_label.setParent(self) 
                error_label.show()

        print("ERROR_SCT: UI Creation Failed. Tab content replaced/updated with error message.")
        self.setEnabled(False) 

    def _setup_saved_sequences_directory(self) -> str:
        # 상대경로 (test_automation/user_sequences) 기준으로 폴더 생성 및 반환
        sequences_dir = constants.USER_SEQUENCES_DIR_NAME
        try:
            os.makedirs(sequences_dir, exist_ok=True)
            print(f"INFO_SCT: User sequences directory: {sequences_dir}")
            return sequences_dir
        except OSError as e:
            print(f"CRITICAL_SCT: Failed to create user sequences directory '{sequences_dir}': {e}")
            # 폴더 생성 실패 시, 현재 디렉토리를 반환 (비추천)
            alt_dir = '.'
            QMessageBox.critical(self, "치명적 경로 오류", 
                                 f"시퀀스 저장 폴더 '{sequences_dir}' 생성에 실패했습니다: {e}\n"
                                 f"현재 작업 디렉토리 '{alt_dir}'를 사용합니다 (권장되지 않음).")
            return alt_dir

    def _setup_main_layout(self, target_layout: QVBoxLayout):
        if target_layout is None:
            print("CRITICAL_ERROR_SCT: Main layout (target_layout) is None in _setup_main_layout.")
            self._ui_setup_successful = False
            return

        try:
            splitter = QSplitter(Qt.Horizontal, self) 
            target_layout.addWidget(splitter)
            self._main_splitter = splitter 
            print(f"DEBUG_SCT: _setup_main_layout - QSplitter created and added successfully. self._main_splitter: {self._main_splitter}, Parent: {self._main_splitter.parent()}")
            
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during QSplitter setup in _setup_main_layout: {e}")
            import traceback
            traceback.print_exc()
            self._main_splitter = None 
            self._ui_setup_successful = False

    def _create_left_panel(self, splitter_arg: Optional[QSplitter]):
        print(f"DEBUG_SCT: Entered _create_left_panel. splitter_arg is {splitter_arg}. self._main_splitter (attribute) is {self._main_splitter}")
        if splitter_arg is None: 
            print(f"ERROR_SCT_LeftPanel: splitter_arg is None in _create_left_panel. Aborting. self._main_splitter is {self._main_splitter}")
            if self._ui_setup_successful : self._ui_setup_successful = False # 명시적으로 실패 처리
            return
        
        left_panel_widget = QWidget(self) 
        left_panel_layout = QVBoxLayout(left_panel_widget) 
        left_panel_layout.setSpacing(10)
        left_panel_layout.setContentsMargins(0,0,0,0)

        try:
            self.action_input_panel = ActionInputPanel(self.completer_model, self.current_settings, self.register_map, parent=left_panel_widget)
            if not self.action_input_panel : raise RuntimeError("ActionInputPanel creation failed.")
            left_panel_layout.addWidget(self.action_input_panel)

            action_buttons_layout = QHBoxLayout()
            self.add_to_seq_button = QPushButton(constants.SEQ_ADD_BUTTON_TEXT, left_panel_widget)
            try: self.add_to_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowRight)); self.add_to_seq_button.setIconSize(QSize(16,16))
            except Exception as e_icon: print(f"Warning_SCT: Icon for add_to_seq_button: {e_icon}")
            action_buttons_layout.addWidget(self.add_to_seq_button)

            self.define_loop_button = QPushButton(constants.DEFINE_LOOP_BUTTON_TEXT, left_panel_widget)
            # Try to set a more loop-like icon (repeat/refresh)
            try:
                loop_icon = QApplication.style().standardIcon(QStyle.SP_BrowserReload)
                self.define_loop_button.setIcon(loop_icon)
                self.define_loop_button.setIconSize(QSize(18, 18))
            except Exception as e_icon:
                print(f"Warning_SCT: Icon for define_loop_button: {e_icon}")
            action_buttons_layout.addWidget(self.define_loop_button)

            # "Update Action" 버튼 추가
            self.update_action_button = QPushButton("Update Selected", left_panel_widget)
            try: self.update_action_button.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogApplyButton))
            except Exception as e_icon: print(f"Warning_SCT: Icon for update_action_button: {e_icon}")
            self.update_action_button.setEnabled(False) # 초기에는 비활성화
            action_buttons_layout.addWidget(self.update_action_button)

            left_panel_layout.addLayout(action_buttons_layout)

            # Stretch before SavedSequencePanel and Play/Stop buttons
            left_panel_layout.addStretch(1)

            print(f"DEBUG_SCT_LeftPanel: About to create SavedSequencePanel. self.sequence_io_manager is {self.sequence_io_manager} (type: {type(self.sequence_io_manager)}), self.saved_sequences_dir is {self.saved_sequences_dir}")
            self.saved_sequence_panel = SavedSequencePanel(self.sequence_io_manager, self.saved_sequences_dir, parent=left_panel_widget)
            if not self.saved_sequence_panel: raise RuntimeError("SavedSequencePanel creation failed.")
            left_panel_layout.addWidget(self.saved_sequence_panel)
            
            play_stop_button_layout = QHBoxLayout()
            self.play_seq_button = QPushButton(constants.SEQ_PLAY_BUTTON_TEXT, left_panel_widget)
            try: self.play_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_MediaPlay))
            except Exception as e_icon: print(f"Warning_SCT: Icon for play_seq_button: {e_icon}")
            
            self.stop_seq_button = QPushButton(constants.SEQ_STOP_BUTTON_TEXT, left_panel_widget)
            try: self.stop_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_MediaStop))
            except Exception as e_icon: print(f"Warning_SCT: Icon for stop_seq_button: {e_icon}")
            
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
            else: raise RuntimeError("Stop sequence button creation failed.")

            play_stop_button_layout.addWidget(self.play_seq_button)
            play_stop_button_layout.addWidget(self.stop_seq_button)
            left_panel_layout.addLayout(play_stop_button_layout)
            
            splitter_arg.addWidget(left_panel_widget) 
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_left_panel: {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False


    def _create_right_panel(self, splitter_arg: Optional[QSplitter]):
        print(f"DEBUG_SCT: Entered _create_right_panel. splitter_arg is {splitter_arg}. self._main_splitter (attribute) is {self._main_splitter}")
        if splitter_arg is None:
            print(f"ERROR_SCT: splitter_arg is None in _create_right_panel. Aborting. self._main_splitter is {self._main_splitter}")
            if self._ui_setup_successful : self._ui_setup_successful = False # 명시적으로 실패 처리
            return

        right_panel_widget = QWidget(self) 
        right_panel_layout = QVBoxLayout(right_panel_widget) 
        right_panel_layout.setSpacing(10)
        right_panel_layout.setContentsMargins(0,0,0,0)

        seq_list_label = QLabel(constants.SEQ_LIST_LABEL, right_panel_widget)
        right_panel_layout.addWidget(seq_list_label)

        try:
            self.sequence_list_widget = QTreeWidget(right_panel_widget)
            if self.sequence_list_widget:
                self.sequence_list_widget.setHeaderLabels(["Sequence Action / Details"])
                self.sequence_list_widget.setColumnCount(1)
                self.sequence_list_widget.setDragEnabled(True)
                self.sequence_list_widget.setAcceptDrops(True)
                self.sequence_list_widget.setDropIndicatorShown(True)
                self.sequence_list_widget.setDragDropMode(QAbstractItemView.InternalMove)
                self.sequence_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                self.sequence_list_widget.customContextMenuRequested.connect(self._show_tree_context_menu)
                # Add stylesheet for item padding and spacing
                self.sequence_list_widget.setStyleSheet("""
                    QTreeWidget::item {
                        padding-top: 4px;
                        padding-bottom: 4px;
                        border: 1px solid transparent; /* Optional: for spacing effect */
                    }
                    QTreeWidget::item:hover {
                        background-color: #e6f2ff; /* Light blue hover, adjust as needed */
                    }
                    QTreeWidget::item:selected {
                        background-color: #cce5ff; /* Slightly darker blue for selection */
                        color: black;
                    }
                """)
                # Increase header height if needed (optional)
                # self.sequence_list_widget.header().setMinimumSectionSize(30) 

                # Connect itemSelectionChanged to update loop variables for ActionInputPanel
                self.sequence_list_widget.itemSelectionChanged.connect(self._update_loop_variables_for_panel_on_selection)

        except Exception as e_treewidget:
            print(f"CRITICAL_ERROR_SCT: Exception during QTreeWidget creation: {e_treewidget}")
            self._ui_setup_successful = False
            return 

        if self.sequence_list_widget is None:
            print(f"CRITICAL_ERROR_SCT: QTreeWidget creation failed (is None).")
            self._ui_setup_successful = False
            return

        font_monospace_name = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        log_font_size = getattr(constants, 'LOG_FONT_SIZE', 10)
        self.sequence_list_widget.setFont(QFont(font_monospace_name, log_font_size))
        self.sequence_list_widget.setAlternatingRowColors(True)
        right_panel_layout.addWidget(self.sequence_list_widget)

        try:
            list_management_buttons_layout = QHBoxLayout()
            self.remove_from_seq_button = QPushButton(constants.SEQ_REMOVE_BUTTON_TEXT, right_panel_widget)
            try: self.remove_from_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon)); self.remove_from_seq_button.setIconSize(QSize(16,16))
            except Exception as e_icon: print(f"Warning_SCT: Icon for remove_from_seq_button: {e_icon}")
            list_management_buttons_layout.addWidget(self.remove_from_seq_button)

            self.clear_seq_button = QPushButton(constants.SEQ_CLEAR_BUTTON_TEXT, right_panel_widget)
            try: self.clear_seq_button.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogResetButton))
            except Exception as e_icon: print(f"Warning_SCT: Icon for clear_seq_button: {e_icon}")
            list_management_buttons_layout.addWidget(self.clear_seq_button)
            right_panel_layout.addLayout(list_management_buttons_layout)

            exec_log_label = QLabel(constants.SEQ_LOG_LABEL, right_panel_widget)
            right_panel_layout.addWidget(exec_log_label)
            self.execution_log_textedit = QTextEdit(right_panel_widget)
            self.execution_log_textedit.setReadOnly(True)
            self.execution_log_textedit.setFont(QFont(font_monospace_name, log_font_size))
            self.execution_log_textedit.setLineWrapMode(QTextEdit.NoWrap) 
            right_panel_layout.addWidget(self.execution_log_textedit)
            
            splitter_arg.addWidget(right_panel_widget) 
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_right_panel (after QTreeWidget creation): {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False

    def _connect_signals(self):
        if not self._ui_setup_successful:
            print("INFO_SCT: UI setup failed, skipping signal connections.")
            return

        if self.add_to_seq_button: self.add_to_seq_button.clicked.connect(self._add_item_from_action_panel)
        else: print("Error_SCT: add_to_seq_button is None, cannot connect.")
        
        if self.define_loop_button: self.define_loop_button.clicked.connect(self._add_new_loop_block_action_slot)
        else: print("Error_SCT: define_loop_button is None, cannot connect.")

        if self.update_action_button: self.update_action_button.clicked.connect(self._handle_update_selected_action)
        else: print("Error_SCT: update_action_button is None, cannot connect.")

        if self.play_seq_button: self.play_seq_button.clicked.connect(self.play_sequence)
        else: print("Error_SCT: play_seq_button is None, cannot connect.")

        if self.stop_seq_button: self.stop_seq_button.clicked.connect(self.request_stop_sequence)
        else: print("Error_SCT: stop_seq_button is None, cannot connect.")

        if self.clear_seq_button: self.clear_seq_button.clicked.connect(self.clear_sequence_list_and_log)
        else: print("Error_SCT: clear_seq_button is None, cannot connect.")

        if self.remove_from_seq_button: self.remove_from_seq_button.clicked.connect(self.remove_selected_item_with_warning)
        else: print("Error_SCT: remove_from_seq_button is None, cannot connect.")
        
        if self.saved_sequence_panel:
            self.saved_sequence_panel.load_sequence_to_editor_requested.connect(self._handle_load_saved_sequence)
            self.saved_sequence_panel.save_current_sequence_as_requested.connect(self._handle_save_current_sequence_as)
        else: print("Error_SCT: saved_sequence_panel is None, cannot connect its signals.")

        if self.sequence_list_widget:
            self.sequence_list_widget.customContextMenuRequested.connect(self._show_tree_context_menu)
            # self.sequence_list_widget.currentItemChanged.connect(self._handle_edit_action_item) # <-- 이 줄을 주석 처리 또는 삭제
            self.sequence_list_widget.itemDoubleClicked.connect(self._handle_edit_action_item) # 더블 클릭 시 편집 핸들러 연결
            # itemSelectionChanged는 이미 _update_loop_variables_for_panel_on_selection에 연결되어 있음 (유지)
            self.sequence_list_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)

    @pyqtSlot()
    def _add_item_from_action_panel(self):
        if not self._ui_setup_successful: 
            QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if not self.action_input_panel:
            QMessageBox.critical(self, "오류", "액션 입력 패널이 준비되지 않았습니다 (action_input_panel is None)."); return
        if self.sequence_list_widget is None:
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다 (sequence_list_widget is None)."); return

        action_data = self.action_input_panel.get_current_action_string_and_prefix()
        if action_data:
            _prefix, full_action_str, params_dict = action_data
            tree_item = QTreeWidgetItem(self.sequence_list_widget)
            tree_item.setText(0, full_action_str)
            self.action_input_panel.clear_input_fields() 

            # ActionInputPanel에서 가져온 정보로 SimpleActionItem 생성
            new_action_data: SimpleActionItem = {
                "item_id": f"action_{datetime.now().timestamp()}", # 고유 ID 생성
                "action_type": _prefix,
                "parameters": params_dict,
                "display_name": full_action_str
            }
            tree_item.setData(0, Qt.UserRole, new_action_data)

    @pyqtSlot()
    def _add_new_loop_block_action_slot(self):
        # 사용자가 "Define Loop" 버튼을 클릭했을 때 호출됩니다.
        # 현재 선택된 아이템을 기준으로 새 루프 블록을 추가할 위치를 결정합니다.
        target_parent = None
        insert_after = None
        if self.sequence_list_widget:
            current_selection = self.sequence_list_widget.currentItem()
            if current_selection:
                # 선택된 아이템이 루프면 그 안에, 아니면 그 다음에 추가
                current_data = current_selection.data(0, Qt.UserRole)
                if isinstance(current_data, dict) and current_data.get("action_type") == "Loop":
                    target_parent = current_selection
                else:
                    insert_after = current_selection 
            # 선택된 아이템이 없으면 최상위에 추가 (insert_after=None, target_parent=None)
        self._add_new_loop_block_action(target_parent_item=target_parent, insert_after_item=insert_after)

    def _add_new_loop_block_action(self, target_parent_item: Optional[QTreeWidgetItem] = None, insert_after_item: Optional[QTreeWidgetItem] = None):
        if not self.sequence_list_widget: return
        loop_dialog = LoopDefinitionDialog(parent=self)
        if loop_dialog.exec_() == QDialog.Accepted:
            new_loop_data = loop_dialog.get_loop_parameters()
            if new_loop_data:
                loop_var = new_loop_data.get("loop_variable_name")
                display_name = new_loop_data.get("display_name", "")
                if display_name:
                    loop_title = f"{display_name} : {loop_var}" if loop_var else display_name
                else:
                    loop_title = f"Loop : {loop_var}" if loop_var else "Loop"
                new_loop_item = QTreeWidgetItem()
                new_loop_item.setText(0, loop_title)
                new_loop_item.setData(0, Qt.UserRole, new_loop_data)

                if target_parent_item:
                    if self._is_parent_allowed_for_child(target_parent_item):
                        target_parent_item.addChild(new_loop_item)
                        target_parent_item.setExpanded(True)
                    else:
                        QMessageBox.warning(self, "추가 불가", "Loop/폴더 노드에만 자식 항목을 추가할 수 있습니다.")
                        return
                else:
                    self.sequence_list_widget.addTopLevelItem(new_loop_item)

                self.action_input_panel.clear_input_fields()

    @pyqtSlot()
    def _handle_define_loop(self):
        # 이 함수는 이제 Define Loop 버튼의 직접적인 핸들러가 아님.
        # _add_new_loop_block_action_slot 을 통해 호출됨.
        # 기존 버튼의 동작을 유지하려면, 최상위 레벨에 추가하도록 호출
        self._add_new_loop_block_action(target_parent_item=None, insert_after_item=None)
        return 

    def _add_items_to_tree(self, sequence_items: List[SequenceItem], parent_tree_item: Optional[QTreeWidgetItem] = None, sequence_display_name: Optional[str] = None):
        """ SequenceItem 리스트를 QTreeWidget에 아이템으로 추가 (재귀적) """
        if not self.sequence_list_widget: return

        # --- 새 기능: 최상위에 불러올 때는 폴더 아이콘과 제목 노드 추가 ---
        if sequence_display_name is not None:
            # 폴더 아이콘이 있는 노드 생성 (항상 parent_tree_item 아래에 추가)
            parent = parent_tree_item if parent_tree_item else self.sequence_list_widget
            parent_item = QTreeWidgetItem(parent)
            parent_item.setText(0, sequence_display_name)
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsDropEnabled) # 폴더 노드는 드롭 비허용(선택적)
            try:
                app = QApplication.instance()
                if app:
                    folder_icon = app.style().standardIcon(QStyle.SP_DirIcon)
                    parent_item.setIcon(0, folder_icon)
            except Exception as e:
                print(f"Warning: Could not set folder icon: {e}")
            parent_item.setExpanded(True)
            for item_data in sequence_items:
                self._add_items_to_tree([item_data], parent_tree_item=parent_item)
            self._update_loop_variables_for_action_panel(self.sequence_list_widget.currentItem())
            return
        target_widget = parent_tree_item if parent_tree_item else self.sequence_list_widget
        for item_data in sequence_items:
            # Loop 노드는 변수명 포함해서 표시
            if item_data.get("action_type") == "Loop":
                loop_var = item_data.get("loop_variable_name")
                display_name = item_data.get("display_name", "")
                if display_name:
                    loop_title = f"{display_name} : {loop_var}" if loop_var else display_name
                else:
                    loop_title = f"Loop : {loop_var}" if loop_var else "Loop"
                tree_item = QTreeWidgetItem(target_widget)
                tree_item.setText(0, loop_title)
                tree_item.setData(0, Qt.UserRole, item_data)
                looped_actions = item_data.get("looped_actions", [])
                if looped_actions:
                    self._add_items_to_tree(looped_actions, tree_item)
                tree_item.setExpanded(True)
            else:
                # 자식 추가 시 부모가 Loop/폴더가 아니면 차단
                if parent_tree_item and not self._is_parent_allowed_for_child(parent_tree_item):
                    QMessageBox.warning(self, "추가 불가", "Loop/폴더 노드에만 자식 항목을 추가할 수 있습니다.")
                    continue
                item_display_name = item_data.get("display_name", item_data.get("action_type", "Unknown Action"))
                tree_item = QTreeWidgetItem(target_widget)
                tree_item.setText(0, item_display_name)
                tree_item.setData(0, Qt.UserRole, item_data)
        self._update_loop_variables_for_action_panel(self.sequence_list_widget.currentItem())

    @pyqtSlot(str)
    def _handle_save_current_sequence_as(self, requested_name_without_ext: str):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if self.sequence_list_widget is None or self.saved_sequence_panel is None:
            QMessageBox.critical(self, "오류", "필수 UI 요소(시퀀스 목록 또는 저장 패널)가 초기화되지 않았습니다."); return
        
        current_items_data = self._get_sequence_data_from_tree(self.sequence_list_widget.invisibleRootItem())
        if not current_items_data:
            QMessageBox.information(self, "시퀀스 저장", "저장할 아이템이 시퀀스 목록에 없습니다."); return
        
        if self.sequence_io_manager.save_sequence(sequence_name_no_ext=requested_name_without_ext, 
                                                 sequence_items=current_items_data, 
                                                 overwrite=True): 
            QMessageBox.information(self, "저장 성공", f"시퀀스가 '{requested_name_without_ext}{constants.SEQUENCE_FILE_EXTENSION}' 이름으로 저장되었습니다.")
            if self.saved_sequence_panel: 
                self.saved_sequence_panel.load_saved_sequences()
            # 저장 후 루프 변수 업데이트
            loop_vars = self._get_active_loop_variables(self.sequence_list_widget.invisibleRootItem())
            self.action_input_panel.update_loop_variables(loop_vars)
        else:
            QMessageBox.warning(self, "저장 실패", f"시퀀스 '{requested_name_without_ext}' 저장에 실패했습니다.")

    def _get_sequence_data_from_tree(self, parent_item: QTreeWidgetItem) -> List[SequenceItem]:
        """ QTreeWidget으로부터 계층적인 SequenceItem 데이터 리스트를 추출 (재귀적) """
        items_data: List[SequenceItem] = []
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            item_data = child_item.data(0, Qt.UserRole) # 저장된 SequenceItem 딕셔너리 가져오기
            if isinstance(item_data, dict):
                # LoopActionItem의 경우, looped_actions도 재귀적으로 추출
                if item_data.get("action_type") == "Loop":
                    # Ensure all loop parameters are preserved or reconstructed if necessary
                    # from the dialog or its representation in the tree item's data.
                    # The current item_data should already be the full LoopActionItem.
                    # We just need to recursively get its children for `looped_actions`.
                    current_loop_data = cast(LoopActionItem, item_data.copy()) # Make a copy to modify
                    current_loop_data["looped_actions"] = self._get_sequence_data_from_tree(child_item)
                    items_data.append(current_loop_data)
                else:
                    items_data.append(cast(SimpleActionItem, item_data)) # type: ignore
        return items_data

    @pyqtSlot()
    def remove_selected_item_with_warning(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        if self.sequence_list_widget is None: 
            QMessageBox.critical(self, "오류", "시퀀스 목록 위젯이 유효하지 않습니다."); return
        
        selected_tree_items = self.sequence_list_widget.selectedItems()
        if not selected_tree_items:
            QMessageBox.information(self, "삭제 오류", "삭제할 아이템을 목록에서 선택하세요."); return

        current_item = selected_tree_items[0]
        item_data = current_item.data(0, Qt.UserRole) # SequenceItem 데이터 가져오기
        item_text_for_warning = current_item.text(0)

        warn_loop_structure = False
        if isinstance(item_data, dict) and item_data.get("action_type") == "Loop":
            if item_data.get("looped_actions"): # 루프 내부에 액션이 있으면 경고
                warn_loop_structure = True
        
        if warn_loop_structure:
            reply = QMessageBox.question(self, "루프 구조 경고",
                                         f"선택된 아이템 '{item_text_for_warning}'은(는) Loop 블록이며 내부에 다른 액션을 포함할 수 있습니다.\n"
                                         "삭제 시 내부의 모든 액션도 함께 삭제됩니다. 계속하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        parent_of_selected = current_item.parent()
        if parent_of_selected: # 자식 아이템인 경우
            parent_of_selected.removeChild(current_item)
        else: # 최상위 아이템인 경우
            self.sequence_list_widget.takeTopLevelItem(self.sequence_list_widget.indexOfTopLevelItem(current_item))
        
        # TODO: 내부 데이터 모델 (List[SequenceItem])에서도 해당 아이템 삭제하는 로직 필요
        #       (현재는 UI에서만 제거. self.sequence_items와 같은 리스트가 있다면 거기서도 제거해야 함)
        #       또는, 항상 QTreeWidget을 기준으로 데이터를 다시 읽어오는 방식 사용.

    @pyqtSlot()
    def clear_sequence_list_and_log(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        
        if self.sequence_list_widget is not None:
            if self.sequence_list_widget.topLevelItemCount() > 0:
                reply = QMessageBox.question(self, "목록 초기화",
                                             "정말로 현재 시퀀스 목록 전체를 지우시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
            self.sequence_list_widget.clear()
        
        if self.execution_log_textedit is not None:
            self.execution_log_textedit.clear()
            
        QMessageBox.information(self, "초기화 완료", "시퀀스 목록 및 실행 로그가 초기화되었습니다.")
        self._update_loop_variables_for_action_panel(None) # 목록이 비었으므로 루프 변수도 초기화

    @pyqtSlot()
    def play_sequence(self):
        if not self._ui_setup_successful: QMessageBox.critical(self, "오류", "탭 UI가 올바르게 초기화되지 않아 작업을 수행할 수 없습니다."); return
        
        if self.sequence_player_thread and self.sequence_player_thread.isRunning():
            QMessageBox.information(self, constants.MSG_TITLE_INFO, "시퀀스가 이미 실행 중입니다. 먼저 중단해주세요."); return
        
        if self.sequence_list_widget is None or self.sequence_list_widget.topLevelItemCount() == 0: # count() -> topLevelItemCount()
            QMessageBox.information(self, constants.MSG_TITLE_INFO, constants.MSG_SEQUENCE_EMPTY); return
        
        if self.execution_log_textedit: self.execution_log_textedit.clear() 
        
        items_to_play = self._get_sequence_data_from_tree(self.sequence_list_widget.invisibleRootItem()) # QTreeWidget에서 데이터 가져오기
        
        sample_num = constants.DEFAULT_SAMPLE_NUMBER 
        if self.main_window_ref and hasattr(self.main_window_ref, 'get_current_sample_number'):
            sample_num = self.main_window_ref.get_current_sample_number()
        
        self.sequence_player = SequencePlayer(
            items_to_play, self.current_settings, self.register_map, 
            self.i2c_device, self.multimeter, self.sourcemeter, self.chamber,
            sample_num, self.main_window_ref, parent=None 
        )
        
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
            if self.execution_log_textedit: 
                self.execution_log_textedit.append("--- 시퀀스 중단 요청됨. 현재 단계 완료 후 중단됩니다... ---")
        else:
            if self.play_seq_button: self.play_seq_button.setEnabled(True)
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
            self.sequence_status_changed_signal.emit(False)


    @pyqtSlot(str)
    def _handle_log_message(self, message: str):
        """시퀀스 플레이어로부터 로그 메시지를 수신하여 로그 창에 표시합니다."""
        self.log_message(message)

    def log_message(self, message: str):
        """로그 메시지를 UI의 로그 창에 표시합니다."""
        if self.execution_log_textedit:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.execution_log_textedit.append(f"[{timestamp}] {message}")
            # 로그 창을 항상 최신 내용이 보이도록 스크롤
            self.execution_log_textedit.verticalScrollBar().setValue(
                self.execution_log_textedit.verticalScrollBar().maximum()
            )

    @pyqtSlot(bool, str)
    def _handle_sequence_finished(self, success_flag: bool, message: str):
        if self.execution_log_textedit: 
            self.execution_log_textedit.append(f"--- {message} ---")
            self.execution_log_textedit.ensureCursorVisible()

        msg_box_func = QMessageBox.information if success_flag else QMessageBox.warning
        msg_box_func(self, "시퀀스 실행 결과", f"시퀀스 실행이 {'완료' if success_flag else '실패 또는 중단'}되었습니다.\n상세: {message}")
        

    @pyqtSlot()
    def _on_thread_actually_finished(self):
        print("Info_SCT: SequencePlayer QThread actually finished.")
        self.sequence_player = None 
        self.sequence_player_thread = None 

        if self.play_seq_button: self.play_seq_button.setEnabled(True)
        if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
        self.sequence_status_changed_signal.emit(False) 
        print("Info_SCT: Player and Thread references cleared, UI state updated.")

    @pyqtSlot()
    def _on_player_destroyed(self):
        print("Info_SCT: SequencePlayer object has been destroyed.")

    def _parse_sequence_item(self, item_text: str) -> Tuple[Optional[str], Dict[str, str]]:
        """Parses a single sequence item string into action type and parameters dict."""
        try:
            item_text_stripped = item_text.lstrip() 
            action_type_str, params_str = item_text_stripped.split(":", 1)
            action_type_str = action_type_str.strip()
            params_dict = {}
            if params_str.strip():
                param_pairs = params_str.split(';')
                for pair in param_pairs:
                    if '=' in pair: 
                        key, value = pair.split('=', 1)
                        params_dict[key.strip()] = value.strip()
            return action_type_str, params_dict
        except ValueError: 
            # Log this error or handle as appropriate for the controller tab context
            problematic_item_text = item_text_stripped if "item_text_stripped" in locals() else item_text
            self.log_message(f"Error: Failed to parse sequence item in controller: '{problematic_item_text}'")
            return None, {}

    def update_hardware_instances(self, 
                                  i2c_dev: Optional[I2CDevice], 
                                  mm_dev: Optional[Multimeter], 
                                  sm_dev: Optional[Sourcemeter], 
                                  ch_dev: Optional[Chamber]):
        self.i2c_device = i2c_dev
        self.multimeter = mm_dev
        self.sourcemeter = sm_dev
        self.chamber = ch_dev
        print("INFO_SCT: Hardware instances updated in SequenceControllerTab.")

    def update_register_map(self, new_register_map: Optional[RegisterMap]):
        self.register_map = new_register_map
        if self.completer_model: 
            field_ids = self.register_map.get_all_field_ids() if self.register_map else []
            self.completer_model.setStringList(field_ids)
        
        if self.action_input_panel: 
            self.action_input_panel.update_completer_model(self.completer_model)
            self.action_input_panel.update_register_map(self.register_map)
        print("INFO_SCT: RegisterMap updated in SequenceControllerTab.")

    def update_settings(self, new_settings: Dict[str, Any]):
        self.current_settings = new_settings if new_settings is not None else {}
        if self.action_input_panel: 
            self.action_input_panel.update_settings(self.current_settings)
        print("INFO_SCT: Settings updated in SequenceControllerTab.")

    # --- QTreeWidget Drag and Drop Handling --- #
    def dragEnterEvent(self, event: QDragEnterEvent):
        # 여기서 event.mimeData()를 확인하여 내부 드래그인지, 
        # 또는 다른 타입의 데이터인지 확인할 수 있습니다.
        # 현재는 QAbstractItemView.InternalMove를 사용하므로, 
        # 프레임워크가 어느 정도 처리해줍니다.
        if event.source() == self.sequence_list_widget: # 같은 위젯 내의 드래그만 허용
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        # 드롭 가능한 위치인지 시각적으로 피드백을 줄 수 있습니다.
        # 예: 특정 아이템 위로 드래그 시, 해당 아이템의 스타일 변경
        # 현재는 기본 동작에 맡깁니다.
        if event.source() == self.sequence_list_widget:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        # 드래그&드롭으로 아이템 이동 시 부모 타입 체크
        if not self.sequence_list_widget: return
        target_pos = event.pos()
        target_item = self.sequence_list_widget.itemAt(target_pos)
        # Loop/폴더만 자식 허용
        if target_item is not None and not self._is_parent_allowed_for_child(target_item):
            QMessageBox.warning(self, "이동 불가", "Loop/폴더 노드에만 자식 항목을 둘 수 있습니다.")
            event.ignore()
            return
        # 드래그된 아이템이 자식이 될 때도 체크
        selected_items = self.sequence_list_widget.selectedItems()
        if selected_items:
            dragged_item = selected_items[0]
            parent_of_dragged = dragged_item.parent()
            if parent_of_dragged and not self._is_parent_allowed_for_child(parent_of_dragged):
                QMessageBox.warning(self, "이동 불가", "Loop/폴더 노드에만 자식 항목을 둘 수 있습니다.")
                event.ignore()
                return
        super(type(self.sequence_list_widget), self.sequence_list_widget).dropEvent(event)
        QTimer.singleShot(0, lambda: self._update_loop_variables_for_action_panel(self.sequence_list_widget.currentItem()))

    # --- End Drag and Drop --- #

    # --- Context Menu --- #
    def _show_tree_context_menu(self, position: QPoint):
        if not self.sequence_list_widget: return
        item_at_pos = self.sequence_list_widget.itemAt(position)
        menu = QMenu(self.sequence_list_widget)

        if item_at_pos: # 아이템 위에서 우클릭
            self.sequence_list_widget.setCurrentItem(item_at_pos) # Ensure item is selected
            item_data = item_at_pos.data(0, Qt.UserRole)
            is_loop_item = isinstance(item_data, dict) and item_data.get("action_type") == "Loop"
            
            edit_text = "Edit Loop Parameters..." if is_loop_item else "Edit Action..."
            act_edit = menu.addAction(QIcon.fromTheme("document-edit"), edit_text)
            act_delete = menu.addAction(QIcon.fromTheme("edit-delete"), "Delete Item")
            menu.addSeparator()
            
            if is_loop_item:
                act_add_inside_loop = menu.addAction("Add Action Inside This Loop")
                act_add_inside_loop.triggered.connect(lambda checked=False, current_loop_item=item_at_pos: self._handle_add_action_to_loop(current_loop_item))
            
            act_add_action_after = menu.addAction("Add New Action After This")
            act_add_action_after.triggered.connect(lambda checked=False, current_item_ref=item_at_pos: self._handle_add_action_here(current_item_ref, insert_after=True))
            act_add_loop_after = menu.addAction("Add New Loop Block After This")
            act_add_loop_after.triggered.connect(lambda checked=False, current_item_ref=item_at_pos: self._add_new_loop_block_action(insert_after_item=current_item_ref))
            
            chosen_action = menu.exec_(self.sequence_list_widget.mapToGlobal(position))
            if chosen_action == act_edit: 
                self._handle_edit_action_item(item_at_pos)
                if self.update_action_button: self.update_action_button.setEnabled(True) # Enable update button
            elif chosen_action == act_delete: self.remove_selected_item_with_warning()
            # Context menu action can change selection or structure, so update loop vars
            self._update_loop_variables_for_action_panel(self.sequence_list_widget.currentItem())
        else: # 빈 공간에서 우클릭
            if self.update_action_button: self.update_action_button.setEnabled(False) # Disable update button
            act_add_top_action = menu.addAction("Add New Action (Top Level)")
            act_add_top_loop = menu.addAction("Add New Loop Block (Top Level)")
            chosen_action = menu.exec_(self.sequence_list_widget.mapToGlobal(position))
            if chosen_action == act_add_top_action: self._handle_add_action_here(None, insert_after=False)
            elif chosen_action == act_add_top_loop: self._add_new_loop_block_action(target_parent_item=None, insert_after_item=None)
            # Adding new top-level items, context for loop vars might be None or based on where it lands if list isn't empty
            self._update_loop_variables_for_action_panel(self.sequence_list_widget.currentItem() if self.sequence_list_widget.topLevelItemCount() > 0 else None)

    def _handle_edit_action_item(self, item: Optional[QTreeWidgetItem]): # item can be None if called by currentItemChanged
        if not item: 
            if self.update_action_button: self.update_action_button.setEnabled(False) # No item selected, disable button
            return
        
        item_text = item.text(0)
        item_data = item.data(0, Qt.UserRole)
        print(f"DEBUG_SCT_Edit: Editing item: '{item_text}', Data: {item_data}, Type of data: {type(item_data)}") # 로깅 추가

        if not isinstance(item_data, dict) or item_data.get("action_type") == "Loop":
            QMessageBox.warning(self, "Update Action", "Selected item is a Loop or has invalid data. Cannot update with simple action panel.")
            if self.update_action_button: self.update_action_button.setEnabled(False)
            return

        # 업데이트 전, 편집 대상 아이템의 컨텍스트에 맞는 루프 변수 목록을 패널에 설정
        self._update_loop_variables_for_action_panel(item)

        action_data_tuple = self.action_input_panel.get_current_action_string_and_prefix()
        if not action_data_tuple:
            QMessageBox.warning(self, "Update Action", "No action data defined in the input panel to update with.")
            return
        
        prefix, full_str, params = action_data_tuple
        
        updated_action_data: SimpleActionItem = {
            "item_id": item_data.get("item_id", f"updated_{datetime.now().timestamp()}"), # 기존 ID 유지 또는 새로 생성
            "action_type": prefix,
            "parameters": params,
            "display_name": full_str
        }
        
        item.setText(0, full_str) # UI 표시 업데이트
        item.setData(0, Qt.UserRole, updated_action_data) # 저장된 데이터 업데이트
        self.log_message(f"Action '{full_str}' (ID: {updated_action_data['item_id']}) updated.")
        self.action_input_panel.clear_input_fields()
        if self.update_action_button: self.update_action_button.setEnabled(False) # 업데이트 후 비활성화

    def _handle_add_action_to_loop(self, loop_item: QTreeWidgetItem):
        if not self.action_input_panel or not loop_item: return
        action_item_data = self.action_input_panel.get_current_action_as_simple_item()
        if not action_item_data:
            self.log_message("Define an action in the panel first to add it to the loop."); return

        loop_data = loop_item.data(0, Qt.UserRole)
        if not loop_data or loop_data.get("action_type") != "Loop":
            self.log_message("Selected item is not a valid loop."); return
        
        self._add_items_to_tree([action_item_data], parent_tree_item=loop_item)
        
        self.log_message(f"Action '{action_item_data.get('display_name')}' added to loop '{loop_data.get('display_name')}'.")
        self.action_input_panel.clear_input_fields()

    def _handle_add_action_here(self, current_item: Optional[QTreeWidgetItem], insert_after: bool = False):
        """ 현재 선택된 아이템과 같은 레벨에 새 액션 추가 """ 
        if not self.action_input_panel or not self.sequence_list_widget: return
        
        action_data_tuple = self.action_input_panel.get_current_action_string_and_prefix()
        if action_data_tuple:
            prefix, full_str, params = action_data_tuple
            new_action_item_data: SimpleActionItem = {
                "item_id": f"item_{datetime.now().timestamp()}",
                "action_type": prefix,
                "parameters": params,
                "display_name": full_str
            }

            parent_of_current = current_item.parent() if current_item else None
            target_parent_for_new_item = parent_of_current if parent_of_current else self.sequence_list_widget.invisibleRootItem()

            new_tree_item = QTreeWidgetItem()
            new_tree_item.setText(0, full_str)
            new_tree_item.setData(0, Qt.UserRole, new_action_item_data)

            if parent_of_current:
                if self._is_parent_allowed_for_child(parent_of_current):
                    current_index_in_parent = parent_of_current.indexOfChild(current_item)
                    parent_of_current.insertChild(current_index_in_parent + 1, new_tree_item)
                else:
                    QMessageBox.warning(self, "추가 불가", "Loop/폴더 노드에만 자식 항목을 추가할 수 있습니다.")
                    return
            else:
                current_top_level_index = self.sequence_list_widget.indexOfTopLevelItem(current_item)
                self.sequence_list_widget.insertTopLevelItem(current_top_level_index + 1, new_tree_item)
            
            self.log_message(f"Action '{full_str}' added near '{current_item.text(0)}'.")
            self.action_input_panel.clear_input_fields()
        else:
            QMessageBox.warning(self, "Add Action", "No action defined in the input panel.")

    @pyqtSlot()
    def _handle_update_selected_action(self):
        if not self.sequence_list_widget or not self.action_input_panel:
            QMessageBox.critical(self, "Error", "UI components not ready for update.")
            return

        selected_item = self.sequence_list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "Update Action", "Please select an action item in the tree to update.")
            return
        
        current_item_data = selected_item.data(0, Qt.UserRole)
        if not isinstance(current_item_data, dict) or current_item_data.get("action_type") == "Loop":
            QMessageBox.warning(self, "Update Action", "Selected item is a Loop or has invalid data. Cannot update with simple action panel.")
            return

        # 업데이트 전, 편집 대상 아이템의 컨텍스트에 맞는 루프 변수 목록을 패널에 설정
        self._update_loop_variables_for_action_panel(selected_item)

        action_data_tuple = self.action_input_panel.get_current_action_string_and_prefix()
        if not action_data_tuple:
            QMessageBox.warning(self, "Update Action", "No action data defined in the input panel to update with.")
            return
        
        prefix, full_str, params = action_data_tuple
        
        updated_action_data: SimpleActionItem = {
            "item_id": current_item_data.get("item_id", f"updated_{datetime.now().timestamp()}"), # 기존 ID 유지 또는 새로 생성
            "action_type": prefix,
            "parameters": params,
            "display_name": full_str
        }
        
        selected_item.setText(0, full_str) # UI 표시 업데이트
        selected_item.setData(0, Qt.UserRole, updated_action_data) # 저장된 데이터 업데이트
        self.log_message(f"Action '{full_str}' (ID: {updated_action_data['item_id']}) updated.")
        self.action_input_panel.clear_input_fields()
        if self.update_action_button: self.update_action_button.setEnabled(False) # 업데이트 후 비활성화

    # --- New method for explicit sub-tab control --- #
    def set_instrument_tab_enabled(self, instrument_type: str, enabled: bool):
        if self.action_input_panel and hasattr(self.action_input_panel, 'enable_instrument_sub_tab'):
            self.action_input_panel.enable_instrument_sub_tab(instrument_type, enabled)
            print(f"DEBUG_SCT: Called ActionInputPanel.enable_instrument_sub_tab for {instrument_type} = {enabled}")
        else:
            print(f"ERROR_SCT: ActionInputPanel or its enable_instrument_sub_tab method not found.")

    def _update_loop_variables_for_panel_on_selection(self):
        """Called when the selection in the QTreeWidget changes."""
        selected_items = self.sequence_list_widget.selectedItems()
        current_tree_item = selected_items[0] if selected_items else None
        self._update_loop_variables_for_action_panel(current_tree_item)

    def _get_active_loop_variables(self, tree_item: Optional[QTreeWidgetItem]) -> List[str]:
        """ 현재 선택된 아이템의 컨텍스트에서 사용 가능한 모든 루프 변수 이름을 수집합니다. """
        active_vars = []
        parent = tree_item
        while parent:
            parent_data = parent.data(0, Qt.UserRole)
            if isinstance(parent_data, dict) and parent_data.get("action_type") == "Loop":
                loop_var_name = parent_data.get("loop_variable_name")
                if loop_var_name and loop_var_name not in active_vars:
                    active_vars.append(loop_var_name)
            parent = parent.parent()
        # The list should be from outermost loop to innermost, if order matters for user display preference
        # If not, the current order (innermost to outermost) is fine for the model.
        # To reverse for display: active_vars.reverse()
        return active_vars

    def _update_loop_variables_for_action_panel(self, current_item_context: Optional[QTreeWidgetItem]):
        """특정 트리 아이템 컨텍스트에 따라 ActionInputPanel의 루프 변수 목록을 업데이트합니다."""
        if self.action_input_panel:
            loop_vars = self._get_active_loop_variables(current_item_context)
            self.action_input_panel.update_loop_variables(loop_vars)

    # --- End Context Menu --- #

    @pyqtSlot(list, str)
    def _handle_load_saved_sequence(self, sequence_items: List[SequenceItem], display_name: str):
        # 기존 트리를 clear하지 않고, 선택된 폴더/루프 노드 아래에 추가, 없으면 최상위에 append
        parent_item = None
        if self.sequence_list_widget:
            selected_items = self.sequence_list_widget.selectedItems()
            if selected_items:
                candidate = selected_items[0]
                if self._is_parent_allowed_for_child(candidate):
                    parent_item = candidate
        self._add_items_to_tree(sequence_items, parent_tree_item=parent_item, sequence_display_name=display_name)

    def _is_parent_allowed_for_child(self, parent_item: QTreeWidgetItem) -> bool:
        # 폴더 노드: UserRole 데이터가 없고 아이콘이 폴더
        item_data = parent_item.data(0, Qt.UserRole)
        if item_data is None:
            # 폴더 노드(시퀀스 제목)로 간주
            return True
        if isinstance(item_data, dict) and item_data.get("action_type") == "Loop":
            return True
        return False

    def _on_tree_selection_changed(self):
        if not self.sequence_list_widget or not self.update_action_button:
            return
        selected = self.sequence_list_widget.selectedItems()
        if selected and isinstance(selected[0].data(0, Qt.UserRole), dict):
            item_data = selected[0].data(0, Qt.UserRole)
            if item_data.get('action_type') != 'Loop':
                self.update_action_button.setEnabled(True)
                return
        self.update_action_button.setEnabled(False)