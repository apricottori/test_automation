# ui/dialogs/excel_export_dialog.py
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QLineEdit, QComboBox, QCheckBox, QListWidget, 
    QListWidgetItem, QPushButton, QGroupBox, QFormLayout,
    QDialogButtonBox, QMessageBox, QFileDialog, QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
import json

from core.data_models import ExcelSheetConfig # 정의된 데이터 모델 사용
from core import constants # UI 문자열 등

class ExcelExportSettingsDialog(QDialog):
    """고급 Excel 내보내기 설정을 위한 다이얼로그"""
    
    # 시그널 정의 (필요시)
    # config_saved = pyqtSignal(list) # List[ExcelSheetConfig]

    def __init__(self, available_columns: list[str], current_sheet_configs: Optional[list[ExcelSheetConfig]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(constants.EXPORT_CONFIG_DIALOG_TITLE) # constants 사용
        self.setMinimumSize(800, 600)
        
        self.available_columns = available_columns if available_columns else []
        # current_sheet_configs가 None이면 빈 리스트로 초기화, 아니면 깊은 복사
        self.sheet_configs: List[ExcelSheetConfig] = [cfg.copy() for cfg in current_sheet_configs] if current_sheet_configs else []

        # UI 멤버 변수 선언
        self.sheet_list: Optional[QListWidget] = None
        self.add_sheet_btn: Optional[QPushButton] = None
        self.remove_sheet_btn: Optional[QPushButton] = None
        self.duplicate_sheet_btn: Optional[QPushButton] = None
        self.save_config_btn: Optional[QPushButton] = None
        self.load_config_btn: Optional[QPushButton] = None

        # 시트 이름 설정 관련
        self.fixed_name_checkbox: Optional[QCheckBox] = None # Radio -> CheckBox로 변경하여 명확성 증대
        self.fixed_name_input: Optional[QLineEdit] = None
        self.dynamic_name_checkbox: Optional[QCheckBox] = None
        self.dynamic_name_field_combo: Optional[QComboBox] = None
        self.dynamic_name_prefix_input: Optional[QLineEdit] = None

        # 피벗 테이블 설정 관련
        self.index_fields_combo: Optional[QComboBox] = None
        self.column_fields_combo: Optional[QComboBox] = None
        self.value_field_combo: Optional[QComboBox] = None
        self.aggfunc_combo: Optional[QComboBox] = None
        self.transpose_checkbox: Optional[QCheckBox] = None

        # 필터 UI
        self.global_filters_group: Optional[QGroupBox] = None # For global filters
        self.index_filters_group: Optional[QGroupBox] = None # For index-specific filters
        self.column_filters_group: Optional[QGroupBox] = None # For column-specific filters
        # These will need more complex UI to add/remove filter conditions dynamically.
        # For now, placeholders or simplified input might be used.

        self.button_box: Optional[QDialogButtonBox] = None
        
        self._init_ui()
        self._connect_signals()
        self._populate_sheet_list()
        if not self.sheet_configs: # 설정이 없으면 기본 시트 하나 추가
            self._add_sheet_config(make_default=True)
        elif self.sheet_list and self.sheet_list.count() > 0:
            self.sheet_list.setCurrentRow(0) # 첫 번째 시트 선택
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- 좌측 패널: 시트 목록 및 관리 --- 
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("<b>Export Sheet Configurations:</b>"))
        self.sheet_list = QListWidget()
        left_layout.addWidget(self.sheet_list)
        
        sheet_mgmt_layout = QHBoxLayout()
        self.add_sheet_btn = QPushButton(QIcon.fromTheme("list-add"), " Add")
        self.remove_sheet_btn = QPushButton(QIcon.fromTheme("list-remove"), " Remove")
        self.duplicate_sheet_btn = QPushButton(QIcon.fromTheme("edit-copy"), " Duplicate")
        sheet_mgmt_layout.addWidget(self.add_sheet_btn); sheet_mgmt_layout.addWidget(self.remove_sheet_btn); sheet_mgmt_layout.addWidget(self.duplicate_sheet_btn)
        left_layout.addLayout(sheet_mgmt_layout)
        
        config_io_layout = QHBoxLayout()
        self.save_config_btn = QPushButton(QIcon.fromTheme("document-save"), " Save Config...")
        self.load_config_btn = QPushButton(QIcon.fromTheme("document-open"), " Load Config...")
        config_io_layout.addWidget(self.save_config_btn); config_io_layout.addWidget(self.load_config_btn)
        left_layout.addLayout(config_io_layout)
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # --- 우측 패널: 선택된 시트 설정 편집 --- 
        right_panel = QWidget()
        right_form_layout = QFormLayout(right_panel) # QFormLayout으로 변경
        right_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        right_form_layout.setLabelAlignment(Qt.AlignRight)

        # ScrollArea for right panel content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        right_form_layout = QFormLayout(scroll_content_widget) # Form layout inside scrollable content
        right_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        right_form_layout.setLabelAlignment(Qt.AlignRight)

        # 1. 시트 이름 설정
        naming_group = QGroupBox("Sheet Naming")
        naming_layout = QVBoxLayout(naming_group)
        self.fixed_name_checkbox = QCheckBox("Use Fixed Name:")
        self.fixed_name_input = QLineEdit()
        fixed_name_row = QHBoxLayout(); fixed_name_row.addWidget(self.fixed_name_checkbox); fixed_name_row.addWidget(self.fixed_name_input)
        naming_layout.addLayout(fixed_name_row)

        self.dynamic_name_checkbox = QCheckBox("Use Dynamic Name from Field:")
        dynamic_naming_sub_layout = QFormLayout()
        self.dynamic_name_field_combo = QComboBox(); self.dynamic_name_field_combo.addItems(self.available_columns)
        self.dynamic_name_prefix_input = QLineEdit(); self.dynamic_name_prefix_input.setPlaceholderText("Optional Prefix")
        dynamic_naming_sub_layout.addRow("Field for Name:", self.dynamic_name_field_combo)
        dynamic_naming_sub_layout.addRow("Prefix:", self.dynamic_name_prefix_input)
        dynamic_naming_widget = QWidget(); dynamic_naming_widget.setLayout(dynamic_naming_sub_layout)
        naming_layout.addWidget(self.dynamic_name_checkbox)
        naming_layout.addWidget(dynamic_naming_widget)
        right_form_layout.addRow(naming_group)

        # 2. 피벗 테이블 설정
        pivot_group = QGroupBox("Pivot Table Configuration")
        pivot_form_layout = QFormLayout(pivot_group) 
        
        # For index_fields and column_fields, using QComboBox for single selection as per simplified UI.
        # Data model supports List[str], so we'll store the selection as a single-item list.
        self.index_fields_combo = QComboBox(); self.index_fields_combo.addItems([""] + self.available_columns) # Add empty option
        self.column_fields_combo = QComboBox(); self.column_fields_combo.addItems([""] + self.available_columns) # Add empty option
        
        self.value_field_combo = QComboBox(); self.value_field_combo.addItems(self.available_columns)
        self.aggfunc_combo = QComboBox(); self.aggfunc_combo.addItems(['first', 'last', 'mean', 'median', 'sum', 'min', 'max', 'count', 'std'])
        self.transpose_checkbox = QCheckBox("Transpose Result")
        pivot_form_layout.addRow(constants.AVAILABLE_COLUMNS_LABEL.replace("Available","Row Field (Index):"), self.index_fields_combo) # Better label
        pivot_form_layout.addRow(constants.AVAILABLE_COLUMNS_LABEL.replace("Available","Column Field:"), self.column_fields_combo) # Better label
        pivot_form_layout.addRow("Value Field:", self.value_field_combo)
        pivot_form_layout.addRow("Aggregation:", self.aggfunc_combo)
        pivot_form_layout.addRow(self.transpose_checkbox)
        right_form_layout.addRow(pivot_group)

        # 3. 필터 설정 (Placeholder for now, as per proposal's phased approach)
        self.global_filters_group = QGroupBox("Global Data Filters (Selects data before pivoting)")
        global_filters_layout = QVBoxLayout(self.global_filters_group)
        # TODO: Implement dynamic UI for adding/removing global filter conditions: Field | Operator | Value
        global_filters_layout.addWidget(QLabel("Global filter UI to be implemented here."))
        self.global_filters_group.setEnabled(False) # Disable for now
        right_form_layout.addRow(self.global_filters_group)

        self.index_filters_group = QGroupBox("Index Value Filters (Filters specific row values after pivoting)")
        index_filters_layout = QVBoxLayout(self.index_filters_group)
        # TODO: Button to open a dialog for selecting unique values from the chosen index_field
        index_filters_layout.addWidget(QLabel("Index value filter UI to be implemented here."))
        self.index_filters_group.setEnabled(False) # Disable for now
        right_form_layout.addRow(self.index_filters_group)
        
        self.column_filters_group = QGroupBox("Column Value Filters (Filters specific column values after pivoting)")
        column_filters_layout = QVBoxLayout(self.column_filters_group)
        # TODO: Button to open a dialog for selecting unique values from the chosen column_field
        column_filters_layout.addWidget(QLabel("Column value filter UI to be implemented here."))
        self.column_filters_group.setEnabled(False) # Disable for now
        right_form_layout.addRow(self.column_filters_group)
        
        # Original right_panel (without scroll) directly used right_form_layout
        # Now, scroll_area contains scroll_content_widget, which has right_form_layout
        # So, the parent of splitter.addWidget should be right_panel, and right_panel's layout should contain the scroll_area.

        # Create a new top-level widget for the right side that will contain the scroll area
        right_panel_container = QWidget()
        right_panel_container_layout = QVBoxLayout(right_panel_container)
        right_panel_container_layout.addWidget(scroll_area)
        right_panel_container_layout.setContentsMargins(0,0,0,0) # Ensure container layout has no margins
        
        # Add the container to the splitter
        splitter.addWidget(right_panel_container)
        splitter.setSizes([250, 550])

        # --- 하단 버튼 --- 
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(self.button_box)

        self._update_naming_options_enabled_state() # 초기 상태 설정

    def _connect_signals(self):
        if self.sheet_list: self.sheet_list.currentItemChanged.connect(self._on_sheet_selection_changed)
        if self.add_sheet_btn: self.add_sheet_btn.clicked.connect(lambda: self._add_sheet_config())
        if self.remove_sheet_btn: self.remove_sheet_btn.clicked.connect(self._remove_selected_sheet)
        if self.duplicate_sheet_btn: self.duplicate_sheet_btn.clicked.connect(self._duplicate_selected_sheet)
        if self.save_config_btn: self.save_config_btn.clicked.connect(self._save_configuration_to_file)
        if self.load_config_btn: self.load_config_btn.clicked.connect(self._load_configuration_from_file)
        
        if self.fixed_name_checkbox: self.fixed_name_checkbox.toggled.connect(self._on_fixed_name_toggled)
        if self.dynamic_name_checkbox: self.dynamic_name_checkbox.toggled.connect(self._on_dynamic_name_toggled)

        # 설정 값 변경 시 _update_current_sheet_config 호출 (선택된 시트가 있을 때만)
        # (QComboBox, QLineEdit 등 모든 입력 위젯의 editingFinished 또는 currentIndexChanged 시그널에 연결)
        for widget in [self.fixed_name_input, self.dynamic_name_field_combo, self.dynamic_name_prefix_input, 
                       self.index_fields_combo, self.column_fields_combo, self.value_field_combo, 
                       self.aggfunc_combo, self.transpose_checkbox]:
            if widget:
                if isinstance(widget, QLineEdit): widget.editingFinished.connect(self._update_current_sheet_config_from_ui)
                elif isinstance(widget, QComboBox): widget.currentIndexChanged.connect(self._update_current_sheet_config_from_ui)
                elif isinstance(widget, QCheckBox): widget.toggled.connect(self._update_current_sheet_config_from_ui)

        if self.button_box: 
            self.button_box.accepted.connect(self.accept) # accept 슬롯은 QDialog 기본 제공
            self.button_box.rejected.connect(self.reject)

    def _on_fixed_name_toggled(self, checked: bool):
        if checked and self.dynamic_name_checkbox and self.dynamic_name_checkbox.isChecked():
            self.dynamic_name_checkbox.setChecked(False) # 동적 이름 선택 해제
        self._update_naming_options_enabled_state()
        self._update_current_sheet_config_from_ui() # 변경사항 즉시 반영

    def _on_dynamic_name_toggled(self, checked: bool):
        if checked and self.fixed_name_checkbox and self.fixed_name_checkbox.isChecked():
            self.fixed_name_checkbox.setChecked(False) # 고정 이름 선택 해제
        self._update_naming_options_enabled_state()
        self._update_current_sheet_config_from_ui() # 변경사항 즉시 반영

    def _update_naming_options_enabled_state(self):
        fixed_checked = self.fixed_name_checkbox.isChecked() if self.fixed_name_checkbox else False
        dynamic_checked = self.dynamic_name_checkbox.isChecked() if self.dynamic_name_checkbox else False

        if self.fixed_name_input: self.fixed_name_input.setEnabled(fixed_checked)
        if self.dynamic_name_field_combo: self.dynamic_name_field_combo.setEnabled(dynamic_checked)
        if self.dynamic_name_prefix_input: self.dynamic_name_prefix_input.setEnabled(dynamic_checked)

    def _populate_sheet_list(self):
        if not self.sheet_list: return
        self.sheet_list.clear()
        for i, config in enumerate(self.sheet_configs):
            display_name = config.get('sheet_name', f"Sheet {i+1}")
            if config.get('dynamic_naming', False) and config.get('dynamic_name_field'):
                prefix = config.get('dynamic_name_prefix', '')
                field = config.get('dynamic_name_field')
                display_name = f"{prefix}[{field}] (Dynamic)"
            self.sheet_list.addItem(QListWidgetItem(display_name))

    def _on_sheet_selection_changed(self):
        if not self.sheet_list or not self.sheet_configs: return
        current_row = self.sheet_list.currentRow()
        if 0 <= current_row < len(self.sheet_configs):
            config = self.sheet_configs[current_row]
            self._load_config_to_ui(config)
        else: # 선택된 항목이 없거나 범위를 벗어난 경우 UI 클리어/비활성화
            self._clear_config_ui()

    def _load_config_to_ui(self, config: ExcelSheetConfig):
        # 시트 이름
        is_dynamic = config.get('dynamic_naming', False)
        if self.fixed_name_checkbox: self.fixed_name_checkbox.setChecked(not is_dynamic)
        if self.dynamic_name_checkbox: self.dynamic_name_checkbox.setChecked(is_dynamic)
        if self.fixed_name_input: self.fixed_name_input.setText(config.get('sheet_name', ''))
        if self.dynamic_name_field_combo: self.dynamic_name_field_combo.setCurrentText(config.get('dynamic_name_field', ''))
        if self.dynamic_name_prefix_input: self.dynamic_name_prefix_input.setText(config.get('dynamic_name_prefix', ''))
        self._update_naming_options_enabled_state()

        # 피벗 설정
        if self.index_fields_combo: self.index_fields_combo.setCurrentText(config.get('index_fields', [''])[0] if config.get('index_fields') else '')
        if self.column_fields_combo: self.column_fields_combo.setCurrentText(config.get('column_fields', [''])[0] if config.get('column_fields') else '')
        if self.value_field_combo: self.value_field_combo.setCurrentText(config.get('value_field', ''))
        if self.aggfunc_combo: self.aggfunc_combo.setCurrentText(config.get('aggfunc', 'first'))
        if self.transpose_checkbox: self.transpose_checkbox.setChecked(config.get('transpose', False))

        # TODO: 필터 UI 로드 로직 추가

    def _clear_config_ui(self):
        if self.fixed_name_input: self.fixed_name_input.clear()
        if self.dynamic_name_field_combo: self.dynamic_name_field_combo.setCurrentIndex(-1)
        if self.dynamic_name_prefix_input: self.dynamic_name_prefix_input.clear()
        if self.index_fields_combo: self.index_fields_combo.setCurrentIndex(-1)
        if self.column_fields_combo: self.column_fields_combo.setCurrentIndex(-1)
        if self.value_field_combo: self.value_field_combo.setCurrentIndex(-1)
        if self.aggfunc_combo: self.aggfunc_combo.setCurrentIndex(0) # 기본값 (예: 'first')
        if self.transpose_checkbox: self.transpose_checkbox.setChecked(False)
        if self.fixed_name_checkbox: self.fixed_name_checkbox.setChecked(True) # 기본값
        if self.dynamic_name_checkbox: self.dynamic_name_checkbox.setChecked(False)
        self._update_naming_options_enabled_state()

    def _update_current_sheet_config_from_ui(self):
        if not self.sheet_list or not self.sheet_configs: return
        current_row = self.sheet_list.currentRow()
        if not (0 <= current_row < len(self.sheet_configs)): return

        config = self.sheet_configs[current_row]
        # 시트 이름
        config['dynamic_naming'] = self.dynamic_name_checkbox.isChecked() if self.dynamic_name_checkbox else False
        config['sheet_name'] = self.fixed_name_input.text() if self.fixed_name_input else ''
        config['dynamic_name_field'] = self.dynamic_name_field_combo.currentText() if self.dynamic_name_field_combo else ''
        config['dynamic_name_prefix'] = self.dynamic_name_prefix_input.text() if self.dynamic_name_prefix_input else ''
        
        # 피벗 설정 (단일 필드만 우선 지원, 리스트로 저장)
        idx_field = self.index_fields_combo.currentText() if self.index_fields_combo else ''
        config['index_fields'] = [idx_field] if idx_field else []
        
        col_field = self.column_fields_combo.currentText() if self.column_fields_combo else ''
        config['column_fields'] = [col_field] if col_field else []
        
        config['value_field'] = self.value_field_combo.currentText() if self.value_field_combo else ''
        config['aggfunc'] = self.aggfunc_combo.currentText() if self.aggfunc_combo else 'first'
        config['transpose'] = self.transpose_checkbox.isChecked() if self.transpose_checkbox else False
        
        # TODO: 필터 UI 값 읽어와서 config에 저장하는 로직
        config['global_filters'] = {} # 임시
        config['index_filters'] = {}  # 임시
        config['column_filters'] = {} # 임시

        # 목록 표시 업데이트
        display_name = config.get('sheet_name', f"Sheet {current_row+1}")
        if config.get('dynamic_naming', False) and config.get('dynamic_name_field'):
            prefix = config.get('dynamic_name_prefix', '')
            field = config.get('dynamic_name_field')
            display_name = f"{prefix}[{field}] (Dynamic)"
        list_item = self.sheet_list.item(current_row)
        if list_item: list_item.setText(display_name)
        
    def _add_sheet_config(self, make_default=False):
        default_val_field = self.available_columns[0] if self.available_columns else ''
        # 새 시트의 기본 이름 결정 (중복 피하기)
        base_name = "Sheet"
        new_sheet_idx = 1
        current_sheet_names = {config.get('sheet_name') for config in self.sheet_configs if config.get('sheet_name')}
        new_sheet_name = f"{base_name}{len(self.sheet_configs) + 1}"
        while new_sheet_name in current_sheet_names:
            new_sheet_idx +=1
            new_sheet_name = f"{base_name}{len(self.sheet_configs) + new_sheet_idx}"

        new_config: ExcelSheetConfig = {
            'sheet_name': new_sheet_name,
            'dynamic_naming': False,
            'dynamic_name_field': '',
            'dynamic_name_prefix': '',
            'index_fields': [],
            'column_fields': [],
            'value_field': default_val_field,
            'aggfunc': 'first',
            'transpose': False,
            'global_filters': {},
            'index_filters': {},
            'column_filters': {}
        }
        self.sheet_configs.append(new_config)
        self._populate_sheet_list() # sheet_list UI 업데이트
        if self.sheet_list: # 목록 업데이트 후 새로 추가된 항목 선택
            self.sheet_list.setCurrentRow(self.sheet_list.count() - 1)

    def _remove_selected_sheet(self):
        if not self.sheet_list: return
        current_row = self.sheet_list.currentRow()
        if 0 <= current_row < len(self.sheet_configs):
            if len(self.sheet_configs) == 1:
                QMessageBox.warning(self, "Cannot Remove", "At least one sheet configuration must exist.")
                return
            del self.sheet_configs[current_row]
            self._populate_sheet_list()
            # 선택 조정 (이전 항목 또는 첫 항목)
            new_row_to_select = max(0, current_row - 1) if self.sheet_list.count() > 0 else -1
            if new_row_to_select != -1: self.sheet_list.setCurrentRow(new_row_to_select)
            else: self._clear_config_ui() # 모든 시트가 지워진 경우 (실제로는 위에서 막힘)
        else:
            QMessageBox.information(self, "No Selection", "Please select a sheet configuration to remove.")

    def _duplicate_selected_sheet(self):
        if not self.sheet_list or not self.sheet_configs: return
        current_row = self.sheet_list.currentRow()
        if 0 <= current_row < len(self.sheet_configs):
            original_config = self.sheet_configs[current_row]
            new_config = original_config.copy() # TypedDict는 얕은 복사, 내부 리스트/딕셔너리 주의
            new_config['sheet_name'] = f"{original_config.get('sheet_name', 'Sheet')}_Copy"
            # 내부 필터 딕셔너리 등도 깊은 복사 필요하면 추가 처리
            new_config['global_filters'] = original_config.get('global_filters', {}).copy()
            new_config['index_filters'] = original_config.get('index_filters', {}).copy()
            new_config['column_filters'] = original_config.get('column_filters', {}).copy()

            self.sheet_configs.append(new_config)
            self._populate_sheet_list()
            if self.sheet_list: self.sheet_list.setCurrentRow(len(self.sheet_configs) - 1)
        else:
            QMessageBox.information(self, "No Selection", "Please select a sheet configuration to duplicate.")

    def _save_configuration_to_file(self):
        self._update_current_sheet_config_from_ui() # 저장 전 현재 UI 값 반영
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Export Configuration", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            if not file_path.lower().endswith('.json'): file_path += '.json'
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.sheet_configs, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Success", "Configuration saved successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def _load_configuration_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Excel Export Configuration", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_configs = json.load(f)
                if not isinstance(loaded_configs, list) or \
                   not all(isinstance(item, dict) for item in loaded_configs):
                    raise ValueError("Invalid configuration file format.")
                
                self.sheet_configs = loaded_configs
                self._populate_sheet_list()
                if self.sheet_list and self.sheet_list.count() > 0: 
                    self.sheet_list.setCurrentRow(0)
                else: # 로드된 설정이 비어있으면
                    self._clear_config_ui()
                QMessageBox.information(self, "Success", "Configuration loaded successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load configuration: {e}")

    def get_final_sheet_configs(self) -> List[ExcelSheetConfig]:
        self._update_current_sheet_config_from_ui() # 반환 전 마지막으로 UI 값 반영
        # 여기서 각 config의 유효성 검사를 추가할 수 있음 (예: 필수 필드 존재 여부)
        valid_configs = []
        for i, config in enumerate(self.sheet_configs):
            is_config_valid = True
            # 예시: 값 필드가 없으면 유효하지 않음
            if not config.get('value_field'):
                is_config_valid = False
                QMessageBox.warning(self, "Configuration Error", f"Sheet '{config.get('sheet_name', i+1)}': Value field is not set.")
            
            if is_dynamic := config.get('dynamic_naming', False):
                if not config.get('dynamic_name_field'):
                    is_config_valid = False
                    QMessageBox.warning(self, "Configuration Error", f"Sheet '{config.get('sheet_name', i+1)}': Dynamic name field is required when dynamic naming is enabled.")
            elif not config.get('sheet_name'): # 고정 이름인데 이름이 없는 경우
                 is_config_valid = False
                 QMessageBox.warning(self, "Configuration Error", f"Sheet at index {i}: Fixed sheet name is required.")

            if is_config_valid:
                valid_configs.append(config)
            else:
                # 유효하지 않은 설정을 어떻게 처리할지 결정 (무시, 기본값 사용, 오류 발생 등)
                # 여기서는 일단 유효한 것만 반환
                pass 
        return valid_configs

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    # 테스트용 available_columns
    test_cols = ["Timestamp", "Variable Name", "Value", "Sample Number", "loop_Voltage", "loop_Temperature", "Status"]
    # 테스트용 초기 설정 (비어있거나, 미리 정의된 설정)
    initial_configs = [
        ExcelSheetConfig(sheet_name='DefaultSheet', dynamic_naming=False, dynamic_name_field='', dynamic_name_prefix='',
                         index_fields=['Timestamp'], column_fields=['Variable Name'], value_field='Value',
                         aggfunc='first', transpose=False, global_filters={}, index_filters={}, column_filters={})
    ]
    dialog = ExcelExportSettingsDialog(available_columns=test_cols, current_sheet_configs=initial_configs)
    if dialog.exec_() == QDialog.Accepted:
        final_configs = dialog.get_final_sheet_configs()
        print("Final configurations:", json.dumps(final_configs, indent=2))
    sys.exit(app.exec_())