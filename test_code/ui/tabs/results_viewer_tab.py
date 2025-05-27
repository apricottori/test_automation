# ui/tabs/results_viewer_tab.py
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, # QDialog는 ExcelExportSettingsDialog에서 사용
    QApplication, QStyle 
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

import pandas as pd

# --- 수정된 임포트 경로 ---
from core import constants
# ExcelExportSettingsDialog를 ui.dialogs 패키지에서 임포트
from ui.dialogs.excel_export_dialog import ExcelExportSettingsDialog

class ResultsViewerTab(QWidget):
    clear_results_requested_signal = pyqtSignal()
    export_excel_requested_signal = pyqtSignal(str, list) 

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 10, 8, 8)

        self.excel_sheets_config: List[Dict[str, Any]] = []
        
        # UI 멤버 변수 선언
        self.results_table: Optional[QTableWidget] = None
        self.clear_button: Optional[QPushButton] = None
        self.export_settings_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None

        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        self.results_table = QTableWidget()
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setShowGrid(True)
        
        font_monospace = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        table_font_size = getattr(constants, 'TABLE_FONT_SIZE', 9)
        font_table_data = QFont(font_monospace, table_font_size)
        if self.results_table: self.results_table.setFont(font_table_data)
        if self.results_table: self.results_table.verticalHeader().setVisible(False)

        self._main_layout.addWidget(self.results_table)

        button_layout = QHBoxLayout()
        self.clear_button = QPushButton(constants.RESULTS_CLEAR_BUTTON_TEXT)
        try:
            app_instance = QApplication.instance()
            if app_instance: self.clear_button.setIcon(app_instance.style().standardIcon(QStyle.SP_DialogResetButton))
        except Exception: pass
        
        self.export_settings_button = QPushButton(constants.EXPORT_SETTINGS_BUTTON_TEXT)
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
            self.export_settings_button.clicked.connect(self._show_export_settings_dialog)

    def _on_clear_button_clicked(self):
        self.clear_results_requested_signal.emit()
        print("ResultsViewerTab: clear_results_requested_signal emitted.")

    def _on_export_button_clicked(self):
        # 내보내기 설정 다이얼로그 표시
        parent_window = self.window()
        available_cols: List[str] = []
        if parent_window and hasattr(parent_window, 'results_manager') and \
           hasattr(parent_window.results_manager, 'get_available_export_columns'):
            try:
                available_cols = parent_window.results_manager.get_available_export_columns()
            except Exception as e:
                print(f"Error getting available columns from ResultsManager: {e}")
                # 사용 가능한 컬럼이 없거나 가져오기 실패 시 사용자에게 알리고 중단
                QMessageBox.warning(self, "Error", "Could not retrieve column data for export settings.")
                return
        else:
            QMessageBox.warning(self, "Error", "Results manager not found or inaccessible.")
            return

        if not available_cols: # 컬럼 정보가 비어있으면 더 이상 진행하지 않음
            QMessageBox.information(self, "No Data", "No data columns available to configure for export.")
            return

        # ExcelExportSettingsDialog 인스턴스화
        # self.excel_sheets_config는 List[ExcelSheetConfig] 타입이어야 함
        # 초기 로드 시 또는 설정 변경 시 이 타입으로 변환/유지되도록 보장 필요
        dialog = ExcelExportSettingsDialog(available_cols, self.excel_sheets_config, self)
        
        if dialog.exec_() == QDialog.Accepted:
            final_configs = dialog.get_final_sheet_configs()
            if not final_configs: # 사용자가 유효한 설정을 하나도 만들지 않은 경우
                QMessageBox.information(self, "No Configuration", "No valid sheet configurations were set for export.")
                return

            self.excel_sheets_config = final_configs # 업데이트된 설정 저장

            # 메인 윈도우를 통해 설정 저장 (필요한 경우)
            if parent_window and hasattr(parent_window, 'save_excel_export_config_to_settings'):
                parent_window.save_excel_export_config_to_settings(self.excel_sheets_config)

            # 파일 저장 다이얼로그 표시
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "결과를 Excel 파일로 저장", "", 
                "Excel Files (*.xlsx);;All Files (*)", options=options
            )
            if file_path:
                if not file_path.lower().endswith('.xlsx'): file_path += '.xlsx'
                # export_excel_requested_signal에 최종 확정된 설정 전달
                self.export_excel_requested_signal.emit(file_path, self.excel_sheets_config)
                print(f"ResultsViewerTab: export_excel_requested_signal emitted with path: {file_path} and {len(self.excel_sheets_config)} sheet(s).")

    def _show_export_settings_dialog(self):
        available_cols: List[str] = []
        # 부모 위젯(RegMapWindow)의 results_manager를 통해 사용 가능한 컬럼 가져오기
        parent_window = self.window() # QWidget.window() 사용
        if parent_window and hasattr(parent_window, 'results_manager') and \
           hasattr(parent_window.results_manager, 'get_available_export_columns'):
            try:
                available_cols = parent_window.results_manager.get_available_export_columns()
            except Exception as e:
                print(f"Error getting available columns from ResultsManager: {e}")
                available_cols = ["Timestamp", "Variable Name", "Value", constants.EXCEL_COL_SAMPLE_NO] # 기본값
        else: 
            available_cols = ["Timestamp", "Variable Name", "Value", constants.EXCEL_COL_SAMPLE_NO]
            print("Warning: Could not get available columns from ResultsManager for Excel export settings. Using defaults.")

        # ExcelExportSettingsDialog 사용 (ui.dialogs에서 임포트)
        dialog = ExcelExportSettingsDialog(available_cols, self.excel_sheets_config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.excel_sheets_config = dialog.get_final_sheet_configs()
            # 변경된 설정을 메인 윈도우를 통해 저장
            if parent_window and hasattr(parent_window, 'save_excel_export_config_to_settings'):
                parent_window.save_excel_export_config_to_settings(self.excel_sheets_config)
            
            QMessageBox.information(self, "설정 저장됨", "Excel 내보내기 설정이 업데이트되었습니다.")
            print(f"ResultsViewerTab: Excel export config updated with {len(self.excel_sheets_config)} sheet(s).")

    def set_excel_export_config(self, config: List[Dict[str, Any]]):
        self.excel_sheets_config = [cfg.copy() for cfg in config] # 깊은 복사
        print(f"ResultsViewerTab: Excel export config received with {len(self.excel_sheets_config)} sheet(s).")

    def populate_table(self, results_df: Optional[pd.DataFrame]):
        if self.results_table is None: return

        self.results_table.clearContents()
        self.results_table.setRowCount(0)

        if results_df is None or results_df.empty:
            self.results_table.setColumnCount(0)
            print("ResultsViewerTab: DataFrame이 비어있어 테이블을 비웁니다.")
            if self.export_button: self.export_button.setEnabled(False)
            return

        self.results_table.setColumnCount(len(results_df.columns))
        self.results_table.setHorizontalHeaderLabels(results_df.columns)
        self.results_table.setRowCount(len(results_df))

        for i, row_tuple in enumerate(results_df.itertuples(index=False, name=None)):
            for j, value in enumerate(row_tuple):
                item_value_str = str(value)
                if isinstance(value, pd.Timestamp):
                    try:
                        # 밀리초까지 표시 (소수점 아래 3자리)
                        item_value_str = value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] 
                    except AttributeError: 
                        pass # 이미 문자열이거나 포맷팅 불가능한 경우
                elif pd.isna(value): # Pandas의 NA 값 처리
                    item_value_str = ""

                self.results_table.setItem(i, j, QTableWidgetItem(item_value_str))
        
        self.results_table.resizeColumnsToContents()
        # Timestamp 컬럼 너비 고정 (가독성)
        if 'Timestamp' in results_df.columns:
            try:
                ts_col_index = list(results_df.columns).index('Timestamp')
                self.results_table.setColumnWidth(ts_col_index, 180) # 너비 조정
            except ValueError: pass # 컬럼이 없는 경우
        
        # Value 컬럼은 남은 공간을 채우도록 설정 (선택 사항)
        if 'Value' in results_df.columns:
            try:
                val_col_index = list(results_df.columns).index('Value')
                self.results_table.horizontalHeader().setSectionResizeMode(val_col_index, QHeaderView.Stretch)
            except ValueError: pass
        
        if self.export_button: self.export_button.setEnabled(True)
        print("ResultsViewerTab: Table populated with results.")