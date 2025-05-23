# ui/widgets/action_input_panel.py
import sys
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QStackedWidget, QGridLayout, QDoubleSpinBox, QCompleter, QTabWidget,
    QMessageBox, QApplication, QStyle
)
from PyQt5.QtCore import Qt, QRegularExpression, QStringListModel, pyqtSignal
from PyQt5.QtGui import QRegularExpressionValidator, QFont, QDoubleValidator

from core import constants
from core.helpers import normalize_hex_input
from core.register_map_backend import RegisterMap


class ActionInputPanel(QWidget):
    """
    SequenceControllerTab의 좌측 상단, 액션 그룹 탭 및
    각 액션의 파라미터 입력을 담당하는 위젯입니다.
    """

    class I2CParamPages:
        WRITE_NAME = 0
        WRITE_ADDR = 1
        READ_NAME = 2
        READ_ADDR = 3
        DELAY = 4
        PLACEHOLDER = 5

    class DMMParamPages:
        MEASURE = 0
        SET_TERMINAL = 1
        PLACEHOLDER = 2

    class SMUParamPages:
        SET_VALUE = 0
        MEASURE = 1
        ENABLE_OUTPUT = 2
        SET_TERMINAL = 3
        SET_PROTECTION_I = 4
        PLACEHOLDER = 5

    class TempParamPages:
        SET_TEMP = 0
        CHECK_TEMP = 1
        PLACEHOLDER = 2


    def __init__(self,
                 completer_model: QStringListModel,
                 current_settings: Dict[str, Any],
                 register_map_instance: Optional[RegisterMap],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.completer_model = completer_model
        self.current_settings = current_settings if current_settings is not None else {}
        self.register_map = register_map_instance

        # UI 멤버 변수 초기화
        self.action_group_tabs: Optional[QTabWidget] = None
        self.i2c_tab_widget: Optional[QWidget] = None
        self.i2c_action_combo: Optional[QComboBox] = None
        self.i2c_params_stack: Optional[QStackedWidget] = None
        self.i2c_write_name_target_input: Optional[QLineEdit] = None
        self.i2c_write_name_value_input: Optional[QLineEdit] = None
        self.i2c_write_addr_target_input: Optional[QLineEdit] = None
        self.i2c_write_addr_value_input: Optional[QLineEdit] = None
        self.i2c_read_name_target_input: Optional[QLineEdit] = None
        self.i2c_read_name_var_name_input: Optional[QLineEdit] = None
        self.i2c_read_addr_target_input: Optional[QLineEdit] = None
        self.i2c_read_addr_var_name_input: Optional[QLineEdit] = None
        self.delay_seconds_input: Optional[QDoubleSpinBox] = None

        self.dmm_tab_widget: Optional[QWidget] = None
        self.dmm_action_combo: Optional[QComboBox] = None
        self.dmm_params_stack: Optional[QStackedWidget] = None
        self.dmm_measure_var_name_input: Optional[QLineEdit] = None
        self.dmm_terminal_combo: Optional[QComboBox] = None

        self.smu_tab_widget: Optional[QWidget] = None
        self.smu_action_combo: Optional[QComboBox] = None
        self.smu_params_stack: Optional[QStackedWidget] = None
        self.smu_set_value_label: Optional[QLabel] = None
        self.smu_set_value_input: Optional[QLineEdit] = None
        self.smu_set_terminal_combo: Optional[QComboBox] = None
        self.smu_measure_var_name_input: Optional[QLineEdit] = None
        self.smu_measure_terminal_combo: Optional[QComboBox] = None
        self.smu_output_state_combo: Optional[QComboBox] = None
        self.smu_terminal_combo: Optional[QComboBox] = None
        self.smu_protection_current_input: Optional[QLineEdit] = None

        self.temp_tab_widget: Optional[QWidget] = None
        self.temp_action_combo: Optional[QComboBox] = None
        self.temp_params_stack: Optional[QStackedWidget] = None
        self.chamber_set_temp_input: Optional[QLineEdit] = None
        self.chamber_check_target_temp_input: Optional[QLineEdit] = None
        self.chamber_check_tolerance_input: Optional[QLineEdit] = None
        self.chamber_check_timeout_input: Optional[QLineEdit] = None

        self._hex_validator = QRegularExpressionValidator(QRegularExpression("[0-9A-Fa-fXx]*"))
        self._double_validator = QDoubleValidator()
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        self._double_validator.setDecimals(6)

        self._setup_ui()
        self.update_settings(self.current_settings)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)

        self.action_group_tabs = QTabWidget()
        self.action_group_tabs.currentChanged.connect(self._update_active_sub_tab_fields)

        self._create_i2c_delay_sub_tab()
        self._create_dmm_sub_tab()
        self._create_smu_sub_tab()
        self._create_temp_sub_tab()

        main_layout.addWidget(self.action_group_tabs)
        self._update_active_sub_tab_fields()

    def _normalize_hex_field(self, line_edit: QLineEdit, num_chars: Optional[int] = None, add_prefix: bool = True):
        if not line_edit: return
        current_text = line_edit.text()
        original_tooltip = line_edit.toolTip()

        normalized_text = normalize_hex_input(current_text, num_chars, add_prefix=add_prefix)

        if normalized_text is None and current_text.strip():
            line_edit.setToolTip(f"Invalid hex value: '{current_text}'. Please enter a valid hex string (e.g., 0xAB or FF).")
            line_edit.setStyleSheet("border: 1px solid red;")
        elif normalized_text is not None:
            line_edit.setText(normalized_text)
            line_edit.setToolTip(original_tooltip if original_tooltip else "")
            line_edit.setStyleSheet("")
        else:
            line_edit.setToolTip(original_tooltip if original_tooltip else "")
            line_edit.setStyleSheet("")
            if not current_text.strip() and normalized_text:
                 line_edit.setText(normalized_text)


    def _create_i2c_delay_sub_tab(self):
        tab = QWidget()
        self.i2c_tab_widget = tab
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>I2C/Delay Action:</b>")); self.i2c_action_combo = QComboBox()
        self.i2c_action_combo.addItems(constants.I2C_DELAY_ACTIONS_LIST)
        self.i2c_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.i2c_action_combo); self.i2c_params_stack = QStackedWidget()
        self._create_i2c_delay_params_widgets(); layout.addWidget(self.i2c_params_stack)
        layout.addStretch(); self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_I2C_TITLE)

    def _create_i2c_delay_params_widgets(self):
        completer = QCompleter(self.completer_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive); completer.setFilterMode(Qt.MatchContains)

        page_i2c_write_name = QWidget(); layout_i2c_write_name = QGridLayout(page_i2c_write_name); layout_i2c_write_name.setVerticalSpacing(12); layout_i2c_write_name.setHorizontalSpacing(8)
        layout_i2c_write_name.addWidget(QLabel(constants.SEQ_INPUT_REG_NAME_LABEL), 0, 0); self.i2c_write_name_target_input = QLineEdit(); self.i2c_write_name_target_input.setPlaceholderText(constants.SEQ_INPUT_REG_NAME_PLACEHOLDER); self.i2c_write_name_target_input.setCompleter(completer)
        layout_i2c_write_name.addWidget(self.i2c_write_name_target_input, 0, 1); layout_i2c_write_name.addWidget(QLabel(constants.SEQ_INPUT_I2C_VALUE_LABEL), 1, 0); self.i2c_write_name_value_input = QLineEdit(); self.i2c_write_name_value_input.setPlaceholderText(constants.SEQ_INPUT_I2C_VALUE_PLACEHOLDER); self.i2c_write_name_value_input.setValidator(self._hex_validator)
        self.i2c_write_name_value_input.editingFinished.connect(lambda le=self.i2c_write_name_value_input: self._normalize_hex_field(le, add_prefix=True))
        layout_i2c_write_name.addWidget(self.i2c_write_name_value_input, 1, 1); self.i2c_params_stack.addWidget(page_i2c_write_name)

        page_i2c_write_addr = QWidget(); layout_i2c_write_addr = QGridLayout(page_i2c_write_addr); layout_i2c_write_addr.setVerticalSpacing(12); layout_i2c_write_addr.setHorizontalSpacing(8)
        layout_i2c_write_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_ADDR_LABEL), 0, 0); self.i2c_write_addr_target_input = QLineEdit(); self.i2c_write_addr_target_input.setPlaceholderText(constants.SEQ_INPUT_I2C_ADDR_PLACEHOLDER); self.i2c_write_addr_target_input.setValidator(self._hex_validator)
        self.i2c_write_addr_target_input.editingFinished.connect(lambda le=self.i2c_write_addr_target_input, nc=4: self._normalize_hex_field(le, nc, add_prefix=True))
        layout_i2c_write_addr.addWidget(self.i2c_write_addr_target_input, 0, 1); layout_i2c_write_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_VALUE_LABEL), 1, 0); self.i2c_write_addr_value_input = QLineEdit(); self.i2c_write_addr_value_input.setPlaceholderText(constants.SEQ_INPUT_I2C_VALUE_PLACEHOLDER); self.i2c_write_addr_value_input.setValidator(self._hex_validator)
        self.i2c_write_addr_value_input.editingFinished.connect(lambda le=self.i2c_write_addr_value_input, nc=2: self._normalize_hex_field(le, nc, add_prefix=True))
        layout_i2c_write_addr.addWidget(self.i2c_write_addr_value_input, 1, 1); self.i2c_params_stack.addWidget(page_i2c_write_addr)

        page_i2c_read_name = QWidget(); layout_i2c_read_name = QGridLayout(page_i2c_read_name); layout_i2c_read_name.setVerticalSpacing(12); layout_i2c_read_name.setHorizontalSpacing(8)
        layout_i2c_read_name.addWidget(QLabel(constants.SEQ_INPUT_REG_NAME_LABEL), 0, 0); self.i2c_read_name_target_input = QLineEdit(); self.i2c_read_name_target_input.setPlaceholderText(constants.SEQ_INPUT_REG_NAME_PLACEHOLDER); self.i2c_read_name_target_input.setCompleter(completer)
        layout_i2c_read_name.addWidget(self.i2c_read_name_target_input, 0, 1); layout_i2c_read_name.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 1, 0); self.i2c_read_name_var_name_input = QLineEdit(); self.i2c_read_name_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_i2c_read_name.addWidget(self.i2c_read_name_var_name_input, 1, 1); self.i2c_params_stack.addWidget(page_i2c_read_name)

        page_i2c_read_addr = QWidget(); layout_i2c_read_addr = QGridLayout(page_i2c_read_addr); layout_i2c_read_addr.setVerticalSpacing(12); layout_i2c_read_addr.setHorizontalSpacing(8)
        layout_i2c_read_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_ADDR_LABEL), 0, 0); self.i2c_read_addr_target_input = QLineEdit(); self.i2c_read_addr_target_input.setPlaceholderText(constants.SEQ_INPUT_I2C_ADDR_PLACEHOLDER); self.i2c_read_addr_target_input.setValidator(self._hex_validator)
        self.i2c_read_addr_target_input.editingFinished.connect(lambda le=self.i2c_read_addr_target_input, nc=4: self._normalize_hex_field(le, nc, add_prefix=True))
        layout_i2c_read_addr.addWidget(self.i2c_read_addr_target_input, 0, 1); layout_i2c_read_addr.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 1, 0); self.i2c_read_addr_var_name_input = QLineEdit(); self.i2c_read_addr_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_i2c_read_addr.addWidget(self.i2c_read_addr_var_name_input, 1, 1); self.i2c_params_stack.addWidget(page_i2c_read_addr)

        page_delay = QWidget(); layout_delay = QGridLayout(page_delay); layout_delay.setVerticalSpacing(12); layout_delay.setHorizontalSpacing(8)
        layout_delay.addWidget(QLabel(constants.SEQ_INPUT_DELAY_LABEL), 0, 0); self.delay_seconds_input = QDoubleSpinBox(); self.delay_seconds_input.setMinimum(0.001); self.delay_seconds_input.setMaximum(3600.0 * 24); self.delay_seconds_input.setDecimals(3); self.delay_seconds_input.setValue(0.01)
        layout_delay.addWidget(self.delay_seconds_input, 0, 1); self.i2c_params_stack.addWidget(page_delay)

        page_placeholder_i2c = QWidget(); layout_placeholder_i2c = QVBoxLayout(page_placeholder_i2c); layout_placeholder_i2c.addWidget(QLabel("Select an I2C/Delay action above."), alignment=Qt.AlignCenter); self.i2c_params_stack.addWidget(page_placeholder_i2c)

    def _create_dmm_sub_tab(self):
        tab = QWidget(); self.dmm_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>DMM Action:</b>")); self.dmm_action_combo = QComboBox()
        self.dmm_action_combo.addItems(constants.DMM_ACTIONS_LIST)
        self.dmm_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.dmm_action_combo); self.dmm_params_stack = QStackedWidget()
        self._create_dmm_params_widgets(); layout.addWidget(self.dmm_params_stack)
        layout.addStretch(); self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_DMM_TITLE)

    def _create_dmm_params_widgets(self):
        page_dmm_measure = QWidget(); layout_dmm_measure = QGridLayout(page_dmm_measure); layout_dmm_measure.setVerticalSpacing(12); layout_dmm_measure.setHorizontalSpacing(8)
        layout_dmm_measure.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 0, 0); self.dmm_measure_var_name_input = QLineEdit(); self.dmm_measure_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_dmm_measure.addWidget(self.dmm_measure_var_name_input, 0, 1); self.dmm_params_stack.addWidget(page_dmm_measure)

        page_dmm_set_terminal = QWidget(); layout_dmm_set_terminal = QGridLayout(page_dmm_set_terminal); layout_dmm_set_terminal.setVerticalSpacing(12); layout_dmm_set_terminal.setHorizontalSpacing(8)
        layout_dmm_set_terminal.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 0, 0); self.dmm_terminal_combo = QComboBox(); self.dmm_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_dmm_set_terminal.addWidget(self.dmm_terminal_combo, 0, 1); self.dmm_params_stack.addWidget(page_dmm_set_terminal)

        page_placeholder_dmm = QWidget(); layout_placeholder_dmm = QVBoxLayout(page_placeholder_dmm); layout_placeholder_dmm.addWidget(QLabel("Select a DMM action above."), alignment=Qt.AlignCenter); self.dmm_params_stack.addWidget(page_placeholder_dmm)

    def _create_smu_sub_tab(self):
        tab = QWidget(); self.smu_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>SMU Action:</b>")); self.smu_action_combo = QComboBox()
        self.smu_action_combo.addItems(constants.SMU_ACTIONS_LIST)
        self.smu_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.smu_action_combo); self.smu_params_stack = QStackedWidget()
        self._create_smu_params_widgets(); layout.addWidget(self.smu_params_stack)
        layout.addStretch(); self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_SMU_TITLE)

    def _create_smu_params_widgets(self):
        page_smu_set = QWidget(); layout_smu_set = QGridLayout(page_smu_set); layout_smu_set.setVerticalSpacing(12); layout_smu_set.setHorizontalSpacing(8)
        self.smu_set_value_label = QLabel(constants.SEQ_INPUT_NUMERIC_VALUE_LABEL); layout_smu_set.addWidget(self.smu_set_value_label, 0, 0); self.smu_set_value_input = QLineEdit(); self.smu_set_value_input.setValidator(self._double_validator); self.smu_set_value_input.setPlaceholderText(constants.SEQ_INPUT_NUMERIC_VALUE_PLACEHOLDER)
        layout_smu_set.addWidget(self.smu_set_value_input, 0, 1); layout_smu_set.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 1, 0); self.smu_set_terminal_combo = QComboBox(); self.smu_set_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_set.addWidget(self.smu_set_terminal_combo, 1, 1); self.smu_params_stack.addWidget(page_smu_set)

        page_smu_measure = QWidget(); layout_smu_measure = QGridLayout(page_smu_measure); layout_smu_measure.setVerticalSpacing(12); layout_smu_measure.setHorizontalSpacing(8)
        layout_smu_measure.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 0, 0); self.smu_measure_var_name_input = QLineEdit(); self.smu_measure_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_smu_measure.addWidget(self.smu_measure_var_name_input, 0, 1); layout_smu_measure.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 1, 0); self.smu_measure_terminal_combo = QComboBox(); self.smu_measure_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_measure.addWidget(self.smu_measure_terminal_combo, 1, 1); self.smu_params_stack.addWidget(page_smu_measure)

        page_smu_enable_output = QWidget(); layout_smu_enable_output = QGridLayout(page_smu_enable_output); layout_smu_enable_output.setVerticalSpacing(12); layout_smu_enable_output.setHorizontalSpacing(8)
        layout_smu_enable_output.addWidget(QLabel(constants.SEQ_INPUT_OUTPUT_STATE_LABEL), 0, 0); self.smu_output_state_combo = QComboBox(); self.smu_output_state_combo.addItems([constants.BOOL_TRUE, constants.BOOL_FALSE])
        layout_smu_enable_output.addWidget(self.smu_output_state_combo, 0, 1); self.smu_params_stack.addWidget(page_smu_enable_output)

        page_smu_set_terminal = QWidget(); layout_smu_set_terminal = QGridLayout(page_smu_set_terminal); layout_smu_set_terminal.setVerticalSpacing(12); layout_smu_set_terminal.setHorizontalSpacing(8)
        layout_smu_set_terminal.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 0, 0); self.smu_terminal_combo = QComboBox(); self.smu_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_set_terminal.addWidget(self.smu_terminal_combo, 0, 1); self.smu_params_stack.addWidget(page_smu_set_terminal)

        page_smu_set_protection_i = QWidget(); layout_smu_set_protection_i = QGridLayout(page_smu_set_protection_i); layout_smu_set_protection_i.setVerticalSpacing(12); layout_smu_set_protection_i.setHorizontalSpacing(8)
        layout_smu_set_protection_i.addWidget(QLabel(constants.SEQ_INPUT_CURRENT_LIMIT_LABEL), 0, 0); self.smu_protection_current_input = QLineEdit(); self.smu_protection_current_input.setValidator(self._double_validator); self.smu_protection_current_input.setPlaceholderText("e.g., 0.1 (for 100mA)")
        layout_smu_set_protection_i.addWidget(self.smu_protection_current_input, 0, 1); self.smu_params_stack.addWidget(page_smu_set_protection_i)

        page_placeholder_smu = QWidget(); layout_placeholder_smu = QVBoxLayout(page_placeholder_smu); layout_placeholder_smu.addWidget(QLabel("Select an SMU action above."), alignment=Qt.AlignCenter); self.smu_params_stack.addWidget(page_placeholder_smu)

    def _create_temp_sub_tab(self):
        tab = QWidget(); self.temp_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>Chamber Action:</b>")); self.temp_action_combo = QComboBox()
        self.temp_action_combo.addItems(constants.TEMP_ACTIONS_LIST)
        self.temp_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.temp_action_combo); self.temp_params_stack = QStackedWidget()
        self._create_temp_params_widgets(); layout.addWidget(self.temp_params_stack)
        layout.addStretch(); self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_TEMP_TITLE)

    def _create_temp_params_widgets(self):
        double_validator_temp = QDoubleValidator(); double_validator_temp.setNotation(QDoubleValidator.StandardNotation); double_validator_temp.setDecimals(2)

        page_chamber_set_temp = QWidget(); layout_chamber_set_temp = QGridLayout(page_chamber_set_temp); layout_chamber_set_temp.setVerticalSpacing(12); layout_chamber_set_temp.setHorizontalSpacing(8)
        layout_chamber_set_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0); self.chamber_set_temp_input = QLineEdit(); self.chamber_set_temp_input.setValidator(double_validator_temp); self.chamber_set_temp_input.setPlaceholderText("e.g., 25.0")
        layout_chamber_set_temp.addWidget(self.chamber_set_temp_input, 0, 1); self.temp_params_stack.addWidget(page_chamber_set_temp)

        page_chamber_check_temp = QWidget(); layout_chamber_check_temp = QGridLayout(page_chamber_check_temp); layout_chamber_check_temp.setVerticalSpacing(12); layout_chamber_check_temp.setHorizontalSpacing(8)
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0); self.chamber_check_target_temp_input = QLineEdit(); self.chamber_check_target_temp_input.setValidator(double_validator_temp); self.chamber_check_target_temp_input.setPlaceholderText("e.g., 25.0")
        layout_chamber_check_temp.addWidget(self.chamber_check_target_temp_input, 0, 1);
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TOLERANCE_LABEL), 1, 0); self.chamber_check_tolerance_input = QLineEdit(); self.chamber_check_tolerance_input.setValidator(QDoubleValidator(0.01, 10.0, 2)); self.chamber_check_tolerance_input.setPlaceholderText(f"e.g., {constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG}")
        layout_chamber_check_temp.addWidget(self.chamber_check_tolerance_input, 1, 1);
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TIMEOUT_LABEL), 2, 0); self.chamber_check_timeout_input = QLineEdit(); self.chamber_check_timeout_input.setValidator(QDoubleValidator(1.0, 3600.0 * 3, 1)); self.chamber_check_timeout_input.setPlaceholderText(f"e.g., {constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC}")
        layout_chamber_check_temp.addWidget(self.chamber_check_timeout_input, 2, 1); self.temp_params_stack.addWidget(page_chamber_check_temp)

        page_placeholder_temp = QWidget(); layout_placeholder_temp = QVBoxLayout(page_placeholder_temp); layout_placeholder_temp.addWidget(QLabel("Select a Chamber action above."), alignment=Qt.AlignCenter); self.temp_params_stack.addWidget(page_placeholder_temp)

    def _update_active_sub_tab_fields(self, index: Optional[int] = None):
        if not self.action_group_tabs: return
        current_tab_index = self.action_group_tabs.currentIndex()

        if current_tab_index == 0:
            if not self.i2c_action_combo or not self.i2c_params_stack: return
            action_text = self.i2c_action_combo.currentText()
            if action_text == constants.ACTION_I2C_WRITE_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_NAME)
            elif action_text == constants.ACTION_I2C_WRITE_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_ADDR)
            elif action_text == constants.ACTION_I2C_READ_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_NAME)
            elif action_text == constants.ACTION_I2C_READ_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_ADDR)
            elif action_text == constants.ACTION_DELAY: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.DELAY)
            else: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.PLACEHOLDER)
        elif current_tab_index == 1:
            if not self.dmm_action_combo or not self.dmm_params_stack: return
            action_text = self.dmm_action_combo.currentText()
            if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.MEASURE)
            elif action_text == constants.ACTION_MM_SET_TERMINAL: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.SET_TERMINAL)
            else: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.PLACEHOLDER)
        elif current_tab_index == 2:
            if not self.smu_action_combo or not self.smu_params_stack or not self.smu_set_value_label: return
            action_text = self.smu_action_combo.currentText()
            if action_text in [constants.ACTION_SM_SET_V, constants.ACTION_SM_SET_I]:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_VALUE)
                self.smu_set_value_label.setText(f"{'Voltage' if action_text == constants.ACTION_SM_SET_V else 'Current'} (Numeric):")
            elif action_text in [constants.ACTION_SM_MEAS_V, constants.ACTION_SM_MEAS_I]: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.MEASURE)
            elif action_text == constants.ACTION_SM_ENABLE_OUTPUT: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.ENABLE_OUTPUT)
            elif action_text == constants.ACTION_SM_SET_TERMINAL: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_TERMINAL)
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_PROTECTION_I)
            else: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.PLACEHOLDER)
        elif current_tab_index == 3:
            if not self.temp_action_combo or not self.temp_params_stack: return
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP: self.temp_params_stack.setCurrentIndex(self.TempParamPages.SET_TEMP)
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP: self.temp_params_stack.setCurrentIndex(self.TempParamPages.CHECK_TEMP)
            else: self.temp_params_stack.setCurrentIndex(self.TempParamPages.PLACEHOLDER)

    def _is_i2c_ready(self) -> bool:
        """I2C 사용을 위한 준비(Chip ID 설정)가 되었는지 확인하고, 아니면 경고 메시지를 표시합니다."""
        chip_id_value = self.current_settings.get("chip_id","")
        if not chip_id_value or not chip_id_value.strip():
            print("DEBUG_AIP: _is_i2c_ready - Chip ID is not set or empty.")
            QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                "Chip ID가 설정되지 않았습니다. Settings 탭에서 Chip ID를 설정해주세요.")
            return False
        print(f"DEBUG_AIP: _is_i2c_ready - Chip ID is '{chip_id_value}'. Returning True.")
        return True

    def _is_device_enabled(self, device_setting_key: str, device_name_for_msg: str) -> bool:
        """설정에서 해당 장비가 활성화되었는지 확인하고, 아니면 경고 메시지를 표시합니다."""
        if not self.current_settings.get(device_setting_key, False):
            print(f"DEBUG_AIP: _is_device_enabled - Device '{device_name_for_msg}' (key: {device_setting_key}) is not enabled in settings.")
            QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                constants.MSG_DEVICE_NOT_ENABLED.format(device_name=device_name_for_msg))
            return False
        if device_setting_key in ["multimeter_use", "sourcemeter_use"]:
            serial_key = device_setting_key.replace("_use", "_serial")
            serial_value = self.current_settings.get(serial_key, "")
            if not serial_value or not serial_value.strip():
                print(f"DEBUG_AIP: _is_device_enabled - Serial number for '{device_name_for_msg}' (key: {serial_key}) is not set.")
                QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                    f"{device_name_for_msg}의 시리얼 번호가 설정되지 않았습니다.")
                return False
        print(f"DEBUG_AIP: _is_device_enabled - Device '{device_name_for_msg}' is enabled.")
        return True


    def get_current_action_string_and_prefix(self) -> Optional[Tuple[str, str, Dict[str,str]]]:
        print("DEBUG_AIP: get_current_action_string_and_prefix called")
        if not self.action_group_tabs:
            print("DEBUG_AIP: self.action_group_tabs is None, returning None")
            return None
        current_tab_index = self.action_group_tabs.currentIndex()
        print(f"DEBUG_AIP: current_tab_index = {current_tab_index}")

        item_str_prefix = ""
        params_list_for_str = []
        params_dict_for_data = {}

        if current_tab_index == 0: # I2C/Delay Tab
            print("DEBUG_AIP: I2C/Delay Tab selected")
            # 필수 UI 요소들이 모두 초기화되었는지 먼저 확인
            # 각 QLineEdit, QComboBox 등이 None이 아닌지 확인
            if not all([
                self.i2c_action_combo, self.i2c_params_stack,
                self.i2c_write_name_target_input, self.i2c_write_name_value_input,
                self.i2c_write_addr_target_input, self.i2c_write_addr_value_input,
                self.i2c_read_name_target_input, self.i2c_read_name_var_name_input,
                self.i2c_read_addr_target_input, self.i2c_read_addr_var_name_input,
                self.delay_seconds_input
            ]):
                print("DEBUG_AIP: CRITICAL - One or more I2C tab UI elements are None.")
                QMessageBox.critical(self, "내부 UI 오류", "I2C 액션 처리에 필요한 UI 요소가 준비되지 않았습니다. 프로그램을 재시작하거나 개발자에게 문의하세요.")
                return None
            
            action_text = self.i2c_action_combo.currentText()
            print(f"DEBUG_AIP: I2C action_text = '{action_text}'")

            if action_text != constants.ACTION_DELAY: # Delay 액션은 Chip ID 불필요
                if not self._is_i2c_ready():
                    print("DEBUG_AIP: _is_i2c_ready() returned False, returning None from get_current_action")
                    return None
                print("DEBUG_AIP: _is_i2c_ready() returned True")

            if action_text == constants.ACTION_I2C_WRITE_NAME:
                print("DEBUG_AIP: Processing ACTION_I2C_WRITE_NAME")
                if not self.register_map or not self.register_map.logical_fields_map:
                    print("DEBUG_AIP: Register map not loaded or empty for I2C_WRITE_NAME, returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_NO_REGMAP_LOADED); return None
                
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_NAME
                name = self.i2c_write_name_target_input.text().strip()
                value_hex_raw = self.i2c_write_name_value_input.text().strip()
                print(f"DEBUG_AIP: Raw Name='{name}', Raw Value='{value_hex_raw}'")
                
                value_hex_normalized = normalize_hex_input(value_hex_raw, add_prefix=True)
                print(f"DEBUG_AIP: Normalized Value='{value_hex_normalized}' for I2C_WRITE_NAME")

                if not value_hex_normalized and value_hex_raw: 
                    print("DEBUG_AIP: Value hex normalization failed (I2C_WRITE_NAME), returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                
                if not name: # 값은 비어있을 수 없음 (normalize_hex_input이 "0x0" 등을 반환하므로)
                    print(f"DEBUG_AIP: Name is empty for I2C_WRITE_NAME. Name='{name}', returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                
                if name not in self.register_map.logical_fields_map:
                    print(f"DEBUG_AIP: Register name '{name}' not in logical_fields_map for I2C_WRITE_NAME, returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)); return None
                
                print("DEBUG_AIP: All checks passed for I2C_WRITE_NAME")
                value_hex = value_hex_normalized if value_hex_normalized is not None else "0x0" # 정규화 실패 시 기본값 (실제로는 위에서 걸러짐)
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_TARGET_NAME}={name}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_hex}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_TARGET_NAME] = name
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_hex

            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                print("DEBUG_AIP: Processing ACTION_I2C_WRITE_ADDR")
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_ADDR
                addr_hex_raw = self.i2c_write_addr_target_input.text().strip()
                value_hex_raw = self.i2c_write_addr_value_input.text().strip()
                print(f"DEBUG_AIP: Raw Addr='{addr_hex_raw}', Raw Value='{value_hex_raw}'")

                addr_hex_normalized = normalize_hex_input(addr_hex_raw, 4, add_prefix=True)
                value_hex_normalized = normalize_hex_input(value_hex_raw, 2, add_prefix=True)
                print(f"DEBUG_AIP: Normalized Addr='{addr_hex_normalized}', Normalized Value='{value_hex_normalized}'")

                if not addr_hex_normalized and addr_hex_raw:
                    print("DEBUG_AIP: Addr hex normalization failed (I2C_WRITE_ADDR), returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"잘못된 주소 형식: {addr_hex_raw}"); return None
                if not value_hex_normalized and value_hex_raw:
                    print("DEBUG_AIP: Value hex normalization failed (I2C_WRITE_ADDR), returning None")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                if not addr_hex_normalized or not value_hex_normalized : # 둘 중 하나라도 정규화 후 비었으면 (또는 원래 비었으면)
                     print(f"DEBUG_AIP: Normalized Addr or Value is empty. Addr='{addr_hex_normalized}', Value='{value_hex_normalized}', returning None")
                     QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                
                print("DEBUG_AIP: All checks passed for I2C_WRITE_ADDR")
                addr_hex = addr_hex_normalized
                value_hex = value_hex_normalized
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_ADDRESS}={addr_hex}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_hex}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_ADDRESS] = addr_hex; params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_hex
            
            elif action_text == constants.ACTION_I2C_READ_NAME:
                print("DEBUG_AIP: Processing ACTION_I2C_READ_NAME")
                if not self.register_map or not self.register_map.logical_fields_map: QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_NO_REGMAP_LOADED); print("DEBUG_AIP: Register map not loaded for I2C_READ_NAME, returning None"); return None
                item_str_prefix = constants.SEQ_PREFIX_I2C_READ_NAME; name = self.i2c_read_name_target_input.text().strip(); var_name = self.i2c_read_name_var_name_input.text().strip()
                if not name or not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "레지스터명과 저장 변수명 모두 입력 필요"); print("DEBUG_AIP: Name or var_name empty for I2C_READ_NAME, returning None"); return None
                if name not in self.register_map.logical_fields_map: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)); print(f"DEBUG_AIP: Name '{name}' not in map for I2C_READ_NAME, returning None"); return None
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_TARGET_NAME}={name}", f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_TARGET_NAME] = name; params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name
                print("DEBUG_AIP: All checks passed for I2C_READ_NAME")

            elif action_text == constants.ACTION_I2C_READ_ADDR:
                print("DEBUG_AIP: Processing ACTION_I2C_READ_ADDR")
                item_str_prefix = constants.SEQ_PREFIX_I2C_READ_ADDR; addr_hex_raw = self.i2c_read_addr_target_input.text().strip(); var_name = self.i2c_read_addr_var_name_input.text().strip()
                addr_hex_normalized = normalize_hex_input(addr_hex_raw, 4, add_prefix=True)
                if not addr_hex_normalized and addr_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"잘못된 주소 형식: {addr_hex_raw}"); print("DEBUG_AIP: Invalid addr format for I2C_READ_ADDR, returning None"); return None
                if not addr_hex_normalized or not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "주소와 저장 변수명 모두 입력 필요"); print("DEBUG_AIP: Addr or var_name empty for I2C_READ_ADDR, returning None"); return None
                addr_hex = addr_hex_normalized
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_ADDRESS}={addr_hex}", f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_ADDRESS] = addr_hex; params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name
                print("DEBUG_AIP: All checks passed for I2C_READ_ADDR")

            elif action_text == constants.ACTION_DELAY:
                print("DEBUG_AIP: Processing ACTION_DELAY")
                item_str_prefix = constants.SEQ_PREFIX_DELAY
                delay_val = self.delay_seconds_input.value()
                if delay_val <= 0: # 지연 시간 유효성 검사
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "지연 시간은 0보다 커야 합니다."); print("DEBUG_AIP: Invalid delay value, returning None"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_SECONDS}={delay_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_SECONDS] = str(delay_val)
                print("DEBUG_AIP: All checks passed for DELAY")
            else:
                print(f"DEBUG_AIP: Unsupported I2C action: {action_text}, returning None")
                QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); return None
        
        # ... (DMM, SMU, Temp 탭 로직에 유사한 디버그 로그 추가) ...
        elif current_tab_index == 1: # DMM Tab
            print("DEBUG_AIP: DMM Tab selected")
            if not (self.dmm_action_combo and self.dmm_measure_var_name_input and self.dmm_terminal_combo):
                print("DEBUG_AIP: CRITICAL - DMM tab UI element is None.")
                QMessageBox.critical(self, "내부 UI 오류", "DMM 액션 처리에 필요한 UI 요소가 준비되지 않았습니다.")
                return None
            if not self._is_device_enabled("multimeter_use", "Multimeter"): print("DEBUG_AIP: DMM not enabled, returning None"); return None
            action_text = self.dmm_action_combo.currentText()
            print(f"DEBUG_AIP: DMM action_text = '{action_text}'")
            if action_text == constants.ACTION_MM_MEAS_V: item_str_prefix = constants.SEQ_PREFIX_MM_MEAS_V
            elif action_text == constants.ACTION_MM_MEAS_I: item_str_prefix = constants.SEQ_PREFIX_MM_MEAS_I
            elif action_text == constants.ACTION_MM_SET_TERMINAL: item_str_prefix = constants.SEQ_PREFIX_MM_SET_TERMINAL
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); print(f"DEBUG_AIP: Unsupported DMM action: {action_text}, returning None"); return None

            if item_str_prefix in [constants.SEQ_PREFIX_MM_MEAS_V, constants.SEQ_PREFIX_MM_MEAS_I]:
                var_name = self.dmm_measure_var_name_input.text().strip()
                if not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "결과 변수명 입력 필요"); print("DEBUG_AIP: DMM var_name empty, returning None"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name
            elif item_str_prefix == constants.SEQ_PREFIX_MM_SET_TERMINAL:
                term_val = self.dmm_terminal_combo.currentText()
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            print(f"DEBUG_AIP: All checks passed for DMM action: {action_text}")


        elif current_tab_index == 2: # SMU Tab
            print("DEBUG_AIP: SMU Tab selected")
            if not (self.smu_action_combo and self.smu_set_value_input and
                    self.smu_set_terminal_combo and self.smu_measure_var_name_input and
                    self.smu_measure_terminal_combo and self.smu_output_state_combo and
                    self.smu_terminal_combo and self.smu_protection_current_input):
                print("DEBUG_AIP: CRITICAL - SMU tab UI element is None.")
                QMessageBox.critical(self, "내부 UI 오류", "SMU 액션 처리에 필요한 UI 요소가 준비되지 않았습니다.")
                return None
            if not self._is_device_enabled("sourcemeter_use", "Sourcemeter"): print("DEBUG_AIP: SMU not enabled, returning None"); return None
            action_text = self.smu_action_combo.currentText()
            print(f"DEBUG_AIP: SMU action_text = '{action_text}'")
            if action_text == constants.ACTION_SM_SET_V: item_str_prefix = constants.SEQ_PREFIX_SM_SET_V
            elif action_text == constants.ACTION_SM_SET_I: item_str_prefix = constants.SEQ_PREFIX_SM_SET_I
            elif action_text == constants.ACTION_SM_MEAS_V: item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_V
            elif action_text == constants.ACTION_SM_MEAS_I: item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_I
            elif action_text == constants.ACTION_SM_ENABLE_OUTPUT: item_str_prefix = constants.SEQ_PREFIX_SM_ENABLE_OUTPUT
            elif action_text == constants.ACTION_SM_SET_TERMINAL: item_str_prefix = constants.SEQ_PREFIX_SM_SET_TERMINAL
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I: item_str_prefix = constants.SEQ_PREFIX_SM_SET_PROTECTION_I
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); print(f"DEBUG_AIP: Unsupported SMU action: {action_text}, returning None"); return None

            if item_str_prefix in [constants.SEQ_PREFIX_SM_SET_V, constants.SEQ_PREFIX_SM_SET_I]:
                val_str = self.smu_set_value_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "값 입력 필요"); print("DEBUG_AIP: SMU value empty, returning None"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); print("DEBUG_AIP: SMU invalid numeric value, returning None"); return None
                term_val = self.smu_set_terminal_combo.currentText()
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_VALUE}={val_str}", f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = val_str; params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix in [constants.SEQ_PREFIX_SM_MEAS_V, constants.SEQ_PREFIX_SM_MEAS_I]:
                var_name = self.smu_measure_var_name_input.text().strip()
                if not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "결과 변수명 입력 필요"); print("DEBUG_AIP: SMU var_name empty, returning None"); return None
                term_val = self.smu_measure_terminal_combo.currentText()
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}", f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name; params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_ENABLE_OUTPUT:
                state_val = 'TRUE' if self.smu_output_state_combo.currentText() == constants.BOOL_TRUE else 'FALSE'
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_STATE}={state_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_STATE] = state_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_SET_TERMINAL:
                term_val = self.smu_terminal_combo.currentText()
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_SET_PROTECTION_I:
                val_str = self.smu_protection_current_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "보호 전류 값 입력 필요"); print("DEBUG_AIP: SMU protection current empty, returning None"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); print("DEBUG_AIP: SMU invalid protection current, returning None"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_CURRENT_LIMIT}={val_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_CURRENT_LIMIT] = val_str
            print(f"DEBUG_AIP: All checks passed for SMU action: {action_text}")

        elif current_tab_index == 3: # Temp Tab
            print("DEBUG_AIP: Temp Tab selected")
            if not (self.temp_action_combo and self.chamber_set_temp_input and
                    self.chamber_check_target_temp_input and self.chamber_check_tolerance_input and
                    self.chamber_check_timeout_input):
                print("DEBUG_AIP: CRITICAL - Temp tab UI element is None.")
                QMessageBox.critical(self, "내부 UI 오류", "Chamber 액션 처리에 필요한 UI 요소가 준비되지 않았습니다.")
                return None
            if not self._is_device_enabled("chamber_use", "Chamber"): print("DEBUG_AIP: Chamber not enabled, returning None"); return None
            action_text = self.temp_action_combo.currentText()
            print(f"DEBUG_AIP: Chamber action_text = '{action_text}'")
            if action_text == constants.ACTION_CHAMBER_SET_TEMP: item_str_prefix = constants.SEQ_PREFIX_CHAMBER_SET_TEMP
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP: item_str_prefix = constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); print(f"DEBUG_AIP: Unsupported Chamber action: {action_text}, returning None"); return None

            if item_str_prefix == constants.SEQ_PREFIX_CHAMBER_SET_TEMP:
                val_str = self.chamber_set_temp_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "목표 온도 값 입력 필요"); print("DEBUG_AIP: Chamber set temp value empty, returning None"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); print("DEBUG_AIP: Chamber invalid set temp value, returning None"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VALUE}={val_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = val_str
            elif item_str_prefix == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP:
                target_temp_str = self.chamber_check_target_temp_input.text().strip()
                tolerance_str = self.chamber_check_tolerance_input.text().strip()
                timeout_str = self.chamber_check_timeout_input.text().strip()
                if not target_temp_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "목표 온도 값 입력 필요"); print("DEBUG_AIP: Chamber check target temp empty, returning None"); return None
                try:
                    float(target_temp_str)
                    if tolerance_str: float(tolerance_str)
                    if timeout_str: float(timeout_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "온도/오차/시간 초과 값 형식 오류"); print("DEBUG_AIP: Chamber check temp invalid params, returning None"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VALUE}={target_temp_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = target_temp_str
                if tolerance_str:
                    params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TOLERANCE}={tolerance_str}")
                    params_dict_for_data[constants.SEQ_PARAM_KEY_TOLERANCE] = tolerance_str
                if timeout_str:
                    params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TIMEOUT}={timeout_str}")
                    params_dict_for_data[constants.SEQ_PARAM_KEY_TIMEOUT] = timeout_str
            print(f"DEBUG_AIP: All checks passed for Chamber action: {action_text}")
        else:
            print(f"DEBUG_AIP: Unknown tab index: {current_tab_index}, returning None")
            return None

        if item_str_prefix:
            full_action_string = f"{item_str_prefix}: {'; '.join(params_list_for_str)}"
            print(f"DEBUG_AIP: Successfully generated action string: {full_action_string}")
            return item_str_prefix, full_action_string, params_dict_for_data
        
        print("DEBUG_AIP: item_str_prefix is empty, returning None at the end of method")
        return None

    def clear_input_fields(self):
        """현재 활성화된 탭의 액션 입력 필드를 초기화합니다."""
        if not self.action_group_tabs: return
        current_tab_index = self.action_group_tabs.currentIndex()

        if current_tab_index == 0 and self.i2c_action_combo:
            action_text = self.i2c_action_combo.currentText()
            if action_text == constants.ACTION_I2C_WRITE_NAME:
                if self.i2c_write_name_target_input: self.i2c_write_name_target_input.clear()
                if self.i2c_write_name_value_input: self.i2c_write_name_value_input.clear(); self.i2c_write_name_value_input.setStyleSheet(""); self.i2c_write_name_value_input.setToolTip("")
            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                if self.i2c_write_addr_target_input: self.i2c_write_addr_target_input.clear(); self.i2c_write_addr_target_input.setStyleSheet(""); self.i2c_write_addr_target_input.setToolTip("")
                if self.i2c_write_addr_value_input: self.i2c_write_addr_value_input.clear(); self.i2c_write_addr_value_input.setStyleSheet(""); self.i2c_write_addr_value_input.setToolTip("")
            elif action_text == constants.ACTION_I2C_READ_NAME:
                if self.i2c_read_name_target_input: self.i2c_read_name_target_input.clear()
                if self.i2c_read_name_var_name_input: self.i2c_read_name_var_name_input.clear()
            elif action_text == constants.ACTION_I2C_READ_ADDR:
                if self.i2c_read_addr_target_input: self.i2c_read_addr_target_input.clear(); self.i2c_read_addr_target_input.setStyleSheet(""); self.i2c_read_addr_target_input.setToolTip("")
                if self.i2c_read_addr_var_name_input: self.i2c_read_addr_var_name_input.clear()
            elif action_text == constants.ACTION_DELAY:
                if self.delay_seconds_input: self.delay_seconds_input.setValue(0.01)
        elif current_tab_index == 1 and self.dmm_action_combo:
            action_text = self.dmm_action_combo.currentText()
            if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]:
                if self.dmm_measure_var_name_input: self.dmm_measure_var_name_input.clear()
        elif current_tab_index == 2 and self.smu_action_combo:
            action_text = self.smu_action_combo.currentText()
            if action_text in [constants.ACTION_SM_SET_V, constants.ACTION_SM_SET_I]:
                if self.smu_set_value_input: self.smu_set_value_input.clear()
            elif action_text in [constants.ACTION_SM_MEAS_V, constants.ACTION_SM_MEAS_I]:
                if self.smu_measure_var_name_input: self.smu_measure_var_name_input.clear()
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I:
                if self.smu_protection_current_input: self.smu_protection_current_input.clear()
        elif current_tab_index == 3 and self.temp_action_combo:
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP:
                if self.chamber_set_temp_input: self.chamber_set_temp_input.clear()
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP:
                if self.chamber_check_target_temp_input: self.chamber_check_target_temp_input.clear()
                if self.chamber_check_tolerance_input: self.chamber_check_tolerance_input.clear()
                if self.chamber_check_timeout_input: self.chamber_check_timeout_input.clear()

    def update_completer_model(self, new_model: Optional[QStringListModel]):
        self.completer_model = new_model
        if self.completer_model is not None:
            if self.i2c_write_name_target_input:
                if not self.i2c_write_name_target_input.completer():
                    completer_write_name = QCompleter(self.completer_model, self)
                    completer_write_name.setCaseSensitivity(Qt.CaseInsensitive)
                    completer_write_name.setFilterMode(Qt.MatchContains)
                    self.i2c_write_name_target_input.setCompleter(completer_write_name)
                else:
                    self.i2c_write_name_target_input.completer().setModel(self.completer_model)
            if self.i2c_read_name_target_input:
                if not self.i2c_read_name_target_input.completer():
                    completer_read_name = QCompleter(self.completer_model, self)
                    completer_read_name.setCaseSensitivity(Qt.CaseInsensitive)
                    completer_read_name.setFilterMode(Qt.MatchContains)
                    self.i2c_read_name_target_input.setCompleter(completer_read_name)
                else:
                    self.i2c_read_name_target_input.completer().setModel(self.completer_model)
        else:
            if self.i2c_write_name_target_input: self.i2c_write_name_target_input.setCompleter(None)
            if self.i2c_read_name_target_input: self.i2c_read_name_target_input.setCompleter(None)

    def update_settings(self, new_settings: Dict[str, Any]):
        self.current_settings = new_settings if new_settings is not None else {}
        dmm_enabled = self.current_settings.get('multimeter_use', False)
        if self.action_group_tabs and self.dmm_tab_widget is not None:
            dmm_tab_idx = self.action_group_tabs.indexOf(self.dmm_tab_widget)
            if dmm_tab_idx != -1:
                self.action_group_tabs.setTabEnabled(dmm_tab_idx, dmm_enabled)
                if not dmm_enabled and self.action_group_tabs.widget(dmm_tab_idx) == self.action_group_tabs.currentWidget():
                    self.action_group_tabs.setCurrentIndex(0)

        smu_enabled = self.current_settings.get('sourcemeter_use', False)
        if self.action_group_tabs and self.smu_tab_widget is not None:
            smu_tab_idx = self.action_group_tabs.indexOf(self.smu_tab_widget)
            if smu_tab_idx != -1:
                self.action_group_tabs.setTabEnabled(smu_tab_idx, smu_enabled)
                if not smu_enabled and self.action_group_tabs.widget(smu_tab_idx) == self.action_group_tabs.currentWidget():
                    self.action_group_tabs.setCurrentIndex(0)

        chamber_enabled = self.current_settings.get('chamber_use', False)
        if self.action_group_tabs and self.temp_tab_widget is not None:
            temp_tab_idx = self.action_group_tabs.indexOf(self.temp_tab_widget)
            if temp_tab_idx != -1:
                self.action_group_tabs.setTabEnabled(temp_tab_idx, chamber_enabled)
                if not chamber_enabled and self.action_group_tabs.widget(temp_tab_idx) == self.action_group_tabs.currentWidget():
                    self.action_group_tabs.setCurrentIndex(0)
        self._update_active_sub_tab_fields()

    def update_register_map(self, new_register_map: Optional[RegisterMap]):
        self.register_map = new_register_map
        print("ActionInputPanel: RegisterMap updated.")