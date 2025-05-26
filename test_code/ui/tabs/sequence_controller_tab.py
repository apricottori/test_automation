import os
import json
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QTextEdit, QSplitter, QLabel, QMessageBox, QListWidgetItem,
    QMenu, QAction, QInputDialog, QCompleter, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle, QApplication, QDialog, QDataWidgetMapper
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QModelIndex, QSize, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QBrush, QPen

from core import constants
from core.sequence_player import SequencePlayer
from core.sequence_io_manager import SequenceIOManager
from ui.widgets.action_input_panel import ActionInputPanel
from ui.widgets.saved_sequence_panel import SavedSequencePanel
from ui.dialogs.loop_definition_dialog import LoopDefinitionDialog


if TYPE_CHECKING:
    from main_window import RegMapWindow
    from core.register_map_backend import RegisterMap
    from PyQt5.QtCore import QStringListModel


# Custom delegate to draw a horizontal line for LOOP_END
class SequenceListItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QIcon.painter, option: QStyleOptionViewItem, index: QModelIndex):
        super().paint(painter, option, index)
        item_data = index.data(Qt.UserRole) # Get the full dictionary
        if isinstance(item_data, dict):
            action_type = item_data.get(constants.SequenceParameterKey.ACTION_TYPE.value, {}).get('type')
            if action_type == constants.SequenceActionType.LOOP_END.value:
                painter.save()
                pen = QPen(option.palette.color(QPalette.Mid)) # Use a color from the palette
                pen.setWidth(1)
                painter.setPen(pen)
                # Draw line slightly above the bottom of the item
                y = option.rect.bottom() - 2
                painter.drawLine(option.rect.left() + 5, y, option.rect.right() - 5, y)
                painter.restore()

class SequenceControllerTab(QWidget):
    new_measurement_signal = pyqtSignal(str, object, str, dict) # variable_name, value, sample_number, conditions
    sequence_status_changed_signal = pyqtSignal(bool) # is_running

    def __init__(self,
                 parent: Optional[QWidget] = None,
                 register_map_instance: Optional['RegisterMap'] = None,
                 settings_instance: Optional[Dict[str, Any]] = None,
                 completer_model_instance: Optional['QStringListModel'] = None,
                 i2c_device_instance: Optional[Any] = None,
                 multimeter_instance: Optional[Any] = None,
                 sourcemeter_instance: Optional[Any] = None,
                 chamber_instance: Optional[Any] = None,
                 main_window_ref: Optional['RegMapWindow'] = None
                 ):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        self.register_map = register_map_instance
        self.current_settings = settings_instance if settings_instance is not None else {}
        self.completer_model = completer_model_instance
        self.i2c_device = i2c_device_instance
        self.multimeter = multimeter_instance
        self.sourcemeter = sourcemeter_instance
        self.chamber = chamber_instance

        self._ui_setup_successful: bool = True # UI 생성 성공 여부 플래그

        # UI 멤버 변수 선언
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
        
        self.sequence_player_thread: Optional[QThread] = None
        self.sequence_player: Optional[SequencePlayer] = None
        
        try:
            self.sequence_io_manager = SequenceIOManager()
            self.saved_sequences_dir: str = self._setup_saved_sequences_directory()

            # SequenceControllerTab 자체의 메인 레이아웃 설정 (단 한번만!)
            main_container_layout = QVBoxLayout(self) # self를 부모로 전달하여 자동 레이아웃 설정
            main_container_layout.setContentsMargins(8, 10, 8, 8)

            # _setup_main_layout에서 스플리터 등을 main_container_layout에 추가
            self._setup_main_layout(main_container_layout)

            if self._ui_setup_successful:
                self._create_left_panel()
            if self._ui_setup_successful: # 왼쪽 패널 생성 성공 시에만 오른쪽 패널 생성 시도
                self._create_right_panel()
            
            if not self._ui_setup_successful:
                self._show_ui_creation_error_state()
            else:
                self._connect_signals()
                self._update_button_states()
                if self.saved_sequence_panel:
                    self.saved_sequence_panel.refresh_sequence_list()

        except Exception as e:
            self._ui_setup_successful = False
            print(f"CRITICAL_ERROR_SCT: Unhandled exception during SequenceControllerTab __init__: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            # __init__에서 발생한 예외는 _show_ui_creation_error_state를 직접 호출해야 할 수 있음
            # 하지만 이 경우, self의 레이아웃이 이미 설정되었거나 부분적으로 설정되었을 수 있어 주의 필요
            try:
                self._show_ui_creation_error_state()
            except Exception as final_except: # 오류 처리 중 또 다른 오류 발생 시
                 # 이 시점에서는 print 외에 안전하게 할 수 있는 것이 거의 없음
                 print(f"CRITICAL_ERROR_SCT: Exception during _show_ui_creation_error_state from __init__ catch block: {type(final_except).__name__} - {final_except}")
                 # 최소한의 오류 메시지라도 표시 시도 (QMessageBox는 QApplication이 필요)
                 if QApplication.instance():
                     QMessageBox.critical(self, "치명적 UI 오류", f"시퀀스 탭 초기화 중 연속 오류 발생.\n{e}\nTHEN\n{final_except}")
                 else:
                     print(f"CRITICAL_ERROR_SCT: Final attempt to set error UI failed: {final_except}")

    def _show_ui_creation_error_state(self):
        # This method is called when _ui_setup_successful is False.
        # The widget might be in an unstable state. Avoid complex layout manipulations.
        print("DEBUG_SCT: Entering _show_ui_creation_error_state")

        # Attempt to clear existing children more simply if a layout exists
        current_layout = self.layout()
        if current_layout is not None:
            print(f"DEBUG_SCT: _show_ui_creation_error_state - Current layout is {current_layout}, attempting to clear children.")
            # Remove all widgets from the layout. The layout itself will be replaced.
            while current_layout.count():
                item = current_layout.takeAt(0)
                if item is None:
                    print("DEBUG_SCT: _show_ui_creation_error_state - takeAt(0) returned None, breaking loop.")
                    break
                widget = item.widget()
                if widget and widget is not self: # Avoid reparenting self to None
                    widget.setParent(None)
                    widget.deleteLater()
                else: 
                    layout_item = item.layout()
                    if layout_item:
                        print(f"DEBUG_SCT: _show_ui_creation_error_state - Clearing sub-layout {layout_item}")
                        while layout_item.count() > 0:
                            sub_item = layout_item.takeAt(0)
                            if sub_item.widget() and sub_item.widget() is not self:
                                sub_item.widget().setParent(None)
                                sub_item.widget().deleteLater()
                            elif sub_item.layout():
                                print(f"DEBUG_SCT: _show_ui_creation_error_state - Deleting nested sub-layout {sub_item.layout()}")
                                sub_item.layout().deleteLater() # Or a similar clearing loop
                        layout_item.deleteLater()
            print(f"DEBUG_SCT: _show_ui_creation_error_state - Finished clearing items from layout {current_layout}.")
        else:
            print("DEBUG_SCT: _show_ui_creation_error_state - No current layout to clear.")

        # Remove all direct children of the SequenceControllerTab widget itself
        # This is important if QVBoxLayout(self) in __init__ failed or if widgets were added directly.
        for child in self.findChildren(QWidget):
            if child.parent() is self: # Only direct children
                child.setParent(None)
                child.deleteLater()
        print("DEBUG_SCT: _show_ui_creation_error_state - Cleared direct children of self.")

        # Now, it should be safe to set a new layout for the error message
        try:
            error_layout = QVBoxLayout()
            self.setLayout(error_layout) # This should now work if previous cleanup was effective
            print("DEBUG_SCT: _show_ui_creation_error_state - Set new error_layout.")

            error_label = QLabel("Test Sequence Controller 탭 초기화 실패.\n"
                                 "애플리케이션 로그를 확인하세요.", self) # Parent to self
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
            error_layout.addWidget(error_label)
            print("DEBUG_SCT: _show_ui_creation_error_state - Added error_label to error_layout.")
        except Exception as e_layout:
            print(f"CRITICAL_ERROR_SCT: Failed to set error layout in _show_ui_creation_error_state: {e_layout}")
            # Fallback: try to just create and show the label if setting layout fails
            try:
                error_label_fallback = QLabel("UI ERROR - Check Logs", self)
                error_label_fallback.setAlignment(Qt.AlignCenter)
                error_label_fallback.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
                error_label_fallback.show()
            except Exception as e_label_fallback:
                print(f"CRITICAL_ERROR_SCT: Failed to even show fallback error label: {e_label_fallback}")

        print("ERROR_SCT: UI Creation Failed. Tab content replaced with error message.")
        self.setEnabled(False)


    def _setup_saved_sequences_directory(self) -> str:
        """저장된 시퀀스 파일들을 위한 디렉토리를 설정하고 경로를 반환합니다."""
        # 사용자 문서 디렉토리 내에 애플리케이션별 디렉토리 생성
        try:
            app_data_dir_parent = os.path.join(os.path.expanduser("~"), "Documents")
            if not os.path.exists(app_data_dir_parent):
                # 문서 디렉토리가 없는 경우 (매우 드묾), 홈 디렉토리 사용
                app_data_dir_parent = os.path.expanduser("~")

            app_name_for_dirs = getattr(constants, 'APP_NAME_FOR_DIRS', 'TestAutomationApp')
            app_data_dir = os.path.join(app_data_dir_parent, app_name_for_dirs)
            os.makedirs(app_data_dir, exist_ok=True)
            
            sequences_dir = os.path.join(app_data_dir, constants.SAVED_SEQUENCES_DIR_NAME)
            os.makedirs(sequences_dir, exist_ok=True)
            return sequences_dir
        except OSError as e:
            print(f"Warning_SCT: 시퀀스 저장 디렉토리 생성 실패 ({e}). 현재 작업 디렉토리 사용.")
            # 대체 경로로 현재 작업 디렉토리 내의 'sequences' 폴더 사용
            fallback_dir = os.path.join(os.getcwd(), constants.SAVED_SEQUENCES_DIR_NAME)
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                return fallback_dir
            except OSError as e2:
                # 이것마저 실패하면 최후의 수단으로 현재 작업 디렉토리 반환
                QMessageBox.critical(self, "치명적 경로 오류", f"모든 시퀀스 저장 경로 생성 실패: {e2}\n현재 작업 디렉토리 사용: {os.getcwd()}")
                return os.getcwd()

    def _setup_main_layout(self, target_layout: QVBoxLayout):
        if target_layout is None:
            print("CRITICAL_ERROR_SCT: Target layout is None in _setup_main_layout.")
            self._ui_setup_successful = False
            return

        try:
            self._main_splitter = QSplitter(Qt.Horizontal, self)
            
            if isinstance(self._main_splitter, QSplitter):
                print(f"DEBUG_SCT: QSplitter created successfully. Type: {type(self._main_splitter)}, Parent: {self._main_splitter.parent()}")
                if self._main_splitter.parent() is self:
                    target_layout.addWidget(self._main_splitter)
                    print("DEBUG_SCT: QSplitter added to target_layout.")
                else:
                    print(f"CRITICAL_ERROR_SCT: QSplitter created but NOT parented to self. Parent is: {self._main_splitter.parent()}. Attempting to reparent and add.")
                    self._main_splitter.setParent(self) 
                    if self._main_splitter.parent() is self:
                        target_layout.addWidget(self._main_splitter)
                        print("DEBUG_SCT: QSplitter reparented and added to target_layout.")
                    else:
                        print("CRITICAL_ERROR_SCT: Failed to reparent QSplitter. UI setup will fail.")
                        self._ui_setup_successful = False
            else:
                print(f"CRITICAL_ERROR_SCT: QSplitter() did not return a QSplitter instance. Got: {type(self._main_splitter)}")
                self._ui_setup_successful = False 
                if self._main_splitter is not None: 
                    self._main_splitter.deleteLater()
                    self._main_splitter = None
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Failed to create or add QSplitter: {e}")
            self._ui_setup_successful = False
            if self._main_splitter: # 예외 발생 시에도 객체가 생성되었을 수 있으므로 정리 시도
                self._main_splitter.deleteLater()
                self._main_splitter = None


    def _create_left_panel(self):
        if not self._ui_setup_successful or not self._main_splitter: # 이전 단계 실패 또는 스플리터 없음
            print("DEBUG_SCT: _create_left_panel - Skipping due to previous failure or no splitter.")
            self._ui_setup_successful = False # 확실히 실패 처리
            return

        left_panel_widget = QWidget(self) 
        left_panel_layout = QVBoxLayout(left_panel_widget) # 레이아웃에 부모 위젯 전달
        left_panel_layout.setSpacing(10)
        left_panel_layout.setContentsMargins(0,0,0,0)

        try:
            print("DEBUG_SCT: _create_left_panel - Attempting to create ActionInputPanel.")
            self.action_input_panel = ActionInputPanel(self.completer_model, self.current_settings, self.register_map, parent=left_panel_widget)
            if not self.action_input_panel : 
                print("ERROR_SCT: ActionInputPanel creation failed.")
                self._ui_setup_successful = False; return
            print("DEBUG_SCT: _create_left_panel - ActionInputPanel created.")
            left_panel_layout.addWidget(self.action_input_panel)
            print("DEBUG_SCT: _create_left_panel - ActionInputPanel added to layout.")

            if not self._ui_setup_successful: return

            action_buttons_layout = QHBoxLayout()
            self.add_to_seq_button = QPushButton(constants.SEQ_ADD_BUTTON_TEXT, left_panel_widget)
            self.define_loop_button = QPushButton(constants.DEFINE_LOOP_BUTTON_TEXT, left_panel_widget)
            action_buttons_layout.addWidget(self.add_to_seq_button)
            action_buttons_layout.addWidget(self.define_loop_button)
            left_panel_layout.addLayout(action_buttons_layout)
            print("DEBUG_SCT: _create_left_panel - Action buttons created and added.")

            if not self._ui_setup_successful: return

            print("DEBUG_SCT: _create_left_panel - Attempting to create SavedSequencePanel.")
            self.saved_sequence_panel = SavedSequencePanel(self.sequence_io_manager, self.saved_sequences_dir, parent=left_panel_widget)
            if not self.saved_sequence_panel: 
                print("ERROR_SCT: SavedSequencePanel creation failed.")
                self._ui_setup_successful = False; return
            print("DEBUG_SCT: _create_left_panel - SavedSequencePanel created.")
            left_panel_layout.addWidget(self.saved_sequence_panel)
            print("DEBUG_SCT: _create_left_panel - SavedSequencePanel added to layout.")

            if not self._ui_setup_successful: return
            
            left_panel_layout.addStretch(1)

            play_stop_button_layout = QHBoxLayout()
            self.play_seq_button = QPushButton(constants.SEQ_PLAY_BUTTON_TEXT, left_panel_widget)
            self.stop_seq_button = QPushButton(constants.SEQ_STOP_BUTTON_TEXT, left_panel_widget)
            
            try: # 아이콘 설정
                app_instance = QApplication.instance()
                if app_instance:
                    play_icon = app_instance.style().standardIcon(QStyle.SP_MediaPlay)
                    stop_icon = app_instance.style().standardIcon(QStyle.SP_MediaStop)
                    if self.play_seq_button: self.play_seq_button.setIcon(play_icon)
                    if self.stop_seq_button: self.stop_seq_button.setIcon(stop_icon)
            except Exception as e: print(f"Warning_SCT: Icon for play/stop_seq_button: {e}")
            
            if self.stop_seq_button: self.stop_seq_button.setEnabled(False)
            else: 
                print("ERROR_SCT: Stop sequence button creation failed.")
                self._ui_setup_successful = False; return
            
            if not self._ui_setup_successful: return
            print("DEBUG_SCT: _create_left_panel - Play/Stop buttons created.")

            play_stop_button_layout.addWidget(self.play_seq_button)
            play_stop_button_layout.addWidget(self.stop_seq_button)
            left_panel_layout.addLayout(play_stop_button_layout)
            
            if self._main_splitter:
                self._main_splitter.addWidget(left_panel_widget)
                print("DEBUG_SCT: _create_left_panel - Left panel widget added to splitter.")
            else:
                print("ERROR_SCT: _main_splitter is None in _create_left_panel. Cannot add widget.")
                self._ui_setup_successful = False
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_left_panel: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False

    def _create_right_panel(self):
        if not self._ui_setup_successful or not self._main_splitter: # 이전 단계 실패 또는 스플리터 없음
            print("DEBUG_SCT: _create_right_panel - Skipping due to previous failure or no splitter.")
            self._ui_setup_successful = False # 확실히 실패 처리
            return

        right_panel_widget = QWidget(self)
        right_panel_layout = QVBoxLayout(right_panel_widget) # 레이아웃에 부모 위젯 전달
        right_panel_layout.setSpacing(10)
        right_panel_layout.setContentsMargins(0,0,0,0)

        seq_list_label = QLabel(constants.SEQ_LIST_LABEL, right_panel_widget)
        right_panel_layout.addWidget(seq_list_label)

        try:
            print("DEBUG_SCT: _create_right_panel - Attempting to create QListWidget.")
            self.sequence_list_widget = QListWidget(right_panel_widget)
            if not self.sequence_list_widget: # 생성 실패 시 (드물지만)
                print("ERROR_SCT: QListWidget creation returned None.")
                self._ui_setup_successful = False; return
            self.sequence_list_widget.setItemDelegate(SequenceListItemDelegate(self.sequence_list_widget))
            print("DEBUG_SCT: _create_right_panel - QListWidget created.")
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during QListWidget creation: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False
            return
        
        if not self._ui_setup_successful: return

        font_monospace = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        log_font_size = getattr(constants, 'LOG_FONT_SIZE', 10) # constants에서 가져오도록 수정
        self.sequence_list_widget.setFont(QFont(font_monospace, log_font_size))
        self.sequence_list_widget.setAlternatingRowColors(True)
        right_panel_layout.addWidget(self.sequence_list_widget)
        print("DEBUG_SCT: _create_right_panel - QListWidget configured and added to layout.")

        if not self._ui_setup_successful: return

        try:
            list_management_buttons_layout = QHBoxLayout()
            self.remove_from_seq_button = QPushButton(constants.SEQ_REMOVE_BUTTON_TEXT, right_panel_widget)
            self.clear_seq_button = QPushButton(constants.SEQ_CLEAR_BUTTON_TEXT, right_panel_widget)
            list_management_buttons_layout.addWidget(self.remove_from_seq_button)
            list_management_buttons_layout.addWidget(self.clear_seq_button)
            right_panel_layout.addLayout(list_management_buttons_layout)
            print("DEBUG_SCT: _create_right_panel - List management buttons created and added.")

            if not self._ui_setup_successful: return

            exec_log_label = QLabel(constants.SEQ_LOG_LABEL, right_panel_widget)
            right_panel_layout.addWidget(exec_log_label)
            print("DEBUG_SCT: _create_right_panel - Attempting to create QTextEdit for log.")
            self.execution_log_textedit = QTextEdit(right_panel_widget)
            if not self.execution_log_textedit: # 생성 실패 시
                print("ERROR_SCT: QTextEdit for log creation returned None.")
                self._ui_setup_successful = False; return
            print("DEBUG_SCT: _create_right_panel - QTextEdit for log created.")
            self.execution_log_textedit.setReadOnly(True)
            self.execution_log_textedit.setFont(QFont(font_monospace, log_font_size))
            self.execution_log_textedit.setLineWrapMode(QTextEdit.NoWrap)
            right_panel_layout.addWidget(self.execution_log_textedit)
            print("DEBUG_SCT: _create_right_panel - QTextEdit for log configured and added to layout.")
            
            if self._main_splitter:
                self._main_splitter.addWidget(right_panel_widget)
                print("DEBUG_SCT: _create_right_panel - Right panel widget added to splitter.")
                # 스플리터 크기 조절 (예: 왼쪽 1/3, 오른쪽 2/3)
                total_width = self._main_splitter.width() if self._main_splitter.width() > 0 else 800 # 기본 너비
                self._main_splitter.setSizes([int(total_width * 0.4), int(total_width * 0.6)])
            else:
                print("ERROR_SCT: _main_splitter is None in _create_right_panel. Cannot add widget.")
                self._ui_setup_successful = False
        except Exception as e:
            print(f"CRITICAL_ERROR_SCT: Exception during _create_right_panel (after SLW creation): {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            self._ui_setup_successful = False

    def _connect_signals(self):
        if not self._ui_setup_successful: return

        if self.add_to_seq_button: self.add_to_seq_button.clicked.connect(self._add_action_to_sequence)
        if self.define_loop_button: self.define_loop_button.clicked.connect(self._define_loop)
        if self.play_seq_button: self.play_seq_button.clicked.connect(self._play_sequence)
        if self.stop_seq_button: self.stop_seq_button.clicked.connect(self.request_stop_sequence)
        if self.remove_from_seq_button: self.remove_from_seq_button.clicked.connect(self._remove_selected_from_sequence)
        if self.clear_seq_button: self.clear_seq_button.clicked.connect(self._clear_sequence_list)
        if self.sequence_list_widget:
            self.sequence_list_widget.itemDoubleClicked.connect(self._edit_sequence_item)
            self.sequence_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.sequence_list_widget.customContextMenuRequested.connect(self._show_sequence_list_context_menu)
            self.sequence_list_widget.itemSelectionChanged.connect(self._update_button_states)
        
        if self.saved_sequence_panel:
            self.saved_sequence_panel.load_sequence_signal.connect(self._load_sequence_from_file)
            self.saved_sequence_panel.save_sequence_as_signal.connect(self._save_sequence_as_file)
            # Rename and Delete signals are handled internally by SavedSequencePanel for now

    def _show_sequence_list_context_menu(self, position):
        if not self.sequence_list_widget: return
        
        selected_items = self.sequence_list_widget.selectedItems()
        if not selected_items: return

        menu = QMenu()
        edit_action = menu.addAction("Edit Selected Action")
        remove_action = menu.addAction("Remove Selected Action")
        menu.addSeparator()
        move_up_action = menu.addAction("Move Up")
        move_down_action = menu.addAction("Move Down")

        action = menu.exec_(self.sequence_list_widget.mapToGlobal(position))

        if action == edit_action:
            self._edit_sequence_item(selected_items[0])
        elif action == remove_action:
            self._remove_selected_from_sequence()
        elif action == move_up_action:
            self._move_selected_item_up()
        elif action == move_down_action:
            self._move_selected_item_down()

    def _move_selected_item_up(self):
        if not self.sequence_list_widget: return
        current_row = self.sequence_list_widget.currentRow()
        if current_row > 0: # Can't move up if it's the first item
            item = self.sequence_list_widget.takeItem(current_row)
            self.sequence_list_widget.insertItem(current_row - 1, item)
            self.sequence_list_widget.setCurrentRow(current_row - 1)
            self._update_button_states()

    def _move_selected_item_down(self):
        if not self.sequence_list_widget: return
        current_row = self.sequence_list_widget.currentRow()
        if current_row < self.sequence_list_widget.count() - 1: # Can't move down if it's the last item
            item = self.sequence_list_widget.takeItem(current_row)
            self.sequence_list_widget.insertItem(current_row + 1, item)
            self.sequence_list_widget.setCurrentRow(current_row + 1)
            self._update_button_states()

    def _add_action_to_sequence(self):
        if not self.action_input_panel or not self.sequence_list_widget:
            QMessageBox.warning(self, "오류", "UI 컴포넌트가 준비되지 않았습니다.")
            return

        action_data = self.action_input_panel.get_action_parameters()
        if action_data:
            display_text = self._format_action_for_display(action_data)
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, action_data) # Store the full dictionary
            self.sequence_list_widget.addItem(item)
            self._update_button_states()
        else:
            # ActionInputPanel should show its own error message if validation fails
            pass
            
    def _define_loop(self):
        if not self.sequence_list_widget: return

        dialog = LoopDefinitionDialog(self.sequence_list_widget, self.register_map, self)
        if dialog.exec_() == QDialog.Accepted:
            loop_params = dialog.get_loop_parameters()
            if loop_params:
                # Add LOOP_START
                loop_start_data = {
                    constants.SequenceParameterKey.ACTION_TYPE.value: {'type': constants.SequenceActionType.LOOP_START.value},
                    constants.SequenceParameterKey.LOOP_ACTION_INDEX.value: loop_params[constants.SequenceParameterKey.LOOP_ACTION_INDEX.value],
                    constants.SequenceParameterKey.LOOP_TARGET_PARAM_KEY.value: loop_params[constants.SequenceParameterKey.LOOP_TARGET_PARAM_KEY.value],
                    constants.SequenceParameterKey.LOOP_START_VALUE.value: loop_params[constants.SequenceParameterKey.LOOP_START_VALUE.value],
                    constants.SequenceParameterKey.LOOP_STEP_VALUE.value: loop_params[constants.SequenceParameterKey.LOOP_STEP_VALUE.value],
                    constants.SequenceParameterKey.LOOP_END_VALUE.value: loop_params[constants.SequenceParameterKey.LOOP_END_VALUE.value]
                }
                display_text_start = self._format_action_for_display(loop_start_data)
                start_item = QListWidgetItem(display_text_start)
                start_item.setData(Qt.UserRole, loop_start_data)
                
                # Add LOOP_END
                loop_end_data = {
                    constants.SequenceParameterKey.ACTION_TYPE.value: {'type': constants.SequenceActionType.LOOP_END.value}
                }
                display_text_end = self._format_action_for_display(loop_end_data)
                end_item = QListWidgetItem(display_text_end)
                end_item.setData(Qt.UserRole, loop_end_data)

                # Insert LOOP_START before the selected action index
                # Insert LOOP_END after the selected action index
                # This needs careful handling if the loop is around multiple actions or at the end.
                # For now, let's assume the dialog gives an index for the *start* of the loop content.
                # A more robust LoopDefinitionDialog would return a start and end index for the content.
                
                # Simplified: Add LOOP_START and LOOP_END at the end of the current list for now.
                # User can then move them.
                # TODO: Enhance LoopDefinitionDialog to allow specifying insertion points or wrapping existing items.
                self.sequence_list_widget.addItem(start_item)
                self.sequence_list_widget.addItem(end_item)
                self._update_button_states()


    def _format_action_for_display(self, action_data: Dict[str, Any]) -> str:
        action_type_info = action_data.get(constants.SequenceParameterKey.ACTION_TYPE.value, {})
        action_type = action_type_info.get('type', "UNKNOWN_ACTION")
        action_display_name = action_type_info.get('display', action_type) # Use display name if available

        params_to_display = []
        if action_type == constants.SequenceActionType.I2C_WRITE_BY_NAME.value:
            name = action_data.get(constants.SequenceParameterKey.TARGET_NAME.value, "N/A")
            val = action_data.get(constants.SequenceParameterKey.VALUE.value, "N/A")
            params_to_display.extend([f"Name: {name}", f"Val: {val}"])
        elif action_type == constants.SequenceActionType.I2C_WRITE_BY_ADDRESS.value:
            addr = action_data.get(constants.SequenceParameterKey.ADDRESS.value, "N/A")
            val = action_data.get(constants.SequenceParameterKey.VALUE.value, "N/A")
            params_to_display.extend([f"Addr: {addr}", f"Val: {val}"])
        elif action_type == constants.SequenceActionType.I2C_READ_BY_NAME.value:
            name = action_data.get(constants.SequenceParameterKey.TARGET_NAME.value, "N/A")
            var = action_data.get(constants.SequenceParameterKey.VARIABLE_NAME.value)
            params_to_display.append(f"Name: {name}")
            if var: params_to_display.append(f"SaveAs: {var}")
        elif action_type == constants.SequenceActionType.I2C_READ_BY_ADDRESS.value:
            addr = action_data.get(constants.SequenceParameterKey.ADDRESS.value, "N/A")
            var = action_data.get(constants.SequenceParameterKey.VARIABLE_NAME.value)
            params_to_display.append(f"Addr: {addr}")
            if var: params_to_display.append(f"SaveAs: {var}")
        elif action_type == constants.SequenceActionType.DELAY_SECONDS.value:
            sec = action_data.get(constants.SequenceParameterKey.SECONDS.value, "N/A")
            params_to_display.append(f"Sec: {sec}")
        elif action_type in [constants.SequenceActionType.DMM_MEASURE_VOLTAGE.value,
                             constants.SequenceActionType.DMM_MEASURE_CURRENT.value,
                             constants.SequenceActionType.SMU_MEASURE_VOLTAGE.value,
                             constants.SequenceActionType.SMU_MEASURE_CURRENT.value]:
            var = action_data.get(constants.SequenceParameterKey.VARIABLE_NAME.value)
            if var: params_to_display.append(f"SaveAs: {var}")
        elif action_type in [constants.SequenceActionType.DMM_SET_TERMINAL.value,
                             constants.SequenceActionType.SMU_SET_TERMINAL.value]:
            term = action_data.get(constants.SequenceParameterKey.TERMINAL.value, "N/A")
            params_to_display.append(f"Terminal: {term}")
        elif action_type in [constants.SequenceActionType.SMU_SET_VOLTAGE.value,
                             constants.SequenceActionType.SMU_SET_CURRENT.value,
                             constants.SequenceActionType.SMU_SET_PROTECTION_CURRENT.value,
                             constants.SequenceActionType.CHAMBER_SET_TEMPERATURE.value]:
            val = action_data.get(constants.SequenceParameterKey.VALUE.value, "N/A")
            params_to_display.append(f"Val: {val}")
        elif action_type == constants.SequenceActionType.SMU_ENABLE_OUTPUT.value:
            state = action_data.get(constants.SequenceParameterKey.STATE.value, "N/A")
            params_to_display.append(f"State: {state}")
        elif action_type == constants.SequenceActionType.CHAMBER_CHECK_TEMPERATURE_STABLE.value:
            timeout = action_data.get(constants.SequenceParameterKey.TIMEOUT_SECONDS.value, "Def")
            tolerance = action_data.get(constants.SequenceParameterKey.TOLERANCE_DEGREES.value, "Def")
            params_to_display.extend([f"Timeout: {timeout}s", f"Tol: {tolerance}°C"])
        elif action_type == constants.SequenceActionType.LOOP_START.value:
            target_key = action_data.get(constants.SequenceParameterKey.LOOP_TARGET_PARAM_KEY.value, "N/A")
            start_v = action_data.get(constants.SequenceParameterKey.LOOP_START_VALUE.value, "N/A")
            step_v = action_data.get(constants.SequenceParameterKey.LOOP_STEP_VALUE.value, "N/A")
            end_v = action_data.get(constants.SequenceParameterKey.LOOP_END_VALUE.value, "N/A")
            params_to_display.extend([f"Var: {target_key}", f"Range: {start_v} to {end_v}", f"Step: {step_v}"])
        elif action_type == constants.SequenceActionType.LOOP_END.value:
            pass # No specific params to show for LOOP_END itself in the list item

        if params_to_display:
            return f"{action_display_name} ({', '.join(params_to_display)})"
        return action_display_name

    def _edit_sequence_item(self, item: QListWidgetItem):
        if not self.action_input_panel or not self.sequence_list_widget: return

        action_data = item.data(Qt.UserRole)
        if not isinstance(action_data, dict):
            QMessageBox.warning(self, "편집 오류", "선택된 항목의 데이터가 유효하지 않습니다.")
            return

        # Populate ActionInputPanel with the existing data
        self.action_input_panel.populate_from_action_data(action_data)

        # For simplicity, remove the old item. User will re-add if they confirm changes.
        # A more sophisticated approach would be to update in-place or use a dialog.
        current_row = self.sequence_list_widget.row(item)
        self.sequence_list_widget.takeItem(current_row)
        self._update_button_states()
        if self.execution_log_textedit:
            self.execution_log_textedit.append(f"Info: Action '{item.text()}' removed for editing. Re-add after modification.")


    def _remove_selected_from_sequence(self):
        if not self.sequence_list_widget: return
        selected_items = self.sequence_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택하세요.")
            return
        for item in selected_items:
            self.sequence_list_widget.takeItem(self.sequence_list_widget.row(item))
        self._update_button_states()

    def _clear_sequence_list(self):
        if not self.sequence_list_widget: return
        reply = QMessageBox.question(self, "목록 초기화", "모든 시퀀스 항목을 삭제하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.sequence_list_widget.clear()
            if self.execution_log_textedit: self.execution_log_textedit.clear() # 로그도 같이 클리어
            self._update_button_states()

    def _play_sequence(self):
        if not self.sequence_list_widget or not self.execution_log_textedit or not self.main_window_ref:
            QMessageBox.critical(self, "실행 오류", "필수 UI 컴포넌트 또는 참조가 없습니다.")
            return

        if self.sequence_list_widget.count() == 0:
            QMessageBox.information(self, "알림", constants.MSG_SEQUENCE_EMPTY)
            return

        if self.sequence_player_thread and self.sequence_player_thread.isRunning():
            QMessageBox.warning(self, "알림", "시퀀스가 이미 실행 중입니다.")
            return

        sequence_items_data = []
        for i in range(self.sequence_list_widget.count()):
            item = self.sequence_list_widget.item(i)
            item_data = item.data(Qt.UserRole)
            if isinstance(item_data, dict): # Ensure it's a dictionary
                sequence_items_data.append(item_data)
            else: # Should not happen if items are added correctly
                self.execution_log_textedit.append(f"<font color='red'>Error: Invalid data for item at index {i}. Skipping.</font>")
                QMessageBox.critical(self, "데이터 오류", f"시퀀스 항목 {i}의 데이터가 잘못되었습니다. 실행을 중단합니다.")
                return


        self.execution_log_textedit.clear()
        self.execution_log_textedit.append("--- 시퀀스 실행 시작 ---")

        self.sequence_player = SequencePlayer(
            sequence_items_data,
            self.register_map,
            self.i2c_device,
            self.multimeter,
            self.sourcemeter,
            self.chamber,
            self.main_window_ref.get_current_sample_number, # Callable
            self.main_window_ref.get_current_measurement_conditions, # Callable
            self.current_settings 
        )
        self.sequence_player_thread = QThread()
        self.sequence_player.moveToThread(self.sequence_player_thread)

        # Connect signals from SequencePlayer
        self.sequence_player.log_message_signal.connect(self._append_log_message)
        self.sequence_player.new_measurement_signal.connect(self.new_measurement_signal) # Relay to main window
        self.sequence_player.sequence_finished_signal.connect(self._on_sequence_finished)
        self.sequence_player.highlight_item_signal.connect(self._highlight_sequence_item)

        self.sequence_player_thread.started.connect(self.sequence_player.run_sequence)
        self.sequence_player_thread.finished.connect(self.sequence_player_thread.deleteLater)
        self.sequence_player.sequence_finished_signal.connect(self.sequence_player_thread.quit)


        self.sequence_player_thread.start()
        self.sequence_status_changed_signal.emit(True)
        self._update_button_states(is_running=True)

    def request_stop_sequence(self):
        if self.sequence_player and self.sequence_player_thread and self.sequence_player_thread.isRunning():
            self.execution_log_textedit.append("<font color='orange'>--- 시퀀스 중단 요청됨 ---</font>")
            self.sequence_player.request_stop()
        else:
            self.execution_log_textedit.append("<font color='gray'>Info: 중단할 실행 중인 시퀀스가 없습니다.</font>")
        # 버튼 상태는 _on_sequence_finished에서 처리

    @pyqtSlot(str, str) # color, message
    def _append_log_message(self, color: str, message: str):
        if self.execution_log_textedit:
            self.execution_log_textedit.append(f"<font color='{color}'>{message}</font>")

    @pyqtSlot(int, bool) # index, is_error
    def _highlight_sequence_item(self, index: int, is_error: bool):
        if self.sequence_list_widget and 0 <= index < self.sequence_list_widget.count():
            self.sequence_list_widget.setCurrentRow(index)
            item = self.sequence_list_widget.item(index)
            if item:
                if is_error:
                    item.setBackground(QColor("mistyrose")) # 연분홍색 배경
                else:
                    # 일반 선택 색상 또는 기본 배경으로 되돌리기
                    # QListWidget의 기본 스타일 시트에 따라 달라질 수 있음
                    # item.setBackground(self.sequence_list_widget.palette().base()) # 기본 배경
                    pass # 현재 선택된 항목은 자동으로 하이라이트되므로 추가 작업 불필요할 수 있음
        
    @pyqtSlot(bool) # was_aborted
    def _on_sequence_finished(self, was_aborted: bool):
        if self.execution_log_textedit:
            if was_aborted:
                self.execution_log_textedit.append("<font color='orange'>--- 시퀀스 실행 중단됨 ---</font>")
            else:
                self.execution_log_textedit.append("--- 시퀀스 실행 완료 ---")
        
        if self.sequence_player_thread:
            if self.sequence_player_thread.isRunning(): # 아직 실행 중이면 quit 요청
                 self.sequence_player_thread.quit()
            # self.sequence_player_thread.wait() # 스레드 종료 대기 (선택적, GUI 반응성 저하 가능성)
        
        self.sequence_player = None # 참조 해제
        # self.sequence_player_thread = None # finished 시그널에서 deleteLater로 처리
        
        self.sequence_status_changed_signal.emit(False)
        self._update_button_states(is_running=False)


    def _update_button_states(self, is_running: Optional[bool] = None):
        if is_running is None: # 명시적 상태가 없으면 스레드 상태 확인
            is_running = self.sequence_player_thread is not None and self.sequence_player_thread.isRunning()

        # UI 요소들이 None이 아닌지 확인 후 활성화/비활성화
        if self.play_seq_button: self.play_seq_button.setEnabled(not is_running and self.sequence_list_widget is not None and self.sequence_list_widget.count() > 0)
        if self.stop_seq_button: self.stop_seq_button.setEnabled(is_running)
        if self.add_to_seq_button: self.add_to_seq_button.setEnabled(not is_running)
        if self.define_loop_button: self.define_loop_button.setEnabled(not is_running)
        if self.clear_seq_button: self.clear_seq_button.setEnabled(not is_running and self.sequence_list_widget is not None and self.sequence_list_widget.count() > 0)
        if self.remove_from_seq_button: self.remove_from_seq_button.setEnabled(not is_running and self.sequence_list_widget is not None and len(self.sequence_list_widget.selectedItems()) > 0)
        if self.action_input_panel: self.action_input_panel.setEnabled(not is_running)
        if self.saved_sequence_panel: self.saved_sequence_panel.setEnabled(not is_running)


    def _load_sequence_from_file(self, file_path: str):
        if not self.sequence_list_widget or not self.execution_log_textedit: return

        try:
            sequence_data = self.sequence_io_manager.load_sequence(file_path)
            if sequence_data:
                self.sequence_list_widget.clear()
                for action_data in sequence_data:
                    display_text = self._format_action_for_display(action_data)
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, action_data)
                    self.sequence_list_widget.addItem(item)
                self.execution_log_textedit.append(f"Info: 시퀀스 '{os.path.basename(file_path)}' 로드 완료.")
            else:
                self.execution_log_textedit.append(f"<font color='red'>Error: 시퀀스 파일 '{os.path.basename(file_path)}' 로드 실패.</font>")
        except Exception as e:
            self.execution_log_textedit.append(f"<font color='red'>Error: 시퀀스 파일 로드 중 예외 발생: {e}</font>")
            QMessageBox.critical(self, "로드 오류", f"시퀀스 파일 로드 중 오류 발생:\n{e}")
        self._update_button_states()

    def _save_sequence_as_file(self, file_path: str):
        if not self.sequence_list_widget or not self.execution_log_textedit: return
        
        sequence_items_data = []
        for i in range(self.sequence_list_widget.count()):
            item = self.sequence_list_widget.item(i)
            item_data = item.data(Qt.UserRole)
            if isinstance(item_data, dict):
                sequence_items_data.append(item_data)
            else: # 데이터가 없거나 잘못된 경우 (이론상 발생 안 함)
                QMessageBox.warning(self, "저장 오류", f"시퀀스 항목 {i}의 데이터가 유효하지 않아 저장할 수 없습니다.")
                return

        if not sequence_items_data:
            QMessageBox.information(self, "알림", "저장할 시퀀스 항목이 없습니다.")
            return

        try:
            if self.sequence_io_manager.save_sequence(file_path, sequence_items_data):
                self.execution_log_textedit.append(f"Info: 시퀀스가 '{os.path.basename(file_path)}'에 저장되었습니다.")
                if self.saved_sequence_panel: self.saved_sequence_panel.refresh_sequence_list() # 저장 후 목록 새로고침
            else:
                self.execution_log_textedit.append(f"<font color='red'>Error: 시퀀스 파일 '{os.path.basename(file_path)}' 저장 실패.</font>")
        except Exception as e:
            self.execution_log_textedit.append(f"<font color='red'>Error: 시퀀스 파일 저장 중 예외 발생: {e}</font>")
            QMessageBox.critical(self, "저장 오류", f"시퀀스 파일 저장 중 오류 발생:\n{e}")

    def update_register_map(self, register_map_instance: Optional['RegisterMap']):
        self.register_map = register_map_instance
        if self.action_input_panel:
            self.action_input_panel.update_register_map(self.register_map)
        # 현재 시퀀스 목록이 있다면, 레지스터 이름 기반 액션들의 유효성 검사 필요 (선택적)

    def update_settings(self, settings_data: Dict[str, Any]):
        self.current_settings = settings_data
        if self.action_input_panel:
            self.action_input_panel.update_settings(self.current_settings)

    def update_hardware_instances(self, i2c_device, multimeter, sourcemeter, chamber):
        self.i2c_device = i2c_device
        self.multimeter = multimeter
        self.sourcemeter = sourcemeter
        self.chamber = chamber
        # SequencePlayer는 실행 시점에 이 인스턴스들을 전달받으므로, 여기서는 저장만 해둠
        if self.action_input_panel: # ActionInputPanel도 하드웨어 상태를 알 필요가 있다면 업데이트
            pass # 현재 ActionInputPanel은 하드웨어 직접 제어 안 함

    def get_sequence_items_for_saving(self) -> List[Dict[str, Any]]:
        """현재 시퀀스 목록의 모든 항목 데이터를 반환합니다 (저장용)."""
        if not self.sequence_list_widget:
            return []
        
        items_data = []
        for i in range(self.sequence_list_widget.count()):
            item = self.sequence_list_widget.item(i)
            item_data = item.data(Qt.UserRole)
            if isinstance(item_data, dict):
                items_data.append(item_data)
        return items_data

    def load_sequence_items_from_data(self, sequence_items_data: List[Dict[str, Any]]):
        """주어진 데이터로 시퀀스 목록을 채웁니다 (불러오기용)."""
        if not self.sequence_list_widget:
            return
        
        self.sequence_list_widget.clear()
        for action_data in sequence_items_data:
            display_text = self._format_action_for_display(action_data)
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, action_data)
            self.sequence_list_widget.addItem(item)
        self._update_button_states()

    def closeEvent(self, event):
        # SequencePlayer 스레드가 실행 중이면 정지 요청
        if self.sequence_player_thread and self.sequence_player_thread.isRunning():
            self.request_stop_sequence()
            # 스레드가 완전히 종료될 때까지 기다릴 수 있지만, GUI가 멈출 수 있으므로 주의
            # self.sequence_player_thread.wait(1000) # 예: 1초 대기
        super().closeEvent(event)
