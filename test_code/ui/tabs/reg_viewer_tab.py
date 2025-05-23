# ui/tabs/reg_viewer_tab.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from typing import Optional, Tuple, List

# --- 수정된 임포트 경로 ---
from core import constants 
from core.data_models import LogicalFieldInfo # 타입 힌팅용
from core.register_map_backend import RegisterMap # RegisterMap 객체 타입 힌팅 및 사용
from core.helpers import normalize_hex_input 

class RegisterViewerTab(QWidget):
    """
    "Register_Viewer" 탭의 UI 및 로직을 담당하는 클래스입니다.
    RegisterMap 객체로부터 레지스터 정보를 받아 테이블 형태로 표시합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 10, 8, 8)

        self.reg_table: Optional[QTableWidget] = None
        self._create_ui()

    def _create_ui(self):
        """Register Viewer 탭의 UI 요소(테이블)를 생성합니다."""
        self.reg_table = QTableWidget()
        if self.reg_table is None: return

        self.reg_table.setColumnCount(6)
        self.reg_table.setHorizontalHeaderLabels([
            constants.REG_VIEWER_COL_REGISTER_NAME,
            constants.REG_VIEWER_COL_ACCESS,
            constants.REG_VIEWER_COL_LENGTH,
            constants.REG_VIEWER_COL_ADDRESS,
            constants.REG_VIEWER_COL_VALUE_HEX,
            constants.REG_VIEWER_COL_DESCRIPTION 
        ])
        self.reg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.reg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.reg_table.setAlternatingRowColors(True)
        self.reg_table.setShowGrid(True)

        header = self.reg_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.Interactive) # Register Name
            self.reg_table.setColumnWidth(0, 220) 
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Access
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Length
            header.setSectionResizeMode(3, QHeaderView.Interactive) # Address
            self.reg_table.setColumnWidth(3, 160) 
            header.setSectionResizeMode(4, QHeaderView.Interactive) # Value
            self.reg_table.setColumnWidth(4, 120)
            header.setSectionResizeMode(5, QHeaderView.Stretch) # Description

        if self.reg_table.verticalHeader():
            self.reg_table.verticalHeader().setVisible(False)
        
        self.reg_table.setWordWrap(False) # Description 컬럼도 일단 False 유지, 필요시 True

        font_monospace = getattr(constants, 'FONT_MONOSPACE', 'Consolas')
        table_font_size = getattr(constants, 'TABLE_FONT_SIZE', 10)
        font_table_data = QFont(font_monospace, table_font_size)
        self.reg_table.setFont(font_table_data)

        self._main_layout.addWidget(self.reg_table)

    def populate_table(self, register_map: Optional[RegisterMap]):
        """
        주어진 RegisterMap 객체의 현재 상태를 기반으로 테이블 내용을 채웁니다.
        """
        if self.reg_table is None:
            print("Error: RegisterViewerTab - reg_table is not initialized.")
            return
            
        self.reg_table.setRowCount(0)
        if not register_map or not register_map.logical_fields_map:
            self.reg_table.clearContents()
            print("RegisterViewerTab: RegisterMap이 없거나 필드가 없어 테이블을 비웁니다.")
            return

        fields_info_list = register_map.get_all_logical_fields_info()

        def get_sort_key(field_info_item: LogicalFieldInfo) -> Tuple[int, str]:
            # regions_mapping이 있고, 비어있지 않은지 확인
            if field_info_item.get('regions_mapping') and field_info_item['regions_mapping']:
                first_addr_hex = field_info_item['regions_mapping'][0][0]
                try:
                    # normalize_hex_input 함수 직접 사용
                    addr_int = int(normalize_hex_input(first_addr_hex, add_prefix=True) or "0xFFFF", 16)
                    return (addr_int, field_info_item['id'])
                except (ValueError, TypeError):
                    # 주소 파싱 실패 시 정렬 우선순위를 낮춤
                    return (0xFFFF, field_info_item['id']) 
            return (0xFFFF, field_info_item['id']) # regions_mapping이 없는 경우

        try:
            fields_info_list.sort(key=get_sort_key)
        except Exception as e:
            print(f"Error sorting fields in RegisterViewerTab: {e}")
            # 정렬 실패 시에도 나머지 로직은 진행하도록 함

        self.reg_table.setSortingEnabled(False) # 데이터 채우는 동안 정렬 비활성화
        for field_info in fields_info_list:
            row_position = self.reg_table.rowCount()
            self.reg_table.insertRow(row_position)

            # Register Name
            self.reg_table.setItem(row_position, 0, QTableWidgetItem(field_info['id']))
            
            # Access
            item_access = QTableWidgetItem(field_info['access'])
            item_access.setTextAlignment(Qt.AlignCenter)
            self.reg_table.setItem(row_position, 1, item_access)
            
            # Length
            item_length = QTableWidgetItem(str(field_info['length']))
            item_length.setTextAlignment(Qt.AlignCenter)
            self.reg_table.setItem(row_position, 2, item_length)

            # Address
            addr_display = "N/A"
            if field_info.get('regions_mapping'):
                try:
                    # 주소 문자열을 정수형으로 변환하여 정렬 후 다시 문자열로 포맷팅
                    addrs_in_field_int = sorted(list(set(
                        int(normalize_hex_input(addr, add_prefix=True) or "0", 16) 
                        for addr, _, _, _, _ in field_info['regions_mapping']
                        if normalize_hex_input(addr, add_prefix=True) # 유효한 hex 주소만 필터링
                    )))
                    if addrs_in_field_int:
                        min_a_int = addrs_in_field_int[0]
                        max_a_int = addrs_in_field_int[-1]
                        min_a_hex = f"0X{min_a_int:04X}"
                        max_a_hex = f"0X{max_a_int:04X}"
                        addr_display = f"{min_a_hex} - {max_a_hex}" if min_a_hex != max_a_hex else min_a_hex
                except (ValueError, TypeError) as e:
                    print(f"Warning: Error processing addresses for field '{field_info['id']}': {e}")
                    addr_display = "ErrAddr" # 주소 처리 중 오류 발생 시
            item_addr = QTableWidgetItem(addr_display)
            item_addr.setTextAlignment(Qt.AlignCenter)
            self.reg_table.setItem(row_position, 3, item_addr)

            # Value (Hex)
            current_val_hex = register_map.get_logical_field_value_hex(field_info['id'], from_initial=False)
            item_value = QTableWidgetItem(current_val_hex)
            item_value.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.reg_table.setItem(row_position, 4, item_value)
            
            # Description - 수정된 부분
            description_text = field_info.get('description') or '' # None일 경우 빈 문자열로 처리
            desc_item = QTableWidgetItem(description_text)
            self.reg_table.setItem(row_position, 5, desc_item)

        self.reg_table.setSortingEnabled(True) # 데이터 채운 후 정렬 활성화
        if self.reg_table.columnCount() > 3: # 주소 컬럼(인덱스 3) 기준으로 초기 정렬
            self.reg_table.sortByColumn(3, Qt.AscendingOrder)

        print("RegisterViewerTab: Table populated.")