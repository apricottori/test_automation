# core/excel_exporter.py
import pandas as pd
from typing import List, Dict, Any, Optional, Union, Callable

from core.data_models import ExcelSheetConfig

class ExcelExporter:
    """고급 Excel 내보내기 기능을 제공하는 클래스"""
    
    def __init__(self, results_df: pd.DataFrame):
        """
        Args:
            results_df: 측정 결과가 담긴 DataFrame
        """
        self.results_df = results_df
        
    def export_to_excel(self, file_path: str, sheet_configs: List[ExcelSheetConfig]) -> bool:
        """
        설정에 따라 결과를 Excel 파일로 내보냄
        
        Args:
            file_path: 저장할 Excel 파일 경로
            sheet_configs: 시트 설정 목록
            
        Returns:
            bool: 내보내기 성공 여부
        """
        if self.results_df.empty:
            print("Error: 내보낼 데이터가 없습니다.")
            return False
            
        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for config in sheet_configs:
                    # 전역 필터 적용
                    filtered_df = self._apply_global_filters(self.results_df, config)
                    
                    if config.get('dynamic_naming', False):
                        # 동적 시트 이름 처리
                        self._process_dynamic_sheets(filtered_df, config, writer)
                    else:
                        # 단일 시트 처리
                        sheet_name = config.get('sheet_name', 'Sheet')
                        pivot_df = self._create_pivot_table(filtered_df, config)
                        pivot_df.to_excel(writer, sheet_name=sheet_name)
                        
            return True
        except Exception as e:
            print(f"Error: Excel 내보내기 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _apply_global_filters(self, df: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        """전역 필터 조건을 적용하여 필터링된 DataFrame 반환"""
        filtered_df = df.copy()
        global_filters = config.get('global_filters', {})
        
        if not global_filters:
            return filtered_df
            
        # 각 필터 조건 적용
        for field, value in global_filters.items():
            if field in filtered_df.columns:
                if isinstance(value, list):
                    filtered_df = filtered_df[filtered_df[field].isin(value)]
                else:
                    filtered_df = filtered_df[filtered_df[field] == value]
                    
        return filtered_df
    
    def _create_pivot_table(self, df: pd.DataFrame, config: ExcelSheetConfig) -> pd.DataFrame:
        """설정에 따라 피벗 테이블 생성"""
        index_fields = config.get('index_fields', [])
        column_fields = config.get('column_fields', [])
        value_field = config.get('value_field')
        aggfunc = config.get('aggfunc', 'mean')
        
        # 인덱스/컬럼 필터 적용
        df_filtered = df.copy()
        index_filters = config.get('index_filters', {})
        column_filters = config.get('column_filters', {})
        
        for field, values in index_filters.items():
            if field in df_filtered.columns and values:
                df_filtered = df_filtered[df_filtered[field].isin(values)]
                
        for field, values in column_filters.items():
            if field in df_filtered.columns and values:
                df_filtered = df_filtered[df_filtered[field].isin(values)]
        
        # 집계 함수 설정
        agg_func_map = {
            'mean': pd.DataFrame.mean,
            'max': pd.DataFrame.max,
            'min': pd.DataFrame.min,
            'sum': pd.DataFrame.sum,
            'count': pd.DataFrame.count,
            'first': lambda x: x.iloc[0] if not x.empty else None, # first/last 수정
            'last': lambda x: x.iloc[-1] if not x.empty else None,
            'median': pd.DataFrame.median,
            'std': pd.DataFrame.std
        }
        
        actual_aggfunc = agg_func_map.get(aggfunc, pd.DataFrame.mean)
        
        # 피벗 테이블 생성
        if not value_field or value_field not in df_filtered.columns: # value_field 존재 여부 확인
            print(f"Warning (ExcelExporter): Value field '{value_field}' not found in filtered data for pivot. Returning empty DataFrame for this sheet part.")
            return pd.DataFrame() # 빈 DataFrame 반환

        if not index_fields and not column_fields: # 인덱스와 컬럼 필드가 모두 없으면 원본 반환 (또는 값 필드만 시리즈로)
            if value_field and value_field in df_filtered.columns:
                 return df_filtered[[value_field]] # 값 필드만 있는 DataFrame 반환
            return df_filtered # 혹은 빈 DataFrame 반환 또는 오류 처리
            
        try:
            pivot_df = pd.pivot_table(
                df_filtered,
                values=value_field,
                index=index_fields if index_fields else None,
                columns=column_fields if column_fields else None,
                aggfunc=actual_aggfunc,
                dropna=False # NaN 값 유지를 위해 dropna=False 추가
            )
        except Exception as e:
            print(f"Error creating pivot table: {e}\nConfig: {config}\nData sample:\n{df_filtered.head()}")
            # 오류 발생 시 빈 DataFrame 또는 특정 오류 DataFrame 반환
            return pd.DataFrame() 
        
        # 행/열 전환 여부
        if config.get('transpose', False):
            pivot_df = pivot_df.transpose()
            
        return pivot_df
    
    def _process_dynamic_sheets(self, df: pd.DataFrame, config: ExcelSheetConfig, writer: pd.ExcelWriter) -> None:
        """동적 시트 이름 처리 - 지정된 필드의 고유값마다 별도 시트 생성"""
        dynamic_field = config.get('dynamic_name_field')
        prefix = config.get('dynamic_name_prefix', '')
        
        if not dynamic_field or dynamic_field not in df.columns:
            # 동적 필드가 없거나 유효하지 않은 경우 기본 시트 하나만 생성
            sheet_name = config.get('sheet_name', 'Sheet_Dynamic_Fallback') # 기본 시트명 변경
            pivot_df = self._create_pivot_table(df, config)
            if not pivot_df.empty: # 피벗 테이블이 비어있지 않을 때만 저장
                pivot_df.to_excel(writer, sheet_name=sheet_name)
            return
            
        # 지정된 필드의 고유값 추출
        unique_values = df[dynamic_field].unique()
        
        processed_sheet_names = set() # 중복 시트 이름 방지

        for value in unique_values:
            temp_sheet_name_base = ""
            if pd.isna(value):  # NaN 값 처리
                temp_sheet_name_base = f"{prefix}NA" if prefix else "NA"
                filtered_df = df[df[dynamic_field].isna()]
            else:
                # Excel 시트 이름 규칙 준수 (31자 제한, 특수문자 제한 등)
                value_str = str(value)
                # 시트 이름에 사용할 수 없는 문자 제거 또는 변경
                # 정규표현식을 사용하여 안전한 문자를 제외한 모든 문자를 '_'로 변경
                safe_value_str = pd.io.common.validate_sheet_name(value_str) # pandas 유틸리티 사용
                
                temp_sheet_name_base = f"{prefix}{safe_value_str}" if prefix else safe_value_str
                
                filtered_df = df[df[dynamic_field] == value]
            
            # 시트 이름 길이 제한 및 중복 처리
            final_sheet_name = temp_sheet_name_base[:31] # 길이 제한
            
            # 중복 시트 이름 처리
            counter = 1
            original_name_for_counter = final_sheet_name
            while final_sheet_name in processed_sheet_names:
                suffix = f"_{counter}"
                # 이름이 너무 길어지면 잘라내기 (접미사 공간 확보)
                if len(original_name_for_counter) + len(suffix) > 31:
                    final_sheet_name = original_name_for_counter[:31 - len(suffix)] + suffix
                else:
                    final_sheet_name = original_name_for_counter + suffix
                counter += 1
            processed_sheet_names.add(final_sheet_name)

            # 필터링된 데이터로 피벗 테이블 생성
            pivot_df = self._create_pivot_table(filtered_df, config)
            if not pivot_df.empty: # 피벗 테이블이 비어있지 않을 때만 저장
                 pivot_df.to_excel(writer, sheet_name=final_sheet_name) 