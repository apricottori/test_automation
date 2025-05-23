# ui/widgets/saved_sequence_panel.py
import sys # sys는 현재 직접 사용되지 않으나, 표준 라이브러리이므로 유지 가능
import os
from typing import List, Dict, Any, Optional # Any는 현재 사용되지 않음

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QInputDialog, QMessageBox, QApplication, QStyle,
    QLineEdit 
)
from PyQt5.QtCore import Qt, pyqtSignal,pyqtSlot

# --- 수정된 임포트 경로 ---
from core import constants
from core.sequence_io_manager import SequenceIOManager 

class SavedSequencePanel(QWidget):
    """
    저장된 테스트 시퀀스 목록을 표시하고 관리하는 UI 패널입니다.
    (로드, 다른 이름으로 저장 요청, 이름 변경, 삭제 기능)
    """
    load_sequence_to_editor_requested = pyqtSignal(list) # List[str]
    save_current_sequence_as_requested = pyqtSignal(str) # filename_without_ext

    def __init__(self, 
                 sequence_io_manager: SequenceIOManager, 
                 saved_sequences_dir: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sequence_io_manager = sequence_io_manager
        self.saved_sequences_dir = saved_sequences_dir

        # UI 멤버 변수 선언
        self.saved_sequences_list_widget: Optional[QListWidget] = None
        self.load_button: Optional[QPushButton] = None
        self.save_as_button: Optional[QPushButton] = None
        self.rename_button: Optional[QPushButton] = None
        self.delete_button: Optional[QPushButton] = None
        
        self._setup_ui()
        self._connect_signals()
        self.load_saved_sequences() # 초기화 시 목록 로드

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0) # 패널 자체의 여백은 0

        group_box = QGroupBox(constants.SAVED_SEQUENCES_GROUP_TITLE)
        group_layout = QVBoxLayout(group_box) # 그룹박스 내부 레이아웃

        self.saved_sequences_list_widget = QListWidget()
        self.saved_sequences_list_widget.setAlternatingRowColors(True)
        # 더블 클릭으로 로드 기능
        self.saved_sequences_list_widget.itemDoubleClicked.connect(self._handle_load_button_clicked)
        group_layout.addWidget(self.saved_sequences_list_widget)

        # 버튼들을 두 줄로 배치 (기존과 동일)
        buttons_layout1 = QHBoxLayout()
        self.load_button = QPushButton(constants.LOAD_SEQUENCE_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance: self.load_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogOpenButton))
        except Exception as e:
            print(f"Warning (SavedSequencePanel): Could not set icon for load_button: {e}")
            
        self.save_as_button = QPushButton(constants.SAVE_SEQUENCE_AS_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance: self.save_as_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogSaveButton))
        except Exception as e:
            print(f"Warning (SavedSequencePanel): Could not set icon for save_as_button: {e}")
        
        buttons_layout1.addWidget(self.load_button)
        buttons_layout1.addWidget(self.save_as_button)
        group_layout.addLayout(buttons_layout1)

        buttons_layout2 = QHBoxLayout()
        self.rename_button = QPushButton(constants.RENAME_SEQUENCE_BUTTON_TEXT)
        try: 
            app_instance = QApplication.instance()
            if app_instance: self.rename_button.setIcon(app_instance.style().standardIcon(QStyle.SP_FileLinkIcon)) # 적절한 아이콘 선택
        except Exception as e:
            print(f"Warning (SavedSequencePanel): Could not set icon for rename_button: {e}")
            
        self.delete_button = QPushButton(constants.DELETE_SEQUENCE_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance: self.delete_button.setIcon(app_instance.style().standardIcon(QStyle.SP_TrashIcon))
        except Exception as e:
            print(f"Warning (SavedSequencePanel): Could not set icon for delete_button: {e}")

        buttons_layout2.addWidget(self.rename_button)
        buttons_layout2.addWidget(self.delete_button)
        group_layout.addLayout(buttons_layout2)
        
        main_layout.addWidget(group_box)

    def _connect_signals(self):
        if self.load_button:
            self.load_button.clicked.connect(self._handle_load_button_clicked)
        if self.save_as_button:
            self.save_as_button.clicked.connect(self._handle_save_as_button_clicked)
        if self.rename_button:
            self.rename_button.clicked.connect(self._handle_rename_button_clicked)
        if self.delete_button:
            self.delete_button.clicked.connect(self._handle_delete_button_clicked)

    def load_saved_sequences(self):
        """지정된 디렉토리에서 저장된 시퀀스 목록을 불러와 UI에 표시합니다."""
        if not self.saved_sequences_list_widget or not self.sequence_io_manager:
            print("Error (SavedSequencePanel): UI or IO manager not initialized for loading sequences.")
            return
            
        self.saved_sequences_list_widget.clear()
        sequences = self.sequence_io_manager.get_saved_sequences(self.saved_sequences_dir)
        for seq_info in sequences:
            item = QListWidgetItem(seq_info["name"])
            item.setData(Qt.UserRole, seq_info["path"]) # 파일 경로를 UserRole 데이터로 저장
            self.saved_sequences_list_widget.addItem(item)
        print(f"SavedSequencePanel: Loaded {len(sequences)} saved sequences from '{self.saved_sequences_dir}'.")

    def _handle_load_button_clicked(self):
        if not self.saved_sequences_list_widget or not self.sequence_io_manager: return
        
        selected_item = self.saved_sequences_list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "시퀀스 로드", "로드할 시퀀스를 목록에서 선택하세요.")
            return
        
        filepath = selected_item.data(Qt.UserRole) # 저장된 파일 경로 가져오기
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "로드 오류", f"시퀀스 파일을 찾을 수 없습니다: {filepath}\n목록을 새로고침합니다.")
            self.load_saved_sequences() # 파일이 없으면 목록을 새로고침
            return
            
        loaded_items = self.sequence_io_manager.load_sequence(filepath)
        if loaded_items is not None:
            self.load_sequence_to_editor_requested.emit(loaded_items)
        else:
            QMessageBox.warning(self, "로드 실패", f"'{selected_item.text()}' 시퀀스를 로드하는데 실패했습니다.")

    def _handle_save_as_button_clicked(self):
        # QInputDialog의 부모 위젯으로 self를 명시적으로 전달
        seq_name, ok = QInputDialog.getText(self, 
                                            constants.SEQUENCE_NAME_INPUT_DIALOG_TITLE, 
                                            constants.SEQUENCE_NAME_INPUT_DIALOG_LABEL)
        if ok and seq_name:
            # 파일명으로 사용하기 안전한 문자만 허용 (공백, 특수문자 등 제거 또는 변경)
            safe_seq_name = "".join(c if c.isalnum() or c in ['_','-'] else '_' for c in seq_name).strip('_')
            if not safe_seq_name: # 모든 문자가 걸러져 이름이 비게 된 경우
                QMessageBox.warning(self, "입력 오류", "유효한 시퀀스 이름이 필요합니다 (영문, 숫자, 밑줄, 하이픈만 사용 가능).")
                return
            self.save_current_sequence_as_requested.emit(safe_seq_name)
        elif ok and not seq_name: # OK를 눌렀으나 이름을 입력하지 않은 경우
             QMessageBox.warning(self, "입력 오류", "시퀀스 이름은 비워둘 수 없습니다.")

    def _handle_rename_button_clicked(self):
        if not self.saved_sequences_list_widget or not self.sequence_io_manager: return
        selected_item = self.saved_sequences_list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "이름 변경", "이름을 변경할 시퀀스를 선택하세요.")
            return

        old_name = selected_item.text()
        old_filepath = selected_item.data(Qt.UserRole)
        
        new_name_base, ok = QInputDialog.getText(self, "시퀀스 이름 변경", 
                                                 f"'{old_name}'의 새 이름을 입력하세요 (확장자 제외):", 
                                                 QLineEdit.Normal, old_name) # 기존 이름을 기본값으로 표시
        if ok and new_name_base and new_name_base != old_name:
            safe_new_name = "".join(c if c.isalnum() or c in ['_','-'] else '_' for c in new_name_base).strip('_')
            if not safe_new_name:
                QMessageBox.warning(self, "입력 오류", "유효한 새 시퀀스 이름이 필요합니다."); return

            new_filepath = self.sequence_io_manager.rename_sequence(old_filepath, safe_new_name, self.saved_sequences_dir)
            if new_filepath:
                QMessageBox.information(self, "이름 변경 성공", f"시퀀스 '{old_name}'의 이름이 '{safe_new_name}'(으)로 변경되었습니다.")
                self.load_saved_sequences() # 목록 새로고침
            else:
                QMessageBox.warning(self, "이름 변경 실패", "시퀀스 이름 변경에 실패했습니다. 파일 시스템 오류 또는 이름 중복을 확인하세요.")
        elif ok and (not new_name_base or new_name_base == old_name):
            # 이름을 입력하지 않았거나 변경하지 않은 경우 아무 작업 안 함
            pass

    def _handle_delete_button_clicked(self):
        if not self.saved_sequences_list_widget or not self.sequence_io_manager: return
        selected_item = self.saved_sequences_list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "시퀀스 삭제", "삭제할 시퀀스를 선택하세요.")
            return
        
        seq_name_to_delete = selected_item.text()
        reply = QMessageBox.question(self, "삭제 확인",
                                     f"정말로 '{seq_name_to_delete}' 시퀀스를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            filepath = selected_item.data(Qt.UserRole)
            if self.sequence_io_manager.delete_sequence(filepath):
                QMessageBox.information(self, "삭제 성공", f"시퀀스 '{seq_name_to_delete}'이(가) 삭제되었습니다.")
                self.load_saved_sequences() # 목록 새로고침
            else:
                QMessageBox.warning(self, "삭제 실패", f"시퀀스 '{seq_name_to_delete}' 삭제에 실패했습니다.")

    def save_sequence_to_file_requested_by_controller(self, items_to_save: List[str], filename_without_ext: str) -> bool:
        """SequenceControllerTab으로부터 현재 시퀀스 저장 요청을 받아 처리합니다."""
        if not self.sequence_io_manager: return False
        
        # 파일명 유효성 검사는 _handle_save_as_button_clicked에서 이미 수행된 것으로 가정
        # 여기서는 전달받은 filename_without_ext를 그대로 사용
        filepath = os.path.join(self.saved_sequences_dir, filename_without_ext + constants.SEQUENCE_FILE_EXTENSION)
        
        if os.path.exists(filepath):
            reply = QMessageBox.question(self, "덮어쓰기 확인", 
                                         f"파일 '{filename_without_ext}{constants.SEQUENCE_FILE_EXTENSION}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: 
                return False # 덮어쓰기 거부

        if self.sequence_io_manager.save_sequence(filepath, items_to_save):
            print(f"Info: Sequence saved to '{filepath}' by controller request.")
            self.load_saved_sequences() # 저장 후 목록 새로고침
            return True
        return False

if __name__ == '__main__':
    # 테스트를 위한 QApplication 인스턴스
    app = QApplication(sys.argv)

    # 테스트를 위한 MockConstants (실제 실행 시에는 core.constants가 임포트되어야 함)
    try:
        from core import constants as test_constants_module
    except ImportError:
        class MockCoreConstants:
            SAVED_SEQUENCES_GROUP_TITLE = "My Saved Sequences (Mock)"
            LOAD_SEQUENCE_BUTTON_TEXT = "Load (Mock)"
            SAVE_SEQUENCE_AS_BUTTON_TEXT = "Save As... (Mock)"
            RENAME_SEQUENCE_BUTTON_TEXT = "Rename (Mock)"
            DELETE_SEQUENCE_BUTTON_TEXT = "Delete (Mock)"
            SEQUENCE_NAME_INPUT_DIALOG_TITLE = "Seq Name (Mock)"
            SEQUENCE_NAME_INPUT_DIALOG_LABEL = "Name (Mock):"
            SEQUENCE_FILE_EXTENSION = ".testseq.json"
            APP_NAME_FOR_FOLDER = "TestAppSavedSeqPanel" # 테스트용 앱 이름
        test_constants_module = MockCoreConstants()
        constants = test_constants_module # 전역 constants를 mock으로 사용 (테스트 환경)


    # 테스트용 시퀀스 저장 디렉토리 (임시 생성)
    test_saved_seq_dir = os.path.join(os.getcwd(), "test_saved_sequences_panel_dir_core")
    if not os.path.exists(test_saved_seq_dir):
        os.makedirs(test_saved_seq_dir, exist_ok=True)
    
    # SequenceIOManager는 core에서 가져와야 함
    try:
        from core.sequence_io_manager import SequenceIOManager as TestSequenceIOManager
        mock_io_manager_instance = TestSequenceIOManager()
        # 테스트 파일 생성
        mock_io_manager_instance.save_sequence(os.path.join(test_saved_seq_dir, "AlphaSeq" + constants.SEQUENCE_FILE_EXTENSION), ["AlphaStep1", "AlphaStep2"])
        mock_io_manager_instance.save_sequence(os.path.join(test_saved_seq_dir, "BetaSeq" + constants.SEQUENCE_FILE_EXTENSION), ["BetaStep1"])
    except ImportError:
        print("CRITICAL: Cannot import SequenceIOManager for testing. Test will be limited.")
        mock_io_manager_instance = None # 테스트 진행 불가 또는 제한적

    if mock_io_manager_instance:
        panel_widget = SavedSequencePanel(mock_io_manager_instance, test_saved_seq_dir)
        panel_widget.setWindowTitle("SavedSequencePanel Test (Core Structure)")
        panel_widget.setGeometry(300, 300, 350, 400) # 패널 크기
        
        @pyqtSlot(list)
        def handle_load_request_test(items): 
            print(f"Test Slot: Load requested for items: {items}")
        
        @pyqtSlot(str)
        def handle_save_as_request_test(name_no_ext): 
            print(f"Test Slot: Save As requested for name (no ext): {name_no_ext}")
            # 실제 저장은 panel_widget.save_sequence_to_file_requested_by_controller 통해 이루어짐
            # 이 시그널은 이름만 전달하므로, SequenceControllerTab에서 현재 목록을 가져와 함께 호출해야 함.
            # 여기서는 이름 수신만 확인.
            if panel_widget: # panel_widget이 None이 아닐 때만 호출
                success = panel_widget.save_sequence_to_file_requested_by_controller(
                    ["TestItemFromController1", "TestItemFromController2"], name_no_ext
                )
                print(f"Test Slot: save_sequence_to_file_requested_by_controller returned: {success}")


        panel_widget.load_sequence_to_editor_requested.connect(handle_load_request_test)
        panel_widget.save_current_sequence_as_requested.connect(handle_save_as_request_test)
        
        panel_widget.show()
        exit_code = app.exec_()
    else:
        print("Test skipped due to missing SequenceIOManager.")
        exit_code = 1
    
    # 테스트 후 생성된 디렉토리 및 파일 정리
    try:
        if os.path.exists(test_saved_seq_dir):
            for item_name in os.listdir(test_saved_seq_dir):
                item_path = os.path.join(test_saved_seq_dir, item_name)
                if os.path.isfile(item_path):
                    os.remove(item_path)
            os.rmdir(test_saved_seq_dir)
            print(f"Test directory '{test_saved_seq_dir}' cleaned up.")
    except Exception as e_cleanup:
        print(f"Error cleaning up test directory '{test_saved_seq_dir}': {e_cleanup}")
    
    sys.exit(exit_code)