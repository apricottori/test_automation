# results_manager.py
from typing import List, Dict, Any, Optional, Set
import pandas as pd
from core import constants # For EXCEL_COL_SAMPLE_NO etc.
import os

class ResultsManager:
    """
    측정 결과를 관리하고, 테이블 및 파일 형태로 내보내는 클래스입니다.
    결과는 메모리에 List[Dict] 형태로 저장됩니다.
    """
    def __init__(self):
        self.results_data: List[Dict[str, Any]] = []
        # 기본 컬럼 순서 정의 (Timestamp, Variable Name, Value는 항상 앞쪽에)
        self.base_columns = ["Timestamp", "Variable Name", "Value", constants.EXCEL_COL_SAMPLE_NO]


    def add_measurement(self,
                        variable_name: str,
                        value: Any,
                        sample_number: Optional[str] = None,
                        conditions: Optional[Dict[str, Any]] = None):
        """
        새로운 측정 결과를 추가합니다.

        Args:
            variable_name (str): 측정된 변수의 이름.
            value (Any): 측정된 값.
            sample_number (Optional[str]): 현재 테스트 중인 샘플 번호.
            conditions (Optional[Dict[str, Any]]): 측정 당시의 주요 조건 값들 
                                                  (예: {"SMU Set Voltage": 1.0, "Chamber Set Temp": 25.0}).
        """
        record: Dict[str, Any] = {
            "Timestamp": pd.Timestamp.now(),
            "Variable Name": variable_name,
            "Value": value
        }
        if sample_number is not None:
            record[constants.EXCEL_COL_SAMPLE_NO] = sample_number
        
        if conditions:
            for cond_key, cond_value in conditions.items():
                # 조건 키 앞에 "Condition_" 접두사를 붙여 일반 결과와 구분 (선택 사항)
                # 또는 constants에 정의된 키를 직접 사용
                # 여기서는 전달된 키를 그대로 사용하되, get_available_export_columns에서 처리
                record[cond_key] = cond_value
        
        self.results_data.append(record)
        print(f"ResultsManager: Measurement added - {variable_name}={value}, Sample={sample_number}, Conds={conditions}")

    def clear_results(self):
        """모든 저장된 측정 결과를 초기화합니다."""
        self.results_data = []
        print("ResultsManager: All results cleared.")

    def get_results_dataframe(self) -> pd.DataFrame:
        """
        현재까지 저장된 모든 측정 결과를 Pandas DataFrame으로 변환하여 반환합니다.
        'Conditions' 딕셔너리는 평탄화되어 개별 컬럼으로 확장됩니다.

        Returns:
            pd.DataFrame: 측정 결과 DataFrame. 결과가 없으면 빈 DataFrame 반환.
        """
        if not self.results_data:
            return pd.DataFrame()

        # DataFrame 생성 시, 모든 레코드에 존재할 수 있는 모든 키를 컬럼으로 인식하도록 함
        # pd.json_normalize를 사용하면 중첩된 'Conditions'도 잘 처리할 수 있지만,
        # 여기서는 이미 add_measurement에서 평탄화된 키로 저장한다고 가정하거나,
        # DataFrame 생성 후 수동으로 평탄화할 수 있습니다.
        # 가장 간단한 방법은 모든 레코드를 순회하며 모든 유니크한 키를 모으는 것입니다.
        
        # 모든 가능한 컬럼명을 수집 (순서 유지를 위해 Set 대신 List와 조건부 추가)
        all_keys: List[str] = []
        temp_keys_set: Set[str] = set() # 중복 방지 및 빠른 확인용

        # 기본 컬럼 우선 추가
        for key in self.base_columns:
            if key not in temp_keys_set:
                all_keys.append(key)
                temp_keys_set.add(key)
        
        # 나머지 모든 유니크한 키 추가
        for record in self.results_data:
            for key in record.keys():
                if key not in temp_keys_set:
                    all_keys.append(key)
                    temp_keys_set.add(key)
        
        # DataFrame 생성 시 columns 인자를 명시하여 순서 및 누락된 컬럼 처리
        df = pd.DataFrame(self.results_data, columns=all_keys)
        return df

    def get_available_export_columns(self) -> List[str]:
        """
        현재 저장된 모든 결과 데이터에서 내보내기 가능한 모든 고유 컬럼명 리스트를 반환합니다.
        순서는 기본 컬럼, 샘플 번호, 그 외 조건 컬럼 순으로 정렬될 수 있습니다.

        Returns:
            List[str]: 사용 가능한 컬럼명 리스트.
        """
        if not self.results_data:
            return self.base_columns[:] # 데이터가 없어도 기본 컬럼은 반환

        # get_results_dataframe()과 유사하게 모든 유니크한 키를 수집
        all_keys_ordered: List[str] = []
        seen_keys: Set[str] = set()

        # 1. 기본 컬럼 (Timestamp, Variable Name, Value)
        for key in ["Timestamp", "Variable Name", "Value"]:
            if key not in seen_keys:
                all_keys_ordered.append(key)
                seen_keys.add(key)
        
        # 2. 샘플 번호 컬럼
        if constants.EXCEL_COL_SAMPLE_NO not in seen_keys:
             # 모든 레코드에서 샘플 번호 키가 실제로 있는지 확인 후 추가
            if any(constants.EXCEL_COL_SAMPLE_NO in record for record in self.results_data):
                all_keys_ordered.append(constants.EXCEL_COL_SAMPLE_NO)
                seen_keys.add(constants.EXCEL_COL_SAMPLE_NO)


        # 3. 나머지 모든 유니크한 키 (주로 조건 컬럼들, 알파벳 순 정렬)
        other_keys = []
        for record in self.results_data:
            for key in record.keys():
                if key not in seen_keys:
                    other_keys.append(key)
                    seen_keys.add(key) # 여기서도 seen_keys에 추가해야 중복 추가 방지
        
        all_keys_ordered.extend(sorted(list(set(other_keys)))) # set으로 중복 제거 후 정렬하여 추가

        return all_keys_ordered


    def export_to_excel(self, file_path: str, sheet_definitions: List[Dict[str, Any]]) -> bool:
        """
        현재 결과를 지정된 Excel 파일 경로에, 정의된 시트 구성에 따라 저장합니다.
        하나의 Excel 파일 내에 여러 시트를 생성할 수 있습니다.

        Args:
            file_path (str): 저장할 Excel 파일의 전체 경로.
            sheet_definitions (List[Dict[str, Any]]): 
                각 시트의 정의를 담은 딕셔너리의 리스트.
                예: [{'sheet_name': 'Sheet1', 'columns': ['Timestamp', 'Value']}, ...]

        Returns:
            bool: 저장 성공 시 True, 실패 시 False.
        """
        if not self.results_data:
            print("Warning: 내보낼 결과 데이터가 없습니다.")
            return False
        if not sheet_definitions:
            print("Warning: Excel 시트 정의가 제공되지 않았습니다. 내보내기를 수행할 수 없습니다.")
            return False

        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 전체 데이터를 한 번만 DataFrame으로 변환 (효율성)
                # get_results_dataframe()은 이미 모든 가능한 컬럼을 포함한 DataFrame을 반환
                full_df = self.get_results_dataframe()

                if full_df.empty: # 변환 후에도 비어있다면 (거의 발생 안 함)
                    print("Warning: DataFrame으로 변환 후 데이터가 비어있습니다.")
                    # 빈 파일이라도 생성할지, 아니면 False 반환할지 결정. 여기서는 빈 파일 생성.
                    # 빈 DataFrame이라도 쓰면 빈 시트가 생성됨.
                    # 또는 return False로 처리 가능.

                for sheet_def in sheet_definitions:
                    sheet_name = sheet_def.get('sheet_name', 'Sheet')
                    columns_to_export = sheet_def.get('columns', [])

                    if not columns_to_export:
                        print(f"Warning: 시트 '{sheet_name}'에 대해 선택된 컬럼이 없습니다. 이 시트는 건너<0xEB><0>니다.")
                        continue
                    
                    # full_df에서 필요한 컬럼만 선택. 존재하지 않는 컬럼은 무시.
                    # (get_available_export_columns와 UI에서 이미 필터링되었을 것이므로, 대부분 존재해야 함)
                    valid_columns_for_sheet = [col for col in columns_to_export if col in full_df.columns]
                    
                    if not valid_columns_for_sheet:
                        print(f"Warning: 시트 '{sheet_name}'에 대해 유효한 컬럼이 없습니다. 이 시트는 건너<0xEB><0>니다.")
                        continue

                    df_sheet = full_df[valid_columns_for_sheet]
                    
                    # Timestamp 컬럼 포맷팅 (문자열로 변환하여 Excel에 원하는 형식으로 표시)
                    if 'Timestamp' in df_sheet.columns:
                        try:
                            # 이미 pd.Timestamp 객체이므로 strftime 사용 가능
                            df_sheet['Timestamp'] = df_sheet['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
                        except AttributeError: # 만약 Timestamp가 문자열로 이미 저장되어 있다면 무시
                            pass


                    df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"Info: 데이터가 Excel 시트 '{sheet_name}'에 저장되었습니다.")
            
            print(f"Info: 모든 결과가 '{file_path}'에 성공적으로 저장되었습니다.")
            return True
        except Exception as e:
            print(f"Error: 결과를 Excel 파일로 내보내는 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    # --- 테스트 코드 ---
    if not hasattr(constants, 'EXCEL_COL_SAMPLE_NO'): constants.EXCEL_COL_SAMPLE_NO = "Sample Number"
    if not hasattr(constants, 'EXCEL_COL_COND_SMU_V'): constants.EXCEL_COL_COND_SMU_V = "SMU Set Voltage"
    if not hasattr(constants, 'EXCEL_COL_COND_CHAMBER_T'): constants.EXCEL_COL_COND_CHAMBER_T = "Chamber Set Temp"


    manager = ResultsManager()

    # 1. 데이터 추가 테스트
    print("\n--- 데이터 추가 테스트 ---")
    manager.add_measurement("Voltage_A", 1.23, sample_number="S001", conditions={constants.EXCEL_COL_COND_SMU_V: 1.2, constants.EXCEL_COL_COND_CHAMBER_T: 25.0})
    manager.add_measurement("Current_B", 0.005, sample_number="S001", conditions={constants.EXCEL_COL_COND_SMU_V: 1.2, "Custom_Cond": "ModeX"})
    manager.add_measurement("Voltage_A", 1.25, sample_number="S002", conditions={constants.EXCEL_COL_COND_SMU_V: 1.5, constants.EXCEL_COL_COND_CHAMBER_T: 30.0})
    manager.add_measurement("Temp_C", 75.1, conditions={"Other_Info": "Run1"}) # 샘플 번호 없는 경우

    # 2. DataFrame 변환 테스트
    print("\n--- DataFrame 변환 테스트 ---")
    df = manager.get_results_dataframe()
    print(df.to_string())
    expected_cols = ["Timestamp", "Variable Name", "Value", constants.EXCEL_COL_SAMPLE_NO, constants.EXCEL_COL_COND_SMU_V, constants.EXCEL_COL_COND_CHAMBER_T, "Custom_Cond", "Other_Info"]
    for col in expected_cols:
        if col in df.columns: # 조건부로 존재할 수 있는 컬럼들
             print(f"Column '{col}' found in DataFrame.")
    assert constants.EXCEL_COL_SAMPLE_NO in df.columns
    assert constants.EXCEL_COL_COND_SMU_V in df.columns


    # 3. 사용 가능한 컬럼 조회 테스트
    print("\n--- 사용 가능한 컬럼 조회 테스트 ---")
    available_cols = manager.get_available_export_columns()
    print(f"사용 가능한 컬럼: {available_cols}")
    assert constants.EXCEL_COL_SAMPLE_NO in available_cols
    assert constants.EXCEL_COL_COND_SMU_V in available_cols
    assert "Custom_Cond" in available_cols
    assert "Other_Info" in available_cols
    # 순서 확인 (기본 컬럼들이 앞에 오는지)
    assert available_cols.index("Timestamp") < available_cols.index(constants.EXCEL_COL_SAMPLE_NO)


    # 4. Excel 내보내기 테스트
    print("\n--- Excel 내보내기 테스트 ---")
    test_excel_path = "test_results_export.xlsx"
    
    sheet_defs = [
        {
            "sheet_name": "Summary",
            "columns": ["Timestamp", "Variable Name", "Value", constants.EXCEL_COL_SAMPLE_NO]
        },
        {
            "sheet_name": "WithConditions",
            "columns": ["Timestamp", constants.EXCEL_COL_SAMPLE_NO, "Variable Name", "Value", constants.EXCEL_COL_COND_SMU_V, constants.EXCEL_COL_COND_CHAMBER_T]
        },
        {
            "sheet_name": "CustomAndOther", # 존재하지 않는 컬럼은 무시됨
            "columns": ["Timestamp", constants.EXCEL_COL_SAMPLE_NO, "Custom_Cond", "Other_Info", "NonExistentColumn"]
        },
        { # 컬럼 없는 시트 (건너뛰어야 함)
            "sheet_name": "EmptyCols",
            "columns": []
        }
    ]
    export_success = manager.export_to_excel(test_excel_path, sheet_defs)
    if export_success:
        print(f"테스트 결과가 '{test_excel_path}'에 저장되었습니다. 내용을 확인해주세요.")
        assert os.path.exists(test_excel_path)
        # 실제 파일 내용 검증은 수동으로 또는 추가 라이브러리(예: openpyxl 직접 사용) 필요
        # os.remove(test_excel_path) # 테스트 후 파일 삭제
    else:
        print(f"Excel 내보내기 실패.")

    # 5. 결과 초기화 테스트
    print("\n--- 결과 초기화 테스트 ---")
    manager.clear_results()
    df_after_clear = manager.get_results_dataframe()
    print(f"초기화 후 DataFrame 행 개수: {len(df_after_clear)}")
    assert len(df_after_clear) == 0
    assert not manager.results_data

    # 6. 빈 데이터로 내보내기 시도
    print("\n--- 빈 데이터로 내보내기 시도 ---")
    export_empty_success = manager.export_to_excel("empty_export.xlsx", sheet_defs)
    assert not export_empty_success # 데이터 없으면 False 반환
    if os.path.exists("empty_export.xlsx"): os.remove("empty_export.xlsx")

    # 7. 빈 시트 정의로 내보내기 시도
    print("\n--- 빈 시트 정의로 내보내기 시도 ---")
    manager.add_measurement("Test", 1) # 데이터 하나 추가
    export_no_sheets_success = manager.export_to_excel("no_sheets_export.xlsx", [])
    assert not export_no_sheets_success # 시트 정의 없으면 False 반환
    if os.path.exists("no_sheets_export.xlsx"): os.remove("no_sheets_export.xlsx")


    if os.path.exists(test_excel_path): # 테스트 후 파일 삭제
        os.remove(test_excel_path)
        print(f"테스트 파일 '{test_excel_path}' 삭제 완료.")