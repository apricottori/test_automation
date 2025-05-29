# core/excel_exporter.py
import pandas as pd
from typing import List, Dict, Any, Optional, Union, Callable

from core.data_models import ExcelSheetConfig
from core import constants # For EXCEL_COL_SAMPLE_NO

class ExcelExporter:
    """고급 Excel 내보내기 기능을 제공하는 클래스"""
    
    def __init__(self, results_df: pd.DataFrame):
        self.results_df = results_df.copy()
        
    def export_to_excel(self, file_path: str, sheet_configs: List[ExcelSheetConfig]) -> bool:
        if self.results_df.empty:
            print("Error (ExcelExporter): No data to export.")
            return False
            
        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for config_idx, config in enumerate(sheet_configs):
                    sheet_name_to_use = config.get('sheet_name', f"Sheet_{config_idx + 1}")
                    if not config.get('dynamic_naming') and not sheet_name_to_use.strip():
                        sheet_name_to_use = f"Sheet_{config_idx + 1}"
                    
                    print(f"INFO_ExcelExporter: Processing sheet: '{sheet_name_to_use}' with config: {config}")

                    df_current_sheet = self.results_df.copy()

                    # Apply legacy filters first if they exist in the config
                    df_current_sheet = self._apply_global_filters(df_current_sheet, config)
                    df_current_sheet = self._apply_value_filters(df_current_sheet, config) # Old value_filters

                    # Filter by selected Test Items (Variable Name)
                    selected_test_items = config.get('include_columns', []) # Default to empty list
                    if selected_test_items and 'Variable Name' in df_current_sheet.columns:
                        df_current_sheet = df_current_sheet[df_current_sheet['Variable Name'].isin(selected_test_items)]
                    elif selected_test_items: # Test items selected but 'Variable Name' col missing
                        print(f"Warning (ExcelExporter): 'Variable Name' column not found for sheet '{sheet_name_to_use}'. Cannot filter by selected Test Items.")
                        df_current_sheet = pd.DataFrame() # Make it empty to skip writing this sheet or write empty

                    if df_current_sheet.empty:
                        print(f"Info (ExcelExporter): Sheet '{sheet_name_to_use}' is empty after pre-filtering. Skipping or writing empty sheet.")
                        # Optionally write an empty sheet explicitly if desired, otherwise it might be skipped by _write_single_sheet
                        # pd.DataFrame().to_excel(writer, sheet_name=sheet_name_to_use, index=False)
                        # continue 

                    if config.get('dynamic_naming', False) and config.get('dynamic_name_field'):
                        self._process_dynamic_sheets(writer, df_current_sheet, config, sheet_name_to_use, config_idx)
                    else:
                        self._write_single_sheet(writer, df_current_sheet, config, sheet_name_to_use)
            return True
        except Exception as e:
            print(f"Error (ExcelExporter): Excel export failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _write_single_sheet(self, writer: pd.ExcelWriter, df_input: pd.DataFrame, config: ExcelSheetConfig, sheet_name: str):
        if df_input.empty and not config.get('dynamic_naming'): # Don't prepare if already empty, unless dynamic processing made it so
            print(f"Info (ExcelExporter): Data for sheet '{sheet_name}' is empty before final layout. Sheet might be skipped.")
            # To write an empty sheet: pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            return

        final_df_for_sheet = self._prepare_sheet_data(df_input, config)
        
        if not final_df_for_sheet.empty:
            try:
                write_index = bool(final_df_for_sheet.index.name or final_df_for_sheet.index.nlevels > 1)
                final_df_for_sheet.to_excel(writer, sheet_name=sheet_name, index=write_index)
                print(f"INFO_ExcelExporter: Successfully wrote data to sheet: '{sheet_name}'. Shape: {final_df_for_sheet.shape}")
            except Exception as e_write:
                print(f"Error (ExcelExporter): Writing sheet '{sheet_name}': {e_write}")
        else:
            print(f"Warning (ExcelExporter): Final data for sheet '{sheet_name}' is empty after layout processing. Sheet not written.")

    def _prepare_sheet_data(self, df_input: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        output_df = df_input.copy()
        if output_df.empty: return pd.DataFrame()

        index_field_list = config.get('index_fields', [])
        column_field_list = config.get('column_fields', [])
        row_field = index_field_list[0] if index_field_list and index_field_list[0] else None
        col_field = column_field_list[0] if column_field_list and column_field_list[0] else None

        sheet_display_name = config.get('sheet_name', 'Untitled') # For logging
        print(f"DEBUG_ExcelExporter_PrepareSheet: Sheet: '{sheet_display_name}', Config - Row: '{row_field}', Col: '{col_field}'. Input df shape: {output_df.shape}, Columns: {output_df.columns.tolist()}") 

        # 필터링: 특정 테스트 항목만 포함
        selected_test_items = config.get('include_columns', [])
        if selected_test_items and 'Variable Name' in output_df.columns:
            output_df = output_df[output_df['Variable Name'].isin(selected_test_items)]
            if output_df.empty:
                print(f"WARN_ExcelExporter: Sheet '{sheet_display_name}' - No data after filtering for selected test items.")
                return pd.DataFrame()

        if row_field and row_field not in output_df.columns:
            print(f"WARN_ExcelExporter: Row field '{row_field}' not in data for sheet '{sheet_display_name}'. Pivot may fail or be incorrect.")
            row_field = None # Invalidate if not present
        if col_field and col_field not in output_df.columns:
            print(f"WARN_ExcelExporter: Column field '{col_field}' not in data for sheet '{sheet_display_name}'. Pivot may fail or be incorrect.")
            col_field = None # Invalidate if not present

        # Scenario A: Both row_field and col_field are selected.
        if row_field and col_field and 'Value' in output_df.columns:
            try:
                print(f"DEBUG_ExcelExporter: Scenario A - Pivoting index='{row_field}', columns='{col_field}', values='Value'")
                # 피벗 테이블을 생성할 때 Variable Name 필드가 있다면 특정 테스트 항목으로 필터링
                if col_field == 'Variable Name' and selected_test_items:
                    pivot_df = pd.pivot_table(output_df, index=row_field, columns=col_field, values='Value', aggfunc='first')
                    # Variable Name이 컬럼일 때 컬럼 순서를 include_columns 순서와 일치시킴
                    common_cols = [col for col in selected_test_items if col in pivot_df.columns]
                    if common_cols:
                        pivot_df = pivot_df[common_cols]
                else:
                    pivot_df = pd.pivot_table(output_df, index=row_field, columns=col_field, values='Value', aggfunc='first')
                output_df = pivot_df
            except Exception as e:
                print(f"ERROR_ExcelExporter: Pivot A failed for sheet '{sheet_display_name}': {e}")
                output_df = self._format_simple_table(df_input, config) # Fallback to simple
        
        # Scenario B: Only row_field is selected (columns can be any field)
        elif row_field and 'Variable Name' in output_df.columns and 'Value' in output_df.columns:
            try:
                print(f"DEBUG_ExcelExporter: Scenario B - Pivoting index='{row_field}', columns='Variable Name', values='Value'")
                pivot_df = pd.pivot_table(output_df, index=row_field, columns='Variable Name', values='Value', aggfunc='first')
                # Variable Name이 컬럼일 때 컬럼 순서를 include_columns 순서와 일치시킴
                if selected_test_items:
                    common_cols = [col for col in selected_test_items if col in pivot_df.columns]
                    if common_cols:
                        pivot_df = pivot_df[common_cols]
                output_df = pivot_df
            except Exception as e:
                print(f"ERROR_ExcelExporter: Pivot B failed for sheet '{sheet_display_name}': {e}")
                output_df = self._format_simple_table(df_input, config) # Fallback to simple
        
        # Scenario C: Only col_field is selected (rows can be any field)
        elif col_field and 'Variable Name' in output_df.columns and 'Value' in output_df.columns:
            try:
                print(f"DEBUG_ExcelExporter: Scenario C - Pivoting index='Variable Name', columns='{col_field}', values='Value'")
                pivot_df = pd.pivot_table(output_df, index='Variable Name', columns=col_field, values='Value', aggfunc='first')
                # 선택된 테스트 항목만 포함
                if selected_test_items:
                    pivot_df = pivot_df.loc[pivot_df.index.isin(selected_test_items)]
                output_df = pivot_df
            except Exception as e:
                print(f"ERROR_ExcelExporter: Pivot C failed for sheet '{sheet_display_name}': {e}")
                output_df = self._format_simple_table(df_input, config) # Fallback to simple
        
        # Scenario D: Neither row_field nor col_field is selected (Simple Table).
        else:
            print(f"DEBUG_ExcelExporter: Scenario D - Formatting as simple table for sheet '{sheet_display_name}'.")
            output_df = self._format_simple_table(df_input, config)

        if config.get('transpose', False) and not output_df.empty:
            print(f"DEBUG_ExcelExporter: Transposing sheet '{sheet_display_name}'")
            output_df = output_df.transpose()
        
        return output_df

    def _format_simple_table(self, df_input: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        # df_input is already filtered by global, value, and selected Test Items.
        # Columns to display: "Variable Name", "Value", "Sample Number", and any loop variables.
        # "Timestamp" is excluded.
        if df_input.empty: return pd.DataFrame()

        cols_to_keep = []
        if 'Variable Name' in df_input.columns: cols_to_keep.append('Variable Name')
        if 'Value' in df_input.columns: cols_to_keep.append('Value')
        if constants.EXCEL_COL_SAMPLE_NO in df_input.columns: cols_to_keep.append(constants.EXCEL_COL_SAMPLE_NO)
        
        standard_cols_to_exclude_as_loop_vars = {'Timestamp', 'Variable Name', 'Value', constants.EXCEL_COL_SAMPLE_NO}
        for col in df_input.columns:
            if col not in standard_cols_to_exclude_as_loop_vars and col not in cols_to_keep:
                cols_to_keep.append(col)
        
        if not cols_to_keep:
            print(f"WARN_ExcelExporter_SimpleTable: No relevant columns found for simple table for sheet '{config.get('sheet_name', '?')}'.")
            return pd.DataFrame() # Return empty if no relevant columns identified
            
        return df_input[cols_to_keep]

    def _apply_global_filters(self, df: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        filtered_df = df.copy()
        global_filters = config.get('global_filters')
        if not global_filters: return filtered_df
        
        current_df = filtered_df
        for field, condition_val in global_filters.items():
            if field not in current_df.columns:
                print(f"Warning (Global Filter): Field '{field}' not found in DataFrame. Skipping this filter.")
                continue
            if isinstance(condition_val, list):
                try: current_df = current_df[current_df[field].astype(str).isin(map(str, condition_val))]
                except Exception as e: print(f"Warning (Global Filter L): Error for field '{field}': {e}. Skipping.")
            elif isinstance(condition_val, str) and condition_val.startswith(('>', '<', '>=', '<=')):
                try:
                    op_len = 2 if condition_val[1] == '=' else 1
                    op, val_str = condition_val[:op_len], condition_val[op_len:]
                    val_num, col_num = pd.to_numeric(val_str), pd.to_numeric(current_df[field], errors='coerce')
                    if op == '>': current_df = current_df[col_num > val_num]
                    elif op == '<': current_df = current_df[col_num < val_num]
                    elif op == '>=': current_df = current_df[col_num >= val_num]
                    elif op == '<=': current_df = current_df[col_num <= val_num]
                    current_df = current_df.dropna(subset=[field])
                except Exception as e: print(f"Warning (Global Filter N): Error for field '{field}': {e}. Skipping.")
            else:
                try:
                    if isinstance(condition_val, bool): current_df = current_df[current_df[field] == condition_val]
                    elif isinstance(condition_val, (int, float)):
                        current_df = current_df[pd.to_numeric(current_df[field], errors='coerce') == condition_val]
                        current_df = current_df.dropna(subset=[field])
                    else: current_df = current_df[current_df[field].astype(str) == str(condition_val)]
                except Exception as e: print(f"Warning (Global Filter E): Error for field '{field}': {e}. Skipping.")
        return current_df

    def _apply_value_filters(self, df: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        df_filtered = df.copy()
        value_filters = config.get('value_filters') 
        if not value_filters: return df_filtered

        for field, allowed_values_str_list in value_filters.items():
            if field in df_filtered.columns:
                if isinstance(allowed_values_str_list, list) and allowed_values_str_list:
                    try: df_filtered = df_filtered[df_filtered[field].astype(str).isin(allowed_values_str_list)]
                    except Exception as e: print(f"Warning (Value Filter): Error for field '{field}': {e}. Skipping.")
                elif allowed_values_str_list: 
                    print(f"Warning (Value Filter): Invalid format for field '{field}'. Expected list. Got: {allowed_values_str_list}")
            else: print(f"Warning (Value Filter): Field '{field}' not found. Skipping.")
        return df_filtered
    
    def _process_dynamic_sheets(self, writer: pd.ExcelWriter, df_input: pd.DataFrame, config: ExcelSheetConfig, base_sheet_name: str, base_config_idx: int) -> None:
        """Processes data for dynamic sheet naming. Input df_input is already globally/value/test-item filtered."""
        dynamic_field = config.get('dynamic_name_field')
        prefix = config.get('dynamic_name_prefix', '')
        
        if not dynamic_field or dynamic_field not in df_input.columns:
            actual_sheet_name = base_sheet_name if base_sheet_name.strip() else f"Dynamic_Fallback_{base_config_idx + 1}"
            print(f"Warning (ExcelExporter): Dynamic naming field '{dynamic_field}' not found for sheet '{base_sheet_name}'. Exporting as single sheet: '{actual_sheet_name}'.")
            self._write_single_sheet(writer, df_input, config, actual_sheet_name)
            return
            
        unique_values = df_input[dynamic_field].unique()
        processed_sheet_names = set() # Tracks names used within this dynamic config to avoid Excel error

        for value in unique_values:
            df_dynamic_split = df_input[df_input[dynamic_field] == value] if not pd.isna(value) else df_input[df_input[dynamic_field].isna()]
            
            current_dynamic_sheet_name_base = f"{prefix}{str(value)}" if not pd.isna(value) else f"{prefix}NA"
            final_dynamic_sheet_name_raw = pd.io.common.validate_sheet_name(current_dynamic_sheet_name_base)
            final_dynamic_sheet_name = final_dynamic_sheet_name_raw[:31]
            
            counter = 1
            temp_name = final_dynamic_sheet_name
            while temp_name in processed_sheet_names:
                suffix = f"_{counter}"
                # Ensure the base name isn't too long to start with
                base_name_for_suffix = final_dynamic_sheet_name_raw[:31 - len(suffix) -1] # -1 for the underscore
                temp_name = f"{base_name_for_suffix}{suffix}"[:31]
                counter += 1
            final_dynamic_sheet_name = temp_name
            processed_sheet_names.add(final_dynamic_sheet_name)

            self._write_single_sheet(writer, df_dynamic_split, config, final_dynamic_sheet_name)