# ui/tabs/results_viewer_tab.py
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, QTabWidget,
    QApplication, QStyle, QInputDialog, QListWidget, QListWidgetItem, 
    QDialogButtonBox, QLabel, QComboBox, QGroupBox, QGridLayout, QListView,
    QSplitter, QFrame, QLineEdit, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

import pandas as pd
import os  # 경로 관련 작업을 위해 추가

# --- 수정된 임포트 경로 ---
from core import constants
from core.excel_exporter import ExcelExporter # For preview generation
from core.data_models import ExcelSheetConfig # 필요한 타입 임포트

class SheetConfigDialog(QDialog):
    """Excel 시트 설정 다이얼로그"""
    
    def __init__(self, available_columns: List[str], current_config: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.available_columns = available_columns
        self.current_config = current_config.copy() if current_config else []
        self.result_config = []
        self.current_sheet_index = 0
        
        self.setWindowTitle("Excel 시트 설정")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        self._create_ui()
        self._populate_sheet_list()
        self._connect_signals()
        
        # 초기 시트가 없는 경우 기본 시트 생성
        if not self.current_config:
            self._add_default_sheet()
        
    def _create_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 상단 영역: 시트 목록 및 추가/삭제 버튼
        top_layout = QHBoxLayout()
        
        # 시트 목록
        sheet_group = QGroupBox("시트 목록")
        sheet_layout = QVBoxLayout(sheet_group)
        
        self.sheet_list = QListWidget()
        sheet_layout.addWidget(self.sheet_list)
        
        # 시트 추가/삭제 버튼
        btn_layout = QHBoxLayout()
        self.add_sheet_btn = QPushButton("시트 추가")
        self.delete_sheet_btn = QPushButton("시트 삭제")
        btn_layout.addWidget(self.add_sheet_btn)
        btn_layout.addWidget(self.delete_sheet_btn)
        sheet_layout.addLayout(btn_layout)
        
        top_layout.addWidget(sheet_group, 1)
        
        # 시트 설정 영역
        config_group = QGroupBox("시트 설정")
        config_layout = QGridLayout(config_group)
        
        # 시트 이름
        config_layout.addWidget(QLabel("시트 이름:"), 0, 0)
        self.sheet_name_input = QLineEdit()
        config_layout.addWidget(self.sheet_name_input, 0, 1)
        
        # 행/열 설정
        config_layout.addWidget(QLabel("행 필드:"), 1, 0)
        self.row_field_combo = QComboBox()
        config_layout.addWidget(self.row_field_combo, 1, 1)
        
        config_layout.addWidget(QLabel("열 필드:"), 2, 0)
        self.column_field_combo = QComboBox()
        config_layout.addWidget(self.column_field_combo, 2, 1)
        
        # 전치(행/열 전환) 옵션
        self.transpose_checkbox = QCheckBox("행/열 전치")
        config_layout.addWidget(self.transpose_checkbox, 3, 0, 1, 2)
        
        # 테스트 항목 선택 (Variable Name 값들)
        config_layout.addWidget(QLabel("포함할 테스트 항목:"), 4, 0)
        self.test_items_list = QListWidget()
        self.test_items_list.setSelectionMode(QListWidget.MultiSelection)
        config_layout.addWidget(self.test_items_list, 5, 0, 1, 2)
        
        top_layout.addWidget(config_group, 2)
        
        main_layout.addLayout(top_layout)
        
        # 하단 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def _connect_signals(self):
        self.add_sheet_btn.clicked.connect(self._add_new_sheet)
        self.delete_sheet_btn.clicked.connect(self._delete_current_sheet)
        self.sheet_list.currentRowChanged.connect(self._load_sheet_config)
        self.sheet_name_input.textChanged.connect(self._update_current_sheet_name)
    
    def _populate_sheet_list(self):
        """현재 시트 구성으로 시트 목록 채우기"""
        self.sheet_list.clear()
        
        for config in self.current_config:
            sheet_name = config.get('sheet_name', 'Unnamed Sheet')
            self.sheet_list.addItem(sheet_name)
        
        # 행/열 필드 콤보박스 초기화
        self.row_field_combo.clear()
        self.column_field_combo.clear()
        
        # 기본 "없음" 옵션 추가
        self.row_field_combo.addItem("없음", "")
        self.column_field_combo.addItem("없음", "")
        
        # 부모 창에서 results_df 가져오기
        parent_window = self.parent().window()
        all_columns = []
        if parent_window and hasattr(parent_window, 'results_manager'):
            results_df = parent_window.results_manager.get_results_dataframe()
            if not results_df.empty:
                all_columns = list(results_df.columns)
        else:
            all_columns = self.available_columns
            
        # 사용 가능한 모든 컬럼 추가 (Value 포함)
        for col in all_columns:
            # Value도 행으로 사용 가능하게 함
            self.row_field_combo.addItem(col, col)
            self.column_field_combo.addItem(col, col)
        
        # 테스트 항목 목록 채우기 (Variable Name의 unique 값들)
        self._populate_test_items()
        
        # 첫 번째 시트 선택
        if self.sheet_list.count() > 0:
            self.sheet_list.setCurrentRow(0)
    
    def _populate_test_items(self):
        """테스트 항목 목록 채우기 (results_df의 'Variable Name' 컬럼 기반)"""
        self.test_items_list.clear()
        
        # 부모 창에서 results_df 가져오기
        parent_window = self.parent().window()
        if parent_window and hasattr(parent_window, 'results_manager'):
            results_df = parent_window.results_manager.get_results_dataframe()
            if not results_df.empty and 'Variable Name' in results_df.columns:
                # Variable Name의 고유 값들 가져오기
                unique_var_names = results_df['Variable Name'].unique()
                for var_name in sorted(unique_var_names):
                    item = QListWidgetItem(var_name)
                    self.test_items_list.addItem(item)
    
    def _load_sheet_config(self, index):
        """선택한 시트의 설정 로드"""
        if index < 0 or index >= len(self.current_config):
            return
        
        self.current_sheet_index = index
        config = self.current_config[index]
        
        # 시트 이름
        self.sheet_name_input.setText(config.get('sheet_name', f'Sheet{index+1}'))
        
        # 행 필드
        row_fields = config.get('index_fields', [])
        row_field = row_fields[0] if row_fields else ""
        row_index = self.row_field_combo.findData(row_field)
        self.row_field_combo.setCurrentIndex(max(0, row_index))
        
        # 열 필드
        column_fields = config.get('column_fields', [])
        column_field = column_fields[0] if column_fields else ""
        col_index = self.column_field_combo.findData(column_field)
        self.column_field_combo.setCurrentIndex(max(0, col_index))
        
        # 전치 옵션
        self.transpose_checkbox.setChecked(config.get('transpose', False))
        
        # 테스트 항목 선택
        include_columns = config.get('include_columns', [])
        for i in range(self.test_items_list.count()):
            item = self.test_items_list.item(i)
            item.setSelected(item.text() in include_columns or not include_columns)
    
    def _update_current_sheet_config(self):
        """현재 UI 상태를 기반으로 현재 시트 설정 업데이트"""
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.current_config):
            return
        
        config = self.current_config[self.current_sheet_index]
        
        # 시트 이름
        config['sheet_name'] = self.sheet_name_input.text() or f'Sheet{self.current_sheet_index+1}'
        
        # 행 필드
        row_field = self.row_field_combo.currentData()
        config['index_fields'] = [row_field] if row_field else []
        
        # 열 필드
        column_field = self.column_field_combo.currentData()
        config['column_fields'] = [column_field] if column_field else []
        
        # 전치 옵션
        config['transpose'] = self.transpose_checkbox.isChecked()
        
        # 테스트 항목 선택
        selected_items = []
        for i in range(self.test_items_list.count()):
            if self.test_items_list.item(i).isSelected():
                selected_items.append(self.test_items_list.item(i).text())
        
        # 선택된 항목이 있으면 해당 항목만 포함, 없으면 모든 항목 포함
        config['include_columns'] = selected_items if selected_items else []
        
        # 시트 목록 업데이트
        self.sheet_list.item(self.current_sheet_index).setText(config['sheet_name'])
        
        # 설정 변경 후 즉시 미리보기 업데이트
        parent_dlg = self.parent()
        if parent_dlg and hasattr(parent_dlg, '_update_sheet_previews'):
            parent_dlg._update_sheet_previews()
    
    def _update_current_sheet_name(self):
        """시트 이름 변경 시 시트 목록 업데이트"""
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.current_config):
            return
        
        sheet_name = self.sheet_name_input.text() or f'Sheet{self.current_sheet_index+1}'
        self.current_config[self.current_sheet_index]['sheet_name'] = sheet_name
        self.sheet_list.item(self.current_sheet_index).setText(sheet_name)
    
    def _add_new_sheet(self):
        """새 시트 추가"""
        new_index = len(self.current_config)
        
        # 부모 창에서 results_df 가져오기
        parent_window = self.parent().window()
        available_fields = []
        variable_names = []
        
        if parent_window and hasattr(parent_window, 'results_manager'):
            results_df = parent_window.results_manager.get_results_dataframe()
            if not results_df.empty:
                # 'Variable Name'과 'Value'를 제외한 모든 컬럼을 후보로 추가
                available_fields = [col for col in results_df.columns if col not in ['Variable Name', 'Value']]
                
                # 'Variable Name' 컬럼의 고유 값들을 추출 (시트 이름 참고용)
                if 'Variable Name' in results_df.columns:
                    variable_names = sorted(results_df['Variable Name'].unique())
        
        # 기본 시트 이름 설정 (변수명이 있으면 첫 번째 변수명 활용)
        default_sheet_name = f"Sheet{new_index+1}"
        if variable_names:
            default_sheet_name = f"{variable_names[0]}"
            if len(variable_names) > 1:
                default_sheet_name += " 외"
        
        # 기본 행 필드 설정 (사용 가능한 필드가 있으면 첫 번째 필드 사용)
        default_index_field = []
        if available_fields:
            default_index_field = [available_fields[0]]
        
        new_sheet_config = {
            'sheet_name': default_sheet_name,
            'dynamic_naming': False,
            'dynamic_name_field': "",
            'dynamic_name_prefix': "",
            'index_fields': default_index_field,
            'column_fields': [],
            'transpose': False,
            'include_columns': [],
            'global_filters': None,
            'value_filters': None
        }
        
        self.current_config.append(new_sheet_config)
        self.sheet_list.addItem(default_sheet_name)
        self.sheet_list.setCurrentRow(new_index)
    
    def _add_default_sheet(self):
        """기본 시트 추가"""
        default_sheet_config = {
            'sheet_name': "Data",
            'dynamic_naming': False,
            'dynamic_name_field': "",
            'dynamic_name_prefix': "",
            'index_fields': [],
            'column_fields': [],
            'transpose': False,
            'include_columns': [],
            'global_filters': None,
            'value_filters': None
        }
        
        self.current_config.append(default_sheet_config)
        self.sheet_list.addItem(default_sheet_config['sheet_name'])
        self.sheet_list.setCurrentRow(0)
    
    def _delete_current_sheet(self):
        """현재 선택된 시트 삭제"""
        if self.sheet_list.count() <= 1:  # 최소한 하나의 시트는 유지
            QMessageBox.warning(self, "경고", "최소한 하나의 시트는 유지해야 합니다.")
            return
        
        current_row = self.sheet_list.currentRow()
        if current_row < 0:
            return
        
        # 시트 목록과 설정에서 제거
        self.sheet_list.takeItem(current_row)
        del self.current_config[current_row]
        
        # 남은 시트 중 하나 선택
        new_row = min(current_row, self.sheet_list.count() - 1)
        self.sheet_list.setCurrentRow(new_row)
    
    def accept(self):
        """확인 버튼 클릭 시 현재 설정 저장"""
        self._update_current_sheet_config()  # 현재 편집 중인 시트 설정 저장
        self.result_config = self.current_config
        super().accept()

class ResultsViewerTab(QWidget):
    clear_results_requested_signal = pyqtSignal()
    export_excel_requested_signal = pyqtSignal(str, list) 

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 10, 8, 8)

        self.excel_sheets_config: List[Dict[str, Any]] = []
        self.results_manager = None  # Will be set by MainWindow
        
        # UI 멤버 변수 선언
        self.preview_tab_widget: Optional[QTabWidget] = None # Preview TabWidget
        self.raw_data_table: Optional[QTableWidget] = None # Original table, now for "Raw Data"
        self.clear_button: Optional[QPushButton] = None
        self.export_settings_button: Optional[QPushButton] = None  # 시트 설정 버튼 추가
        self.export_button: Optional[QPushButton] = None

        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        # Main results table (raw data view)
        self.raw_data_table = QTableWidget()
        if self.raw_data_table is None: return # Should not happen

        self.raw_data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.raw_data_table.setAlternatingRowColors(True)
        self.raw_data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.raw_data_table.setShowGrid(True)
        
        font_monospace = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        table_font_size = getattr(constants, 'TABLE_FONT_SIZE', 9)
        font_table_data = QFont(font_monospace, table_font_size)
        self.raw_data_table.setFont(font_table_data)
        self.raw_data_table.verticalHeader().setVisible(False)

        # Preview Tab Widget
        self.preview_tab_widget = QTabWidget()
        self.preview_tab_widget.addTab(self.raw_data_table, "Raw Data")
        self._main_layout.addWidget(self.preview_tab_widget)

        button_layout = QHBoxLayout()
        self.clear_button = QPushButton(constants.RESULTS_CLEAR_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance: self.clear_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogResetButton))
        except Exception: pass
        
        # 시트 설정 버튼 다시 추가
        self.export_settings_button = QPushButton("시트 설정...")
        try:
            app_instance = QApplication.instance()
            if app_instance: self.export_settings_button.setIcon(app_instance.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        except Exception: pass

        self.export_button = QPushButton(constants.RESULTS_EXPORT_BUTTON_TEXT)
        self.export_button.setEnabled(False) 
        try:
            app_instance = QApplication.instance()
            if app_instance: self.export_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogSaveButton))
        except Exception: pass

        button_layout.addStretch()
        if self.clear_button: button_layout.addWidget(self.clear_button)
        if self.export_settings_button: button_layout.addWidget(self.export_settings_button)
        if self.export_button: button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        self._main_layout.addLayout(button_layout)

    def _connect_signals(self):
        if self.clear_button:
            self.clear_button.clicked.connect(self._on_clear_button_clicked)
        if self.export_button:
            self.export_button.clicked.connect(self._on_export_button_clicked)
        if self.export_settings_button:
            self.export_settings_button.clicked.connect(self._on_export_settings_button_clicked)

    def _on_clear_button_clicked(self):
        self.clear_results_requested_signal.emit()
        print("ResultsViewerTab: clear_results_requested_signal emitted.")

    def _on_export_settings_button_clicked(self):
        """시트 설정 다이얼로그 표시"""
        parent_window = self.window()
        if not (parent_window and hasattr(parent_window, 'results_manager')):
            QMessageBox.critical(self, "Error", "Results manager not found or inaccessible.")
            return
        
        results_df = parent_window.results_manager.get_results_dataframe()
        if results_df.empty:
            QMessageBox.information(self, "No Data", "There is no data to export.")
            return
        
        # 사용 가능한 모든 컬럼 가져오기
        available_columns = list(results_df.columns)
        
        # 현재 설정 가져오기
        dialog = SheetConfigDialog(available_columns, self.excel_sheets_config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.excel_sheets_config = dialog.result_config
            self._update_sheet_previews()
            QMessageBox.information(self, "설정 완료", "Excel 시트 설정이 업데이트되었습니다.")

    def _on_export_button_clicked(self):
        parent_window = self.window()
        if not (parent_window and hasattr(parent_window, 'results_manager')):
            QMessageBox.critical(self, "Error", "Results manager not found or inaccessible.")
            return

        results_df = parent_window.results_manager.get_results_dataframe()
        if results_df.empty:
            QMessageBox.information(self, "No Data", "There is no data to export.")
            return
        
        # 설정이 없으면 기본 설정 적용
        if not self.excel_sheets_config:
            self.set_excel_export_config([])
        
        options = QFileDialog.Options()
        
        # 현재 작업 디렉토리를 기본 경로로 사용
        current_dir = os.getcwd()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", current_dir, 
            "Excel Files (*.xlsx);;All Files (*)", options=options
        )
        if file_path:
            if not file_path.lower().endswith('.xlsx'):
                file_path += '.xlsx'
            
            # Timestamp 컬럼 제거
            filtered_df = results_df.copy()
            if 'Timestamp' in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=['Timestamp'])
            
            # Raw Data 시트(첫 번째 시트)를 제외한 시트 구성만 사용
            export_configs = self.excel_sheets_config[1:] if len(self.excel_sheets_config) > 1 else []
            
            # 직접 ExcelExporter 사용
            exporter = ExcelExporter(filtered_df)
            if exporter.export_to_excel(file_path, export_configs):
                QMessageBox.information(self, constants.MSG_TITLE_SUCCESS, f"Results exported to '{file_path}'.")
            else:
                QMessageBox.warning(self, constants.MSG_TITLE_ERROR, "Failed to export Excel file. Check logs.")

    def set_excel_export_config(self, config_list_from_settings: List[Dict[str, Any]]):
        # 기본 Excel 시트 설정을 생성
        self.excel_sheets_config = []
        
        # 기본 Raw Data 시트 설정 추가
        default_sheet_config: ExcelSheetConfig = {
            'sheet_name': "Raw Data",
            'dynamic_naming': False,
            'dynamic_name_field': "",
            'dynamic_name_prefix': "",
            'index_fields': [],
            'column_fields': [],
            'transpose': False,
            'include_columns': [],  # 모든 열 포함
            'global_filters': None,
            'value_filters': None
        }
        self.excel_sheets_config.append(default_sheet_config)
        
        # 설정에서 가져온 시트 구성이 있으면 사용
        if isinstance(config_list_from_settings, list) and config_list_from_settings:
            # 기존 시트 설정을 새 형식으로 변환하여 추가
            for i, cfg_data in enumerate(config_list_from_settings):
                if isinstance(cfg_data, dict):
                    # 모든 필수 키를 가진 기본 설정 생성
                    default_minimal_config = {
                        'sheet_name': f"Sheet{i+1}",
                        'dynamic_naming': False,
                        'dynamic_name_field': "", 
                        'dynamic_name_prefix': "",
                        'index_fields': [],
                        'column_fields': [],
                        'transpose': False,
                        'include_columns': [],
                        'global_filters': None,
                        'value_filters': None
                    }
                    
                    # 구 형식(columns 키)에서 신 형식(include_columns 키)으로 변환
                    if 'columns' in cfg_data and isinstance(cfg_data['columns'], list):
                        # "Variable Name"과 "Value" 열은 항상 필요함
                        # "Timestamp", "Sample Number" 등은 선택적 표시 항목
                        # "Variable Name" 열의 값들(측정 항목 이름)이 include_columns에 들어감
                        columns_without_timestamp = [col for col in cfg_data['columns'] if col != "Timestamp"]
                        
                        if 'Variable Name' in columns_without_timestamp and 'Value' in columns_without_timestamp:
                            # 시트 이름은 그대로 유지
                            default_minimal_config['sheet_name'] = cfg_data.get('sheet_name', f"Sheet{i+1}")
                            
                            # columns에서 "Variable Name"을 제외한 항목들을 index_fields로 사용
                            # (대개 "Sample Number"나 루프 변수들이 여기에 해당)
                            index_candidates = [col for col in columns_without_timestamp if col not in ('Variable Name', 'Value')]
                            if index_candidates:
                                # 첫 번째 항목을 index_fields로 사용
                                default_minimal_config['index_fields'] = [index_candidates[0]]
                            
                            # include_columns는 비워두어 모든 측정 항목 포함
                            default_minimal_config['include_columns'] = []
                        else:
                            # "Variable Name"이나 "Value"가 없으면 그냥 모든 columns를 include_columns로 처리
                            default_minimal_config['include_columns'] = columns_without_timestamp
                    
                    # 설정 병합 (cfg_data의 값이 default_minimal_config를 덮어씀)
                    validated_cfg = {**default_minimal_config, **cfg_data}
                    
                    # 만약 include_columns와 columns가 모두 있다면 include_columns 우선
                    if 'columns' in validated_cfg and 'include_columns' not in cfg_data:
                        validated_cfg.pop('columns')  # 이전 형식의 'columns' 키 제거
                    
                    self.excel_sheets_config.append(validated_cfg)
                else:
                    print(f"Warning: Invalid item type in loaded excel_sheets_config at index {i}")

        print(f"ResultsViewerTab: Excel export config initialized/set with {len(self.excel_sheets_config)} sheet(s).")
        self._update_sheet_previews()

    def populate_table(self, results_df: Optional[pd.DataFrame]):
        if self.raw_data_table is None: return

        self.raw_data_table.clearContents()
        self.raw_data_table.setRowCount(0)

        if results_df is None or results_df.empty:
            self.raw_data_table.setColumnCount(0)
            print("ResultsViewerTab (Raw Data): DataFrame is empty, clearing table.")
            if self.export_button: self.export_button.setEnabled(False)
            self._update_sheet_previews()
            return
        
        # Timestamp 컬럼 제외
        filtered_df = results_df.copy()
        if 'Timestamp' in filtered_df.columns:
            filtered_df = filtered_df.drop(columns=['Timestamp'])

        self.raw_data_table.setColumnCount(len(filtered_df.columns))
        self.raw_data_table.setHorizontalHeaderLabels(filtered_df.columns)
        self.raw_data_table.setRowCount(len(filtered_df))

        for i, row_tuple in enumerate(filtered_df.itertuples(index=False, name=None)):
            for j, value in enumerate(row_tuple):
                item_value_str = str(value)
                if pd.isna(value):
                    item_value_str = ""

                self.raw_data_table.setItem(i, j, QTableWidgetItem(item_value_str))
        
        self.raw_data_table.resizeColumnsToContents()
        
        # Value 컬럼은 남은 공간을 채우도록 설정
        if 'Value' in filtered_df.columns:
            try:
                val_col_index = list(filtered_df.columns).index('Value')
                self.raw_data_table.horizontalHeader().setSectionResizeMode(val_col_index, QHeaderView.Stretch)
            except ValueError: pass
        
        if self.export_button: self.export_button.setEnabled(True)
        print("ResultsViewerTab (Raw Data): Table populated with results.")
        self._update_sheet_previews()

    def _update_sheet_previews(self):
        if self.preview_tab_widget is None: return
        
        # 탭을 Raw Data만 남기고 모두 제거
        while self.preview_tab_widget.count() > 1:
            self.preview_tab_widget.removeTab(1)

        parent_window = self.window()
        if not (parent_window and hasattr(parent_window, 'results_manager')):
            print("Warning: Results manager not found for preview generation.")
            return
        
        full_results_df = parent_window.results_manager.get_results_dataframe()
        if full_results_df.empty:
            print("Info: No data for preview.")
            return
        
        # 성능을 위해 미리보기로 생성할 최대 시트 수 제한
        MAX_PREVIEW_SHEETS = 5
        
        # Raw Data 이후의 모든 시트에 대한 미리보기 생성
        if len(self.excel_sheets_config) > 1:
            # Timestamp 컬럼 제외
            filtered_df = full_results_df.copy()
            if 'Timestamp' in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=['Timestamp'])

            exporter = ExcelExporter(filtered_df)
            
            # 추가 시트 미리보기 생성 (최대 MAX_PREVIEW_SHEETS개)
            preview_count = 0
            for config in self.excel_sheets_config[1:]:  # Raw Data 다음부터 모든 시트
                if preview_count >= MAX_PREVIEW_SHEETS:
                    break
                    
                sheet_name = config.get('sheet_name', 'Preview')
                
                try:
                    # 피벗 테이블 생성 로직은 ExcelExporter._prepare_sheet_data에 위임
                    # 필터링, 피벗팅, 열 순서 조정 등이 일관되게 적용됨
                    preview_df = exporter._prepare_sheet_data(filtered_df, config)
                    
                    if not preview_df.empty:
                        preview_table = QTableWidget()
                        preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                        preview_table.setAlternatingRowColors(True)
                        preview_table.setFont(self.raw_data_table.font() if self.raw_data_table else QFont())
                        preview_table.verticalHeader().setVisible(False)
                        
                        # 테이블에 데이터 채우기
                        preview_table.setColumnCount(len(preview_df.columns))
                        preview_table.setHorizontalHeaderLabels([str(col) for col in preview_df.columns])
                        preview_table.setRowCount(len(preview_df))
                        
                        # 인덱스가 있는 경우(피벗 테이블) 인덱스도 표시
                        has_index = not preview_df.index.equals(pd.RangeIndex(len(preview_df)))
                        if has_index:
                            preview_table.setVerticalHeaderLabels([str(idx) for idx in preview_df.index])
                            preview_table.verticalHeader().setVisible(True)
                        
                        for r_idx, r_data in enumerate(preview_df.itertuples(index=False)):
                            for c_idx, value in enumerate(r_data):
                                item_value_str = "" if pd.isna(value) else str(value)
                                preview_table.setItem(r_idx, c_idx, QTableWidgetItem(item_value_str))
                        
                        preview_table.resizeColumnsToContents()
                        self.preview_tab_widget.addTab(preview_table, sheet_name)
                        preview_count += 1
                except Exception as e:
                    print(f"Error generating preview for sheet '{sheet_name}': {e}")
                    import traceback
                    traceback.print_exc()
                
        print(f"ResultsViewerTab: Sheet preview updated. Total tabs: {self.preview_tab_widget.count()}")