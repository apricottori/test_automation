# core/hardware_control.py
import time
# typing 모듈에서 필요한 요소들을 임포트합니다.
from typing import Optional, Tuple, Any, ForwardRef, TYPE_CHECKING 
from PyQt5.QtCore import pyqtSignal

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

try:
    from raonpy.rti.efm8evb import EVB as RuntimeEVB # 런타임용
    from raonpy.device.keithley2401 import KEITHLEY2401 as RuntimeKEITHLEY2401
    from raonpy.device.agilent34401a import Agilent34401A as RuntimeAgilent34401A
    from raonpy.device import su241 as runtime_raon_su241 
    EVB_런타임 = RuntimeEVB # 명확한 이름 사용
    KEITHLEY2401_런타임 = RuntimeKEITHLEY2401
    Agilent34401A_런타임 = RuntimeAgilent34401A
    raon_su241_런타임 = runtime_raon_su241
except ImportError as e:
    print(f"Critical Error: raonpy 라이브러리 또는 일부 모듈을 찾을 수 없습니다. {e}")
    # 타입 힌트용 클래스가 로드되지 않았을 수 있으므로, 런타임 대체용 None 설정
    EVB_런타임 = None 
    KEITHLEY2401_런타임 = None
    Agilent34401A_런타임 = None
    raon_su241_런타임 = None
    # 타입 힌트용도 None으로 설정하여 AttributeError 방지 (선택적)
    if 'EVB' not in globals(): EVB = None # type: ignore
    if 'KEITHLEY2401' not in globals(): KEITHLEY2401 = None # type: ignore
    if 'Agilent34401A' not in globals(): Agilent34401A = None # type: ignore
    if 'raon_su241_typing' not in globals(): raon_su241_typing = None # type: ignore


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

        if EVB_런타임 is None: 
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
            
            self.evb_instance = EVB_런타임() 
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
        self.instrument: Optional[Any] = None # Any는 유지하거나, 더 구체적인 기본 클래스 타입으로 변경 가능
        self.is_connected: bool = False
        self.device_class_ref = device_class_ref # 실제 런타임 클래스 참조

        self._cached_set_voltage: Optional[float] = None
        self._cached_set_current: Optional[float] = None
        self._cached_target_temperature: Optional[float] = None

        actual_device_class = None
        if device_name == "Multimeter (Agilent34401A)": actual_device_class = Agilent34401A_런타임
        elif device_name == "Sourcemeter (Keithley2401)": actual_device_class = KEITHLEY2401_런타임
        elif device_name == "Chamber (SU241)": actual_device_class = raon_su241_런타임.SU241 if raon_su241_런타임 else None
        else: actual_device_class = self.device_class_ref

        if actual_device_class is None:
            print(f"Error: {self.device_name}의 device class 로드 실패. 장치를 초기화할 수 없습니다.")
            return

        is_chamber = "Chamber" in self.device_name 
        try:
            if device_name in ["Multimeter (Agilent34401A)", "Sourcemeter (Keithley2401)"]:
                self.instrument = actual_device_class() # No serial_number_str here
            elif serial_number_str and not is_chamber:
                self.instrument = actual_device_class(serial_number_str)
            elif is_chamber:
                self.instrument = actual_device_class()
            else:
                print(f"Error: Insufficient information to initialize {self.device_name}.")
                return 

            if self.instrument and hasattr(self.instrument, 'set_verbose'):
                 self.instrument.set_verbose(False) 
            print(f"Info: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 인스턴스가 생성되었습니다.")
        except TypeError as te: 
             print(f"Error: {self.device_name}(SN/Addr: {self.serial_number if self.serial_number else 'N/A'}) 인스턴스 생성 중 TypeError: {te}. raonpy 라이브러리 API를 확인하세요.")
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
            # For instruments initialized without address, pass it to open/connect
            if self.device_name in ["Multimeter (Agilent34401A)", "Sourcemeter (Keithley2401)"] and self.serial_number:
                self.instrument.open(self.serial_number) # open() takes the address
            else:
                self.instrument.open() # For Chamber or others not needing address at open

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
            print(f"Error: {self.device_name}이(가) 연결되지 않았습니다.")
            return False, None

        querier = None
        if hasattr(self.instrument, 'query'):
            querier = self.instrument.query
        elif hasattr(self.instrument, 'gpib') and hasattr(self.instrument.gpib, 'query'):
            querier = self.instrument.gpib.query

        if querier:
            try:
                if delay: time.sleep(delay)
                response = querier(command_str)
                response_str = response.strip() if isinstance(response, str) else str(response) 
                return True, response_str
            except Exception as e:
                print(f"Error: {self.device_name} 쿼리 중 오류 ('{command_str}'): {e}")
                return False, None
        else:
            print(f"Error: {self.device_name}에 'query' 또는 'gpib.query' 메서드가 없습니다.")
            return False, None

    def reset(self) -> bool:
        return self.gpib_write("*RST")

    def get_cached_set_voltage(self) -> Optional[float]: return self._cached_set_voltage
    def get_cached_set_current(self) -> Optional[float]: return self._cached_set_current
    def get_cached_target_temperature(self) -> Optional[float]: return self._cached_target_temperature


class Multimeter(GPIBDevice):
    def __init__(self, serial_number_str: str):
        super().__init__(serial_number_str, "Multimeter (Agilent34401A)", Agilent34401A_런타임)
    # ... (Multimeter의 나머지 메소드들은 이전과 동일하게 유지) ...
    def measure_voltage(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: return False, None
        raw_value: Any = None
        try:
            if hasattr(self.instrument, 'measure_voltage'):
                raw_value = self.instrument.measure_voltage() 
            else: 
                success_query, raw_value_str = self.gpib_query(":MEASure:VOLTage:DC?")
                if not success_query or raw_value_str is None: return False, None
                raw_value = raw_value_str
            
            value_str = str(raw_value).strip()
            if not value_str: 
                print(f"Error: Multimeter 전압 측정 결과가 비어있습니다.")
                return False, None
            value = float(value_str)
            return True, value
        except (ValueError, TypeError) as e: 
            print(f"Error: Multimeter 전압 측정 결과 처리 중 예외 발생: {e} (raw_value: {raw_value})")
            return False, None
        except Exception as e: 
            print(f"Error: Multimeter 전압 측정 중 예외 발생: {e}")
            return False, None

    def measure_current(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: return False, None
        raw_value: Any = None
        try:
            if hasattr(self.instrument, 'measure_current'):
                raw_value = self.instrument.measure_current()
            else:
                success_query, raw_value_str = self.gpib_query(":MEASure:CURRent:DC?")
                if not success_query or raw_value_str is None: return False, None
                raw_value = raw_value_str
            
            value_str = str(raw_value).strip()
            if not value_str:
                print(f"Error: Multimeter 전류 측정 결과가 비어있습니다.")
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
        if terminal_type_str.upper() == constants.TERMINAL_FRONT.upper(): 
            print(f"Info: {self.device_name}은(는) 기본적으로 전면 터미널을 사용합니다.")
            return True
        elif terminal_type_str.upper() == constants.TERMINAL_REAR.upper():
            print(f"Warning: {self.device_name}은(는) 후면 터미널을 지원하지 않거나, SCPI 명령이 없을 수 있습니다.")
            return False 
        else:
            print(f"Error: 잘못된 터미널 타입입니다: {terminal_type_str}")
            return False


class Sourcemeter(GPIBDevice):
    def __init__(self, serial_number_str: str):
        super().__init__(serial_number_str, "Sourcemeter (Keithley2401)", KEITHLEY2401_런타임)
    # ... (Sourcemeter의 나머지 메소드들은 이전과 동일하게 유지) ...
    def connect(self) -> bool:
        if super().connect():
            return self.reset() and self.gpib_write("*CLS")
        return False

    def set_terminal(self, terminal_type_str: str) -> bool:
        cmd = f":ROUTe:TERMinals {terminal_type_str.upper()}"
        success = self.gpib_write(cmd)
        if success: time.sleep(0.1) 
        return success

    def enable_output(self, state: bool) -> bool:
        cmd = f":OUTPut:STATe {'ON' if state else 'OFF'}"
        return self.gpib_write(cmd)

    def set_voltage(self, voltage_float: float, terminal_type_str: str = constants.TERMINAL_FRONT) -> bool:
        if not self.is_connected: return False
        if not self.set_terminal(terminal_type_str): return False
        if not self.gpib_write(":SOURce:FUNCtion VOLTage"): return False
        if not self.gpib_write(f":SOURce:VOLTage:LEVel {voltage_float:.6f}"): return False
        if not self.enable_output(True): return False
        
        self._cached_set_voltage = voltage_float 
        self._cached_set_current = None 
        return True

    def set_current(self, current_float: float, terminal_type_str: str = constants.TERMINAL_FRONT) -> bool:
        if not self.is_connected: return False
        if not self.set_terminal(terminal_type_str): return False
        if not self.gpib_write(":SOURce:FUNCtion CURRent"): return False
        if not self.gpib_write(f":SOURce:CURRent:LEVel {current_float:.6e}"): return False
        if not self.enable_output(True): return False
        
        self._cached_set_current = current_float 
        self._cached_set_voltage = None 
        return True

    def set_protection_current(self, current_limit_amps: float) -> bool:
        if not self.is_connected: return False
        cmd = f":SENSe:CURRent:PROTection {current_limit_amps:.6e}"
        return self.gpib_write(cmd)

    def _configure_measurement(self, meas_type: str = "VOLT", terminal: str = constants.TERMINAL_FRONT) -> bool:
        if not self.set_terminal(terminal): return False
        if meas_type.upper() == "VOLT":
            if not self.gpib_write(":SENSe:FUNCtion 'VOLTage:DC'"): return False
            if not self.gpib_write(":SENSe:VOLTage:DC:NPLCycles 1"): return False 
        elif meas_type.upper() == "CURR":
            if not self.gpib_write(":SENSe:FUNCtion 'CURRent:DC'"): return False
            if not self.gpib_write(":SENSe:CURRent:DC:NPLCycles 1"): return False
        else: 
            print(f"Error: 지원되지 않는 측정 타입입니다: {meas_type}")
            return False
        if not self.gpib_write(f":FORMat:ELEMents {meas_type.upper()}"): return False
        return True

    def measure_voltage(self, terminal_type_str: str = constants.TERMINAL_FRONT) -> tuple[bool, Optional[float]]:
        if not self.is_connected: return False, None
        if not self._configure_measurement("VOLT", terminal_type_str): return False, None
        
        success_query, response_str = self.gpib_query(":READ?") 
        if success_query and response_str is not None:
            try:
                value_str_clean = response_str.split(',')[0].strip()
                if not value_str_clean:
                    print(f"Error: Sourcemeter 전압 결과가 비어있습니다.")
                    return False, None
                value = float(value_str_clean)
                return True, value
            except (ValueError, IndexError, TypeError) as e:
                print(f"Error: Sourcemeter 전압 결과 파싱 오류: '{response_str}' ({e})")
        return False, None

    def measure_current(self, terminal_type_str: str = constants.TERMINAL_FRONT) -> tuple[bool, Optional[float]]:
        if not self.is_connected: return False, None
        if not self._configure_measurement("CURR", terminal_type_str): return False, None
        
        success_query, response_str = self.gpib_query(":READ?") 
        if success_query and response_str is not None:
            try:
                value_str_clean = response_str.split(',')[0].strip()
                if not value_str_clean:
                    print(f"Error: Sourcemeter 전류 결과가 비어있습니다.")
                    return False, None
                value = float(value_str_clean)
                return True, value
            except (ValueError, IndexError, TypeError) as e:
                print(f"Error: Sourcemeter 전류 결과 파싱 오류: '{response_str}' ({e})")
        return False, None


class Chamber(GPIBDevice):
    log_message_signal = pyqtSignal(str) 

    def __init__(self, serial_number_str: Optional[str] = None):
        # raonpy.device.su241.SU241 클래스 참조 전달
        device_class_to_use = raon_su241_런타임.SU241 if raon_su241_런타임 and hasattr(raon_su241_런타임, 'SU241') else None
        super().__init__(serial_number_str if serial_number_str else "", 
                         "Chamber (SU241)",
                         device_class_to_use)
        # SequencePlayerType은 이 파일 상단에서 ForwardRef로 정의됨
        self.stop_flag_ref: Optional[SequencePlayerType] = None 

    def set_stop_flag_ref(self, player_instance: SequencePlayerType): # 타입 힌트 수정
        """SequencePlayer의 중단 플래그를 참조하기 위한 메소드"""
        self.stop_flag_ref = player_instance

    # ... (Chamber의 나머지 메소드들은 이전과 동일하게 유지) ...
    def set_target_temperature(self, temperature_float: float) -> bool:
        if not self.is_connected or not self.instrument: return False
        try:
            if hasattr(self.instrument, 'set_target_temp'): self.instrument.set_target_temp(temperature_float)
            elif hasattr(self.instrument, 'set_temp'): self.instrument.set_temp(temperature_float)
            elif hasattr(self.instrument, 'setTemperature'): self.instrument.setTemperature(temperature_float)
            else:
                print(f"Error: {self.device_name}에 온도 설정 메서드가 없거나 SCPI 명령 전송 실패.")
                return False
            self._cached_target_temperature = temperature_float 
            return True
        except Exception as e:
            print(f"Error: Chamber 목표 온도 설정 중 오류: {e}")
            return False

    def start_operation(self) -> bool:
        if not self.is_connected or not self.instrument: return False
        try:
            if hasattr(self.instrument, 'start'): self.instrument.start()
            elif hasattr(self.instrument, 'run'): self.instrument.run()
            else: 
                print(f"Error: {self.device_name}에 동작 시작 메서드가 없거나 SCPI 명령 전송 실패.")
                return False
            return True
        except Exception as e: print(f"Error: Chamber 동작 시작 중 오류: {e}"); return False

    def get_current_temperature(self) -> tuple[bool, Optional[float]]:
        if not self.is_connected or not self.instrument: return False, None
        current_temp_val: Any = None
        try:
            if hasattr(self.instrument, 'get_current_temp'): current_temp_val = self.instrument.get_current_temp()
            elif hasattr(self.instrument, 'get_temp'): current_temp_val = self.instrument.get_temp()
            elif hasattr(self.instrument, 'readTemperature'): current_temp_val = self.instrument.readTemperature()
            else:
                print(f"Error: {self.device_name}에 현재 온도 읽기 메서드가 없거나 SCPI 쿼리 실패.")
                return False, None

            if current_temp_val is not None:
                try:
                    value_str = str(current_temp_val).strip()
                    if not value_str:
                        return False, None
                    current_temp_float = float(value_str)
                    return True, current_temp_float
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
        
        # log_message_signal은 Chamber 클래스에 직접 정의되어야 함
        if self.log_message_signal: 
            self.log_message_signal.emit(f"Chamber: 온도 안정화 시작 (목표: {target_temp}°C, 허용오차: ±{tolerance}°C, 제한시간: {timeout_sec}초)")

        while time.time() - start_time < timeout_sec:
            # SequencePlayer의 request_stop_flag를 확인 (참조가 설정되었다면)
            if self.stop_flag_ref and self.stop_flag_ref.request_stop_flag:
                if self.log_message_signal: self.log_message_signal.emit("Chamber: 온도 안정화 대기 중 중단 요청됨.")
                return False, last_measured_temp

            read_success, current_temp = self.get_current_temperature()
            if read_success and current_temp is not None:
                last_measured_temp = current_temp
                if self.log_message_signal: self.log_message_signal.emit(f"  Chamber: 현재 {current_temp:.1f}°C (목표 {target_temp}°C)")
                if abs(current_temp - target_temp) <= tolerance:
                    if self.log_message_signal: self.log_message_signal.emit(f"Chamber: 온도가 {target_temp}°C 로 안정화되었습니다 (현재: {current_temp:.1f}°C).")
                    return True, current_temp
            else: 
                if self.log_message_signal: self.log_message_signal.emit("  Chamber: 현재 온도 읽기 실패. 재시도...")
            
            sleep_interval = 1.0 
            time_left = timeout_sec - (time.time() - start_time)
            actual_sleep = min(sleep_interval, max(0, time_left))
            if actual_sleep == 0 and time_left > 0: 
                actual_sleep = time_left

            if actual_sleep > 0:
                 time.sleep(actual_sleep)
            # 루프 시작에서 중단 플래그를 확인하므로 여기서 중복 확인 불필요
            # if self.stop_flag_ref and self.stop_flag_ref.request_stop_flag: continue 

        if self.log_message_signal: self.log_message_signal.emit(f"Chamber: 온도 안정화 시간 초과 (목표: {target_temp}°C, 최종: {last_measured_temp if last_measured_temp is not None else 'N/A'}°C, 제한시간: {timeout_sec}초).")
        return False, last_measured_temp