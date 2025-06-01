# core/hardware_control.py
import time
import re # Add re import
# typing 모듈에서 필요한 요소들을 임포트합니다.
from typing import Optional, Tuple, Any, ForwardRef, TYPE_CHECKING 
from PyQt5.QtCore import pyqtSignal, QObject

# core 패키지 내 모듈 임포트
from core import helpers 
from core import constants 

# --- raonpy 라이브러리 임포트 ---
# TYPE_CHECKING은 정적 타입 검사 시에만 True가 됩니다.
# 이를 통해 런타임 ImportError를 피하면서 타입 힌트를 제공할 수 있습니다.
if TYPE_CHECKING:
    from raonpy.rti.efm8evb import EVB
    from raonpy.device.keithley2401 import KEITHLEY2401
    from raonpy.device.agilent34401a import Agilent34401A
    from raonpy.device import su241 as raon_su241_typing # 타입 힌트용 별칭
    # SequencePlayer도 타입 힌트용으로만 임포트 시도
    from core.sequence_player import SequencePlayer as SequencePlayer_Typing_Hint

# 미리 None으로 초기화
evb_runtime_class = None
keithley2401_runtime_class = None
agilent34401a_runtime_class = None
su241_runtime_module = None 

try:
    from raonpy.rti.efm8evb import EVB as RuntimeEVB # 런타임용
    from raonpy.device.keithley2401 import KEITHLEY2401 as RuntimeKEITHLEY2401
    from raonpy.device.agilent34401a import Agilent34401A as RuntimeAgilent34401A
    import raonpy.device.su241 as actual_su241_module # 모듈을 직접 import
    
    evb_runtime_class = RuntimeEVB
    keithley2401_runtime_class = RuntimeKEITHLEY2401
    agilent34401a_runtime_class = RuntimeAgilent34401A
    su241_runtime_module = actual_su241_module # import된 모듈을 변수에 할당

except ImportError as e:
    print(f"Critical Error: raonpy 라이브러리 또는 일부 모듈을 찾을 수 없습니다. {e}")
    # 변수들은 이미 위에서 None으로 초기화되었으므로, 여기서는 추가 할당 불필요
    if 'EVB' not in globals(): EVB = None # type: ignore
    if 'KEITHLEY2401' not in globals(): KEITHLEY2401 = None # type: ignore
    if 'Agilent34401A' not in globals(): Agilent34401A = None # type: ignore
    if 'raon_su241_typing' not in globals(): raon_su241_typing = None # type: ignore
    if 'SequencePlayer_Typing_Hint' not in globals(): SequencePlayer_Typing_Hint = None # type: ignore


# SequencePlayer 클래스에 대한 Forward Reference 정의
# 순환 참조를 피하기 위해 문자열로 클래스 경로 지정
SequencePlayerType = ForwardRef('core.sequence_player.SequencePlayer')


class I2CDevice:
    """I2C 장치 제어를 위한 클래스입니다."""
    def __init__(self, chip_id_str: str = "0x18"):
        self.chip_id: int = 0 
        # 타입 힌트를 문자열 리터럴 또는 TYPE_CHECKING 블록 내부의 타입으로 변경
        self.evb_instance: Optional["EVB"] = None # 문자열 리터럴 사용
        # 또는 if TYPE_CHECKING: self.evb_instance: Optional[EVB] = None
        self.is_opened: bool = False 

        if evb_runtime_class is None: 
            print(f"Error: EVB 모듈 로드 실패. I2C 장치를 초기화할 수 없습니다.")
            return

        if not chip_id_str:
            print(f"Error: Chip ID가 제공되지 않았습니다. I2C 장치 초기화 실패.")
            return
        try:
            if chip_id_str.lower().startswith("0x"):
                self.chip_id = int(chip_id_str, 16)
            else:
                self.chip_id = int(chip_id_str) 
            
            self.evb_instance = evb_runtime_class() 
            try:
                if self.evb_instance: 
                    self.evb_instance.open()
                    self.is_opened = True
                    print(f"Info: I2C 장치(ID: {chip_id_str} / {self.chip_id:#04X})가 성공적으로 초기화 및 연결되었습니다.")
            except Exception as open_e: 
                self.is_opened = False
                print(f"Error: I2C EVB 연결(open) 중 오류 발생: {open_e}. 다른 프로그램이 장치를 사용 중이거나 권한 문제가 있을 수 있습니다.")
                self.evb_instance = None 
        except ValueError:
            print(f"Error: 잘못된 Chip ID 형식입니다: {chip_id_str}. I2C 장치 초기화 실패.")
            self.evb_instance = None
        except Exception as e: 
            print(f"Error: I2C EVB 초기화 중 예외 발생: {e}")
            self.evb_instance = None

    # ... (I2CDevice의 나머지 메소드들은 이전과 동일하게 유지) ...
    def change_port(self, port_number: int) -> bool:
        if not self.evb_instance or not self.is_opened:
            print("Error: I2C EVB가 초기화되지 않았거나 연결되지 않았습니다 (change_port).")
            return False
        try:
            if hasattr(self.evb_instance, 'i2c0_change_port'):
                self.evb_instance.i2c0_change_port(port_number)
                print(f"Info: I2C 포트가 {port_number}로 변경되었습니다.")
                return True
            else:
                print(f"Error: EVB 인스턴스에 'i2c0_change_port' 메서드가 없습니다.")
                return False
        except Exception as e: 
            print(f"Error: I2C 포트 변경 중 오류 발생 ('{str(e)}'). EVB 연결 상태를 확인하세요.")
            if "is_not_opened" in str(e).lower(): 
                self.is_opened = False
            return False

    def write(self, address_hex_str: str, value_hex_str: str) -> bool:
        if not self.evb_instance or not self.is_opened:
            print("Error: I2C EVB가 초기화되지 않았거나 연결되지 않았습니다 (write).")
            return False
        try:
            norm_addr_str = helpers.normalize_hex_input(address_hex_str, add_prefix=True)
            norm_val_str = helpers.normalize_hex_input(value_hex_str, add_prefix=True)

            if norm_addr_str is None or norm_val_str is None:
                print(f"Error: I2C 쓰기를 위한 주소({address_hex_str}) 또는 값({value_hex_str}) 형식이 잘못되었습니다.")
                return False

            address = int(norm_addr_str, 16)
            value = int(norm_val_str, 16)

            time.sleep(0.005) 
            self.evb_instance.i2c0_reg16_write(self.chip_id, address, value)
            return True
        except ValueError:
            print(f"Error: I2C 쓰기를 위한 주소({address_hex_str}) 또는 값({value_hex_str}) 변환 중 오류 발생.")
            return False
        except Exception as e:
            print(f"Error: I2C 쓰기 중 예외 발생 (Addr: {address_hex_str}, Val: {value_hex_str}): {e}")
            if "is_not_opened" in str(e).lower(): self.is_opened = False
            return False

    def read(self, address_hex_str: str) -> tuple[bool, Optional[int]]: 
        if not self.evb_instance or not self.is_opened:
            print("Error: I2C EVB가 초기화되지 않았거나 연결되지 않았습니다 (read).")
            return False, None
        try:
            norm_addr_str = helpers.normalize_hex_input(address_hex_str, add_prefix=True)
            if norm_addr_str is None:
                print(f"Error: I2C 읽기를 위한 주소({address_hex_str}) 형식이 잘못되었습니다.")
                return False, None

            address = int(norm_addr_str, 16)
            time.sleep(0.005)
            read_value = self.evb_instance.i2c0_reg16_read(self.chip_id, address)
            return True, read_value
        except ValueError:
            print(f"Error: I2C 읽기를 위한 주소({address_hex_str}) 변환 중 오류 발생.")
            return False, None
        except Exception as e:
            print(f"Error: I2C 읽기 중 예외 발생 (Addr: {address_hex_str}): {e}")
            if "is_not_opened" in str(e).lower(): self.is_opened = False
            return False, None

    def close(self):
        if self.evb_instance and self.is_opened:
            try:
                self.evb_instance.close()
                print("Info: I2C 장치 연결이 닫혔습니다.")
            except Exception as e:
                print(f"Error: I2C 장치 연결 해제 중 오류 발생: {e}")
        self.is_opened = False


class GPIBDevice:
    """GPIB 계측기 제어를 위한 기본 클래스입니다."""
    def __init__(self, serial_number_str: str, device_name: str, device_class_ref: Any):
        self.serial_number = serial_number_str 
        self.device_name = device_name
        self.instrument: Optional[Any] = None
        self.is_connected: bool = False

        self._cached_set_voltage: Optional[float] = None
        self._cached_set_current: Optional[float] = None
        self._cached_target_temperature: Optional[float] = None

        actual_device_class = None
        if device_name == "Multimeter (Agilent34401A)":
            actual_device_class = agilent34401a_runtime_class
        elif device_name == "Sourcemeter (Keithley2401)":
            actual_device_class = keithley2401_runtime_class
        elif device_name == "Chamber (SU241)":
            actual_device_class = device_class_ref # Chamber에서 전달된 클래스 참조 사용
            if actual_device_class is None: 
                if su241_runtime_module and hasattr(su241_runtime_module, 'SU241'):
                    actual_device_class = su241_runtime_module.SU241
                else:
                    print(f"Error: SU241 class not found for Chamber via device_class_ref or direct import.")
        else: 
            actual_device_class = device_class_ref

        if actual_device_class is None:
            print(f"Error: {self.device_name}의 device class 로드 실패. 장치를 초기화할 수 없습니다.")
            self.instrument = None 
            return 

        try:
            if device_name in ["Multimeter (Agilent34401A)", "Sourcemeter (Keithley2401)", "Chamber (SU241)"]:
                self.instrument = actual_device_class()
            elif serial_number_str: 
                self.instrument = actual_device_class(serial_number_str)
            else: 
                self.instrument = actual_device_class()
            
            if self.instrument and hasattr(self.instrument, 'set_verbose'):
                 self.instrument.set_verbose(False) 
            print(f"Info: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 인스턴스가 생성되었습니다.")
        except TypeError as te: 
             print(f"Error: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 인스턴스 생성 중 TypeError: {te}. raonpy 라이브러리 API 또는 생성자 호출 방식을 확인하세요.")
             self.instrument = None
        except Exception as e:
            print(f"Error: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 인스턴스 생성 중 오류: {e}")
            self.instrument = None

    def connect(self) -> bool:
        if not self.instrument:
            print(f"Error: {self.device_name} 인스턴스가 없습니다. 연결할 수 없습니다.")
            return False
        if self.is_connected:
            print(f"Info: {self.device_name}이(가) 이미 연결되어 있습니다.")
            return True
        try:
            if self.device_name in ["Multimeter (Agilent34401A)", "Sourcemeter (Keithley2401)"] and self.serial_number:
                self.instrument.open(self.serial_number)
            elif self.device_name == "Chamber (SU241)" and self.serial_number:
                try:
                    self.instrument.open(self.serial_number)
                except Exception as e_open_chamber_with_serial:
                    print(f"Warning: Chamber open with serial '{self.serial_number}' failed ({e_open_chamber_with_serial}). Trying open without serial.")
                    self.instrument.open() 
            else:
                self.instrument.open()

            self.is_connected = True
            print(f"Info: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'})에 성공적으로 연결되었습니다.")
            return True
        except Exception as e:
            print(f"Error: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 연결 중 오류 발생: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.instrument and self.is_connected:
            try:
                self.instrument.close()
                print(f"Info: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 연결이 해제되었습니다.")
            except Exception as e:
                print(f"Error: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 연결 해제 중 오류 발생: {e}")
        self.is_connected = False
        self._cached_set_voltage = None
        self._cached_set_current = None
        self._cached_target_temperature = None

    def gpib_write(self, command_str: str) -> bool:
        if not self.is_connected or not self.instrument:
            print(f"Error: {self.device_name}이(가) 연결되지 않았습니다.")
            return False
        
        writer = None
        if hasattr(self.instrument, 'write'):
            writer = self.instrument.write
        elif hasattr(self.instrument, 'gpib') and hasattr(self.instrument.gpib, 'write'):
            writer = self.instrument.gpib.write
        
        if writer:
            try:
                writer(command_str)
                return True
            except Exception as e:
                print(f"Error: {self.device_name} 쓰기 중 오류 ('{command_str}'): {e}")
                return False
        else:
            print(f"Error: {self.device_name}에 'write' 또는 'gpib.write' 메서드가 없습니다.")
            return False

    def gpib_query(self, command_str: str, delay: Optional[float] = None) -> tuple[bool, Optional[str]]:
        if not self.is_connected or not self.instrument:
            print(f"Error: {self.device_name}이(가) 연결되지 않았습니다. (gpib_query)")
            return False, None

        querier = None
        if hasattr(self.instrument, 'query'):
            querier = self.instrument.query
        elif hasattr(self.instrument, 'gpib') and hasattr(self.instrument.gpib, 'query'): # For raonpy structure
            querier = self.instrument.gpib.query
        
        if not querier:
            print(f"Error: {self.device_name}에 'query' 또는 'gpib.query' 메서드가 없습니다.")
            return False, None

        try:
            if delay: 
                print(f"DEBUG_GPIB_QUERY: Delaying for {delay}s before query.")
                time.sleep(delay)
            
            print(f"DEBUG_GPIB_QUERY: Sending query '{command_str}' to {self.device_name}")
            response = querier(command_str) # This might be where raonpy handles/suppresses timeout
            print(f"DEBUG_GPIB_QUERY: Raw response from querier for '{command_str}': '{response}' (type: {type(response)})")

            if response is None: # Explicitly check for None, which might indicate timeout/error from raonpy
                print(f"Error: {self.device_name} query ('{command_str}') returned None. Assuming read error/timeout.")
                return False, None
            
            response_str = str(response).strip()
            
            # If after stripping, the string is empty OR it's literally "None" (as seen in log)
            if not response_str or response_str.lower() == 'none': 
                print(f"Error: {self.device_name} query ('{command_str}') resulted in empty or 'None' string after strip: '{response_str}'")
                return False, None # Treat as failure

            return True, response_str
        except Exception as e: # Catch any other Python-level exceptions during the query
            print(f"Error: {self.device_name} 쿼리 중 예외 발생 ('{command_str}'): {type(e).__name__} - {e}")
            return False, None

    def reset(self) -> bool:
        return self.gpib_write("*RST")

    def get_cached_set_voltage(self) -> Optional[float]: return self._cached_set_voltage
    def get_cached_set_current(self) -> Optional[float]: return self._cached_set_current
    def get_cached_target_temperature(self) -> Optional[float]: return self._cached_target_temperature


class Multimeter(GPIBDevice):
    def __init__(self, serial_number_str: str):
        # Match the device_name string used in your connect logic
        super().__init__(serial_number_str, "Multimeter (Agilent34401A)", agilent34401a_runtime_class)

    def connect(self) -> bool:
        # Override to always disable beep after connecting
        connected = super().connect()
        if connected:
            # Try to disable beep
            try:
                self.gpib_write("SYST:BEEP:STAT OFF")
                print("INFO: DMM beep disabled (SYST:BEEP:STAT OFF sent)")
            except Exception as e:
                print(f"Warning: Failed to disable DMM beep: {e}")
        return connected

    def measure_voltage(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: 
            print(f"DEBUG_DMM_MV: Not connected or no instrument. Connected: {self.is_connected}, Instrument: {self.instrument}")
            return False, None
        
        raw_value: Any = None
        print(f"DEBUG_DMM_MV: Attempting to measure voltage...")

        try:
            # Attempt 1: Use raonpy's built-in measure_voltage if available
            if hasattr(self.instrument, 'measure_voltage'):
                print(f"DEBUG_DMM_MV: Attempt 1 - Calling self.instrument.measure_voltage() ({type(self.instrument)})")
                time.sleep(0.1) # Short delay before measurement
                raw_value = self.instrument.measure_voltage()
                print(f"DEBUG_DMM_MV: Raw value from instrument.measure_voltage(): '{raw_value}' (type: {type(raw_value)})")

                if raw_value is not None and str(raw_value).strip():
                    value = float(str(raw_value).strip())
                    print(f"DEBUG_DMM_MV: Successfully measured voltage (Attempt 1): {value}")
                    return True, value
                else:
                    print(f"DEBUG_DMM_MV: Attempt 1 (instrument.measure_voltage) returned empty or None. Trying direct GPIB query.")

            # Attempt 2: Direct GPIB query if Attempt 1 failed or self.instrument.measure_voltage doesn't exist
            print(f"DEBUG_DMM_MV: Attempt 2 - Using direct GPIB query :MEASure:VOLTage:DC?")
            success_query, query_response_str = self.gpib_query(":MEASure:VOLTage:DC?")
            print(f"DEBUG_DMM_MV: gpib_query(':MEASure:VOLTage:DC?') result: success={success_query}, response_str='{query_response_str}'")

            if success_query and query_response_str is not None and str(query_response_str).strip():
                raw_value = query_response_str
                value_str_cleaned = str(raw_value).strip()
                # Try to extract a float number, handling potential non-numeric prefixes/suffixes from instrument
                match = re.search(r"([+\-]?\d+\.\d*E?[+\-]?\d*)", value_str_cleaned)
                if match:
                    value = float(match.group(1))
                    print(f"DEBUG_DMM_MV: Successfully measured voltage (Attempt 2 - Direct Query): {value}")
                    return True, value
                else:
                    print(f"Error: DMM voltage measurement - Could not parse float from direct query response: '{value_str_cleaned}'")
                    return False, None
            else:
                print(f"Error: DMM voltage measurement - Direct GPIB query failed or returned empty/None.")
                return False, None

        except ValueError as ve:
            print(f"Error: Multimeter 전압 측정 결과 처리 중 ValueError: {ve} (raw_value: '{raw_value}')")
            return False, None
        except Exception as e:
            print(f"Error: Multimeter 전압 측정 중 예외 발생: {e} (raw_value: '{raw_value}')")
            import traceback
            traceback.print_exc()
            return False, None

    def measure_current(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: return False, None
        raw_value: Any = None
        try:
            time.sleep(0.1) 
            if hasattr(self.instrument, 'measure_current'):
                raw_value = self.instrument.measure_current()
            else:
                success_query, raw_value_str = self.gpib_query(":MEASure:CURRent:DC?")
                if not success_query or raw_value_str is None: return False, None
                raw_value = raw_value_str
            
            value_str = str(raw_value).strip()
            if not value_str:
                print(f"Error: Multimeter 전류 측정 결과가 비어있습니다. (raw_value was '{raw_value}')")
                return False, None
            value = float(value_str)
            return True, value
        except (ValueError, TypeError) as e:
            print(f"Error: Multimeter 전류 측정 결과 처리 중 예외 발생: {e} (raw_value: {raw_value})")
            return False, None
        except Exception as e:
            print(f"Error: Multimeter 전류 측정 중 예외 발생: {e}")
            return False, None

    def set_terminal(self, terminal_type_str: str) -> bool:
        if not self.is_connected or not self.instrument:
            print(f"DEBUG_DMM_ST: Not connected or no instrument for set_terminal.")
            return False
        
        cmd = ""
        # Ensure terminal_type_str is compared against values from constants
        if terminal_type_str.upper() == constants.TERMINAL_FRONT: # Use constants.TERMINAL_FRONT.upper() if constants.TERMINAL_FRONT is 'FRONT'
            cmd = "ROUT:TERM FRONT"
        elif terminal_type_str.upper() == constants.TERMINAL_REAR: # Use constants.TERMINAL_REAR.upper()
            cmd = "ROUT:TERM REAR"
        else:
            print(f"Error: Invalid terminal type '{terminal_type_str}' for DMM.")
            return False

        print(f"DEBUG_DMM_ST: Sending GPIB command: '{cmd}' to DMM")
        if self.gpib_write(cmd):
            # As per your snippet, *WAI is used. It ensures the command completes.
            # However, some drivers might handle this internally or it might interfere.
            # Let's include it as it was in your reference.
            self.gpib_write("*WAI") 
            if terminal_type_str.upper() == constants.TERMINAL_REAR: # Use constants.TERMINAL_REAR.upper()
                 time.sleep(1) # Specific delay for REAR as per your snippet
            print(f"DEBUG_DMM_ST: DMM Terminal set to {terminal_type_str.upper()} successfully.")
            return True
        else:
            print(f"Error: Failed to set DMM terminal to {terminal_type_str.upper()}.")
            return False


class Sourcemeter(GPIBDevice):
    def __init__(self, serial_number_str: str):
        super().__init__(serial_number_str, "Sourcemeter (Keithley2401)", keithley2401_runtime_class)
        self._current_terminal: str = constants.TERMINAL_FRONT # 현재 활성 터미널 저장, 기본값 FRONT
        self._cached_set_voltage = 0.0 # V_SOURCE 기본 전압 0V로 초기화

    def connect(self) -> bool:
        if super().connect():
            return self.reset() and self.gpib_write("*CLS")
        return False

    def set_terminal(self, terminal_type_str: str) -> bool:
        cmd = f":ROUTe:TERMinals {terminal_type_str.upper()}"
        success = self.gpib_write(cmd)
        if success: 
            self._current_terminal = terminal_type_str.upper() # 현재 터미널 업데이트
            time.sleep(1.0) # Changed to 1.0s based on reference
        return success

    def enable_output(self, state: bool) -> bool:
        cmd = f":OUTPut:STATe {'ON' if state else 'OFF'}"
        return self.gpib_write(cmd)

    def set_voltage(self, voltage_float: float) -> bool:
        """오직 전압만 세팅. 터미널/출력 등은 별도 액션에서만."""
        if not self.is_connected: return False
        if not self.gpib_write(":SOURce:FUNCtion VOLTage"): 
            print(f"Error: {self.device_name} 전압 소스 모드 설정 실패 in set_voltage.")
            return False
        if not self.gpib_write(f":SOURce:VOLTage:LEVel {voltage_float:.6f}"):
            print(f"Error: {self.device_name} 전압 레벨 {voltage_float:.6f}V 설정 실패.")
            return False
        self._cached_set_voltage = voltage_float 
        self._cached_set_current = None # 전압 설정 시 전류 캐시는 초기화
        print(f"Info: {self.device_name} 전압 레벨 {voltage_float:.3f}V 로 설정됨 (출력은 아직 비활성 상태일 수 있음).")
        return True

    def configure_vsource_and_enable(self) -> bool:
        """V_SOURCE: 전압 소스 모드, 전류 센싱, 전류 자동 범위, 출력 ON, LOCAL 만 실행. 터미널/전압 세팅 없음."""
        if not self.is_connected: return False
        if not self.gpib_write(":SOURce:FUNCtion VOLTage"): 
            print(f"Error: {self.device_name} 전압 소스 모드 설정 실패.")
            return False
        if not self.gpib_write(":SENSe:FUNCtion 'CURRent:DC'"):
            print(f"Error: {self.device_name} 전류 감지 기능 설정 실패.")
            return False
        if not self.gpib_write(":SENSe:CURRent:DC:RANGe:AUTO ON"):
            print(f"Error: {self.device_name} 전류 감지 자동 범위 설정 실패.")
            return False
        if not self.enable_output(True): 
            print(f"Error: {self.device_name} 출력 활성화 실패.")
            return False
        if not self.gpib_write(":SYSTem:LOCal"): 
            print(f"Warning: {self.device_name} 로컬 모드 전환 실패.")
        print(f"Info: {self.device_name} V_SOURCE 구성 완료 (출력 ON, 전압: {self._cached_set_voltage:.3f}V, 터미널: {self._current_terminal}).")
        return True

    def set_current(self, current_float: float) -> bool: # terminal_type_str 파라미터 제거
        if not self.is_connected: return False
        # 터미널 설정은 여기서 하지 않음.
        if not self.gpib_write(":SOURce:FUNCtion CURRent"): return False
        if not self.gpib_write(f":SOURce:CURRent:LEVel {current_float:.6e}"): return False
        # 전류 소스 설정 시, 전압 감지 및 보호 설정이 필요할 수 있음. 현재는 레벨만 설정.
        # 예: if not self.gpib_write(":SENSe:FUNCtion 'VOLTage:DC'"): return False
        # 예: if not self.gpib_write(":SENSe:VOLTage:DC:RANGe:AUTO ON"): return False
        # 예: if not self.set_protection_voltage(20.0): return False # 보호 전압 설정

        if not self.enable_output(True): return False
        
        self._cached_set_current = current_float 
        self._cached_set_voltage = None 
        print(f"Info: {self.device_name} 전류 레벨 {current_float:.3e}A 로 설정됨 (출력 활성화됨, 터미널: {self._current_terminal}).")
        return True

    def set_protection_current(self, current_limit_amps: float) -> bool:
        if not self.is_connected: return False
        cmd = f":SENSe:CURRent:PROTection {current_limit_amps:.6e}" # Keep full word "PROTection" as it's more standard
        return self.gpib_write(cmd)

    def measure_voltage(self, terminal_type_str: Optional[str] = None) -> tuple[bool, Optional[float]]: # 터미널 선택적
        if not self.is_connected or not self.instrument: return False, None
        
        # 명시적으로 터미널이 주어지면 설정, 아니면 현재 설정된 터미널 사용
        if terminal_type_str and not self.set_terminal(terminal_type_str):
            print(f"Error: Sourcemeter 터미널 설정 실패 ({terminal_type_str}) for measure_voltage")
            return False, None
        
        # 전압 측정을 위해 SENSE 기능 설정 (필요시)
        # if not self.gpib_write(":SENSe:FUNCtion 'VOLTage:DC'"): return False, None
        # if not self.gpib_write(":SENSe:VOLTage:DC:RANGe:AUTO ON"): return False, None

        response_str: Optional[str] = None
        try:
            if hasattr(self.instrument, 'measure_voltage'):
                response_str = self.instrument.measure_voltage() # Use raonpy method
            else:
                print("Error: Sourcemeter instrument does not have 'measure_voltage' method.")
                return False, None

            if response_str is not None:
                value_str_clean = response_str.split(',')[0].strip() # Keithley typically returns "voltage,current,resistance,..."
                if not value_str_clean:
                    print(f"Error: Sourcemeter 전압 결과가 비어있습니다.")
                    return False, None
                value = float(value_str_clean)
                return True, value
            else:
                print("Error: Sourcemeter 전압 측정 결과가 None입니다.")
                return False, None
        except (ValueError, IndexError, TypeError) as e:
            print(f"Error: Sourcemeter 전압 결과 파싱 오류: '{response_str}' ({e})")
            return False, None
        except Exception as e_meas:
            print(f"Error: Sourcemeter 전압 측정 중 예외 발생: {e_meas}")
            return False, None

    def measure_current(self, terminal_type_str: Optional[str] = None) -> tuple[bool, Optional[float]]: # 터미널 선택적
        if not self.is_connected or not self.instrument: return False, None

        # 명시적으로 터미널이 주어지면 설정, 아니면 현재 설정된 터미널 사용
        if terminal_type_str and not self.set_terminal(terminal_type_str):
            print(f"Error: Sourcemeter 터미널 설정 실패 ({terminal_type_str}) for measure_current")
            return False, None
        
        # 전류 측정을 위해 SENSE 기능 설정 (set_voltage 또는 configure_vsource_and_enable에서 이미 했을 수 있음)
        # 하지만 독립적인 측정 함수 호출 시 안전하게 다시 설정하는 것이 좋을 수 있음.
        if not self.gpib_write(":SENSe:FUNCtion 'CURRent:DC'"): return False, None
        if not self.gpib_write(":SENSe:CURRent:DC:RANGe:AUTO ON"): return False, None

        response_str: Optional[str] = None
        try:
            if hasattr(self.instrument, 'measure_current'):
                response_str = self.instrument.measure_current() # Use raonpy method
            else:
                print("Error: Sourcemeter instrument does not have 'measure_current' method.")
                return False, None
            
            if response_str is not None:
                value_str_clean = response_str.split(',')[0].strip() # Keithley typically returns "current,voltage,resistance,..."
                if not value_str_clean:
                    print(f"Error: Sourcemeter 전류 결과가 비어있습니다.")
                    return False, None
                value = float(value_str_clean)
                return True, value
            else:
                print("Error: Sourcemeter 전류 측정 결과가 None입니다.")
                return False, None
        except (ValueError, IndexError, TypeError) as e:
            print(f"Error: Sourcemeter 전류 결과 파싱 오류: '{response_str}' ({e})")
            return False, None
        except Exception as e_meas:
            print(f"Error: Sourcemeter 전류 측정 중 예외 발생: {e_meas}")
            return False, None


class Chamber(GPIBDevice, QObject):
    log_message_signal = pyqtSignal(str)
    def __init__(self, serial_number_str: Optional[str] = None, parent: Optional[QObject] = None):
        # 1. GPIBDevice의 __init__을 먼저 호출합니다.
        safe_serial = serial_number_str if serial_number_str is not None else ""
        
        device_class_to_pass = None
        if su241_runtime_module and hasattr(su241_runtime_module, 'SU241'):
            device_class_to_pass = su241_runtime_module.SU241
        else:
            print("Warning (Chamber.__init__): runtime_su241_module.SU241 not found for Chamber device_class_ref.")
            
        GPIBDevice.__init__(self, 
                              serial_number_str=safe_serial, 
                              device_name="Chamber (SU241)", 
                              device_class_ref=device_class_to_pass)

        # 2. QObject의 __init__을 명시적으로 호출합니다.
        QObject.__init__(self, parent) # Pass parent to QObject                              
        
        self.stop_flag_ref: Optional[SequencePlayerType] = None 

    def set_stop_flag_ref(self, player_instance: SequencePlayerType): # 타입 힌트 수정
        """SequencePlayer의 중단 플래그를 참조하기 위한 메소드"""
        self.stop_flag_ref = player_instance

    # ... (Chamber의 나머지 메소드들은 이전과 동일하게 유지) ...
    def set_target_temperature(self, temperature_float: float) -> bool:
        if not self.is_connected or not self.instrument: return False
        try:
            # Log the attempt to set temperature
            print(f"DEBUG_CHAMBER: Attempting to set target temperature to {temperature_float}°C via raonpy.")
            if hasattr(self.instrument, 'set_target_temp'): 
                self.instrument.set_target_temp(temperature_float)
                print(f"DEBUG_CHAMBER: Called self.instrument.set_target_temp({temperature_float})")
            elif hasattr(self.instrument, 'set_temp'): 
                self.instrument.set_temp(temperature_float)
                print(f"DEBUG_CHAMBER: Called self.instrument.set_temp({temperature_float})")
            elif hasattr(self.instrument, 'setTemperature'): 
                self.instrument.setTemperature(temperature_float)
                print(f"DEBUG_CHAMBER: Called self.instrument.setTemperature({temperature_float})")
            else:
                print(f"Error: {self.device_name}에 온도 설정 메서드가 없거나 SCPI 명령 전송 실패.")
                return False
            self._cached_target_temperature = temperature_float 
            print(f"DEBUG_CHAMBER: Target temperature {temperature_float}°C set and cached.")
            return True
        except Exception as e:
            print(f"Error: Chamber 목표 온도 설정 중 오류: {e}")
            return False

    def start_operation(self) -> bool:
        if not self.is_connected or not self.instrument: return False
        try:
            print(f"DEBUG_CHAMBER: Attempting to start chamber operation via raonpy.")
            if hasattr(self.instrument, 'start'): 
                self.instrument.start()
                print(f"DEBUG_CHAMBER: Called self.instrument.start()")
            elif hasattr(self.instrument, 'run'): 
                self.instrument.run()
                print(f"DEBUG_CHAMBER: Called self.instrument.run()")
            else: 
                print(f"Error: {self.device_name}에 동작 시작 메서드가 없거나 SCPI 명령 전송 실패.")
                return False
            return True
        except Exception as e: print(f"Error: Chamber 동작 시작 중 오류: {e}"); return False

    def get_current_temperature(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: return False, None
        current_temp_val: Any = None
        try:
            print(f"DEBUG_CHAMBER_GET_TEMP: Attempting to get current temperature via raonpy.")
            if hasattr(self.instrument, 'get_current_temp'): 
                current_temp_val = self.instrument.get_current_temp()
                print(f"DEBUG_CHAMBER_GET_TEMP: Raw value from get_current_temp: {current_temp_val}")
            elif hasattr(self.instrument, 'get_temp'): 
                current_temp_val = self.instrument.get_temp()
                print(f"DEBUG_CHAMBER_GET_TEMP: Raw value from get_temp: {current_temp_val}")
            elif hasattr(self.instrument, 'readTemperature'): 
                current_temp_val = self.instrument.readTemperature()
                print(f"DEBUG_CHAMBER_GET_TEMP: Raw value from readTemperature: {current_temp_val}")
            else:
                print(f"Error: {self.device_name}에 현재 온도 읽기 메서드가 없거나 SCPI 쿼리 실패.")
                return False, None

            if current_temp_val is not None:
                try:
                    value_str = str(current_temp_val).strip()
                    if not value_str:
                        return False, None
                    current_temp_float = float(value_str)
                    # 소수점 첫째 자리까지 버림
                    truncated_temp = float(int(current_temp_float * 10) / 10)
                    return True, truncated_temp
                except (ValueError, TypeError):
                    print(f"Error: Chamber 현재 온도 값 파싱 오류: {current_temp_val}")
                    return False, None
            return False, None 
        except Exception as e: print(f"Error: Chamber 현재 온도 읽기 중 오류: {e}"); return False, None

    def stop_operation(self) -> bool:
        if not self.is_connected or not self.instrument: return False
        try:
            if hasattr(self.instrument, 'stop'): self.instrument.stop()
            else: 
                print(f"Error: {self.device_name}에 동작 중지 메서드가 없거나 SCPI 명령 전송 실패.")
                return False
            return True
        except Exception as e: print(f"Error: Chamber 동작 중지 중 오류: {e}"); return False

    def power_off(self) -> bool: 
        if not self.is_connected or not self.instrument: return False
        try:
            if hasattr(self.instrument, 'power_off'): self.instrument.power_off()
            else: 
                print("Warning: Chamber에 power_off 기능이 명시적으로 없습니다. 동작 중지만 수행합니다.")
                return self.stop_operation() 
            return True
        except Exception as e: print(f"Error: Chamber 전원 끄는 중 오류: {e}"); return False

    def is_temperature_stable(self,
                              target_temp: float,
                              tolerance: float = constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG,
                              timeout_sec: float = constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC
                             ) -> tuple[bool, Optional[float]]:
        if not self.is_connected: return False, None
        start_time = time.time()
        last_measured_temp: Optional[float] = None
        
        log_msg_prefix = "Chamber (is_temperature_stable):"
        self.log_message_signal.emit(f"{log_msg_prefix} 온도 안정화 시작 (목표: {target_temp}°C, 허용오차: ±{tolerance}°C, 제한시간: {timeout_sec}초)")
        print(f"DEBUG_CHAMBER_STABLE: Entry - Target: {target_temp}, Tol: {tolerance}, Timeout: {timeout_sec}")

        while time.time() - start_time < timeout_sec:
            if self.stop_flag_ref and self.stop_flag_ref.request_stop_flag:
                msg_stop = f"{log_msg_prefix} 온도 안정화 대기 중 중단 요청됨."
                self.log_message_signal.emit(msg_stop)
                print(f"DEBUG_CHAMBER_STABLE: {msg_stop}")
                return False, last_measured_temp

            read_success, current_temp = self.get_current_temperature()
            print(f"DEBUG_CHAMBER_STABLE: Loop - Read success: {read_success}, Current temp: {current_temp}")
            if read_success and current_temp is not None:
                last_measured_temp = current_temp
                self.log_message_signal.emit(f"  Chamber: 현재 {current_temp:.1f}°C (목표 {target_temp}°C)")
                if abs(current_temp - target_temp) <= tolerance:
                    msg_stable = f"{log_msg_prefix} 온도가 {target_temp}°C 로 안정화되었습니다 (현재: {current_temp:.1f}°C)."
                    self.log_message_signal.emit(msg_stable)
                    print(f"DEBUG_CHAMBER_STABLE: {msg_stable}")
                    return True, current_temp
            else: 
                msg_read_fail = f"{log_msg_prefix} 현재 온도 읽기 실패. 재시도..."
                self.log_message_signal.emit(msg_read_fail)
                print(f"DEBUG_CHAMBER_STABLE: {msg_read_fail}")
            
            sleep_interval = 1.0 
            time_left = timeout_sec - (time.time() - start_time)
            actual_sleep = min(sleep_interval, max(0, time_left))
            if actual_sleep == 0 and time_left > 0: 
                actual_sleep = time_left
            print(f"DEBUG_CHAMBER_STABLE: Sleeping for {actual_sleep:.2f}s (Time left: {time_left:.2f}s)")

            if actual_sleep > 0:
                 time.sleep(actual_sleep)

        msg_timeout = f"{log_msg_prefix} 온도 안정화 시간 초과 (목표: {target_temp}°C, 최종: {last_measured_temp if last_measured_temp is not None else 'N/A'}°C, 제한시간: {timeout_sec}초)."
        self.log_message_signal.emit(msg_timeout)
        print(f"DEBUG_CHAMBER_STABLE: {msg_timeout}")
        return False, last_measured_temp