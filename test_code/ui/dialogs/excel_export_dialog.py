# ui/dialogs/excel_export_dialog.py
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QDialogButtonBox,
    QListWidgetItem, QLineEdit, QMessageBox, QWidget, QScrollArea, QPushButton
)
from PyQt5.QtCore import Qt
# QApplication, QStyle은 아이콘 설정에 직접 사용되지 않으므로 제거 가능 (필요시 다시 추가)

# core 패키지에서 constants 임포트
from core import constants

class ExcelExportSettingsDialog(QDialog):
    """Excel 내보내기 시트 및 컬럼 설정을 위한 다이얼로그입니다."""
    def __init__(self, 
                 available_columns: List[str], 
                 current_sheet_configs: List[Dict[str, Any]], 
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(constants.EXPORT_CONFIG_DIALOG_TITLE)
        self.setMinimumSize(600, 450)

        self.available_columns = sorted(list(set(available_columns))) # 중복 제거 및 정렬
        # 외부에서 받은 리스트를 변경하지 않도록 깊은 복사 사용 고려
        self.sheet_configs = [config.copy() for config in current_sheet_configs]

        main_layout = QHBoxLayout(self)

        # 왼쪽: 시트 목록 및 관리 버튼
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("<b>Sheets:</b>"))
        self.sheet_list_widget = QListWidget()
        self.sheet_list_widget.itemSelectionChanged.connect(self._on_sheet_selection_changed)
        left_layout.addWidget(self.sheet_list_widget)

        sheet_buttons_layout = QHBoxLayout()
        self.add_sheet_button = QPushButton(constants.ADD_SHEET_BUTTON_TEXT)
        self.add_sheet_button.clicked.connect(self._add_sheet)
        self.remove_sheet_button = QPushButton(constants.REMOVE_SHEET_BUTTON_TEXT)
        self.remove_sheet_button.clicked.connect(self._remove_sheet)
        sheet_buttons_layout.addWidget(self.add_sheet_button)
        sheet_buttons_layout.addWidget(self.remove_sheet_button)
        left_layout.addLayout(sheet_buttons_layout)
        
        left_layout.addWidget(QLabel("Sheet Name:"))
        self.sheet_name_input = QLineEdit()
        self.sheet_name_input.editingFinished.connect(self._rename_current_sheet)
        left_layout.addWidget(self.sheet_name_input)

        main_layout.addWidget(left_panel, 1) # 비율 1

        # 오른쪽: 선택된 시트의 컬럼 설정
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel(f"<b>{constants.COLUMNS_IN_SHEET_LABEL}</b> (Drag to reorder)"))
        
        self.selected_columns_list_widget = QListWidget()
        self.selected_columns_list_widget.setDragDropMode(QListWidget.InternalMove) # 순서 변경
        right_layout.addWidget(self.selected_columns_list_widget)

        right_layout.addWidget(QLabel(f"<b>{constants.AVAILABLE_COLUMNS_LABEL}</b> (Double-click to add)"))
        
        # 사용 가능한 컬럼 목록은 스크롤 가능하도록 처리
        self.available_columns_list_widget = QListWidget()
        self.available_columns_list_widget.addItems(self.available_columns)
        self.available_columns_list_widget.itemDoubleClicked.connect(self._add_column_to_sheet)
        
        scroll_area_available = QScrollArea()
        scroll_area_available.setWidgetResizable(True)
        scroll_area_available.setWidget(self.available_columns_list_widget)
        right_layout.addWidget(scroll_area_available)

        main_layout.addWidget(right_panel, 2) # 비율 2

        # 하단: OK, Cancel 버튼
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._finalize_configs_and_accept)
        self.button_box.rejected.connect(self.reject)
        
        # 전체 레이아웃 구성 (메인 레이아웃과 버튼 박스를 수직으로 배치)
        dialog_main_layout = QVBoxLayout()
        dialog_main_layout.addLayout(main_layout)
        dialog_main_layout.addWidget(self.button_box)
        self.setLayout(dialog_main_layout)

        self._populate_sheet_list()
        if self.sheet_list_widget.count() > 0:
            self.sheet_list_widget.setCurrentRow(0)
        else: 
            self._add_sheet(default_name="Sheet1", select_all_available=True)

    def _populate_sheet_list(self):
        self.sheet_list_widget.clear()
        for config in self.sheet_configs:
            item = QListWidgetItem(config.get("sheet_name", "Unnamed Sheet"))
            self.sheet_list_widget.addItem(item)

    def _on_sheet_selection_changed(self):
        current_item = self.sheet_list_widget.currentItem()
        current_row = self.sheet_list_widget.currentRow()
        
        # 현재 선택된 시트의 컬럼 목록을 selected_columns_list_widget에 업데이트 전에,
        # 이전 시트에서 selected_columns_list_widget의 순서 변경이 있었다면 이를 self.sheet_configs에 먼저 저장
        # 하지만, itemSelectionChanged는 너무 자주 발생하므로, OK 버튼 클릭 시점에 최종 저장하는 것이 더 효율적
        # 여기서는 UI 표시만 업데이트
        
        if not current_item or current_row < 0 or current_row >= len(self.sheet_configs):
            self.sheet_name_input.clear()
            self.sheet_name_input.setEnabled(False)
            self.selected_columns_list_widget.clear()
            return

        self.sheet_name_input.setEnabled(True)
        config = self.sheet_configs[current_row]
        self.sheet_name_input.setText(config.get("sheet_name", ""))
        
        self.selected_columns_list_widget.clear()
        self.selected_columns_list_widget.addItems(config.get("columns", []))

    def _add_sheet(self, default_name: Optional[str] = None, select_all_available: bool = False):
        new_sheet_index = len(self.sheet_configs)
        sheet_name_candidate = default_name if default_name else f"Sheet{new_sheet_index + 1}"
        
        # 중복되지 않는 시트 이름 생성
        existing_names = {config.get("sheet_name") for config in self.sheet_configs}
        sheet_name = sheet_name_candidate
        counter = 1
        while sheet_name in existing_names:
            sheet_name = f"{sheet_name_candidate}_{counter}"
            counter += 1
            
        initial_cols = []
        if select_all_available: 
            initial_cols = self.available_columns[:]

        self.sheet_configs.append({"sheet_name": sheet_name, "columns": initial_cols})
        self._populate_sheet_list()
        self.sheet_list_widget.setCurrentRow(new_sheet_index) # 새로 추가된 시트 선택

    def _remove_sheet(self):
        current_row = self.sheet_list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.sheet_configs):
            return
        
        if len(self.sheet_configs) == 1:
            QMessageBox.warning(self, "삭제 불가", "최소 한 개의 시트는 유지해야 합니다.")
            return

        del self.sheet_configs[current_row]
        self._populate_sheet_list()
        
        new_selection_row = max(0, current_row -1) if self.sheet_list_widget.count() > 0 else -1
        if new_selection_row != -1 :
             self.sheet_list_widget.setCurrentRow(new_selection_row)
        else: # 모든 시트가 삭제된 경우 (실제로는 위에서 막힘)
             self._on_sheet_selection_changed() 

    def _rename_current_sheet(self):
        current_row = self.sheet_list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.sheet_configs):
            return
        
        new_name = self.sheet_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "입력 오류", "시트 이름은 비워둘 수 없습니다.")
            self.sheet_name_input.setText(self.sheet_configs[current_row].get("sheet_name", ""))
            return
        
        for i, config in enumerate(self.sheet_configs):
            if i != current_row and config.get("sheet_name") == new_name:
                QMessageBox.warning(self, "이름 중복", f"시트 이름 '{new_name}'이(가) 이미 존재합니다.")
                self.sheet_name_input.setText(self.sheet_configs[current_row].get("sheet_name", ""))
                return

        self.sheet_configs[current_row]["sheet_name"] = new_name
        self.sheet_list_widget.item(current_row).setText(new_name)

    def _add_column_to_sheet(self, item: QListWidgetItem):
        current_sheet_row = self.sheet_list_widget.currentRow()
        if current_sheet_row < 0 or current_sheet_row >= len(self.sheet_configs):
            return
        
        col_name = item.text()
        current_cols_in_sheet = self.sheet_configs[current_sheet_row].get("columns", [])
        if col_name not in current_cols_in_sheet:
            current_cols_in_sheet.append(col_name)
            # self.sheet_configs[current_sheet_row]["columns"]는 이미 current_cols_in_sheet를 참조하므로 별도 할당 불필요
            self.selected_columns_list_widget.addItem(col_name)
        else:
            QMessageBox.information(self, "알림", f"컬럼 '{col_name}'은(는) 이미 시트에 포함되어 있습니다.")

    def _finalize_configs_and_accept(self):
        # 현재 선택된 시트의 컬럼 목록을 (드래그앤드롭 순서 반영하여) self.sheet_configs에 저장
        current_sheet_row = self.sheet_list_widget.currentRow()
        if 0 <= current_sheet_row < len(self.sheet_configs):
            updated_cols = [self.selected_columns_list_widget.item(i).text() 
                            for i in range(self.selected_columns_list_widget.count())]
            self.sheet_configs[current_sheet_row]["columns"] = updated_cols
        
        # 모든 시트 이름 유효성 및 최종 중복 검사 (선택 사항, _rename_current_sheet에서 이미 처리)
        # ...

        self.accept() # QDialog.Accepted 반환

    def get_final_sheet_configs(self) -> List[Dict[str, Any]]:
        return self.sheet_configs