# data_models.py
from typing import List, Tuple, TypedDict, Optional # Optional 추가

class LogicalFieldInfo(TypedDict):
    """
    Represents a logical register field, potentially spanning multiple addresses or bit regions.
    JSON 파일의 "registers" 배열 내 각 객체 정보와 파생된 정보를 저장합니다.
    """
    id: str                     # Original ID from JSON, e.g., "PRODUCT_CODE"
    display_name: str           # User-facing name, e.g., "PRODUCT_CODE<11:0>", "ENABLE"
    access: str                 # Access type mapped to "RO", "RW", "WO", or "N/A"
    length: int                 # Total bit length of the field
    
    # The following global_lsb/msb_index are relative to the field itself.
    # For a field of 'length' bits, its own LSB is 0 and MSB is length-1.
    global_lsb_index: int       # Typically 0 for the field's own context
    global_msb_index: int       # Typically field_info['length'] - 1
    
    initial_value_int: int      # Integer representation of the field's initial (reset) value
    description: Optional[str]  # Description of the field, from JSON

    # List of tuples, each describing a contiguous segment (region) of this field within an 8-bit address.
    # Each tuple: (
    #   address_hex: str,          # e.g., "0X0005"
    #   local_bit_offset: int,     # LSB position of this segment within the 8-bit address (0-7)
    #   local_bit_width: int,      # Number of bits this segment occupies in this address
    #   field_part_lsb_in_field: int, # LSB index of this segment *within the field* (0 to field.length-1)
    #   field_part_msb_in_field: int  # MSB index of this segment *within the field* (0 to field.length-1)
    # )
    # The list is sorted by field_part_lsb_in_field (LSB part of the field first).
    regions_mapping: List[Tuple[str, int, int, int, int]]


class AddressBitMapping(TypedDict):
    """
    Represents how a part of a logical field maps to a specific 8-bit address.
    Used in RegisterMap.address_layout.
    """
    field_id: str               # ID of the logical field this part belongs to
    local_lsb: int              # LSB position of this field part within the 8-bit address (0-7)
    local_msb: int              # MSB position of this field part within the 8-bit address (0-7)
    
    # LSB index of this part relative to the field's overall LSB (which is 0 for the field)
    field_part_lsb_relative_to_field_lsb: int 
    # MSB index of this part relative to the field's overall LSB
    field_part_msb_relative_to_field_lsb: int

# Example of how these might be used (conceptual, actual usage in RegisterMap class)
#
# product_code_field_example: LogicalFieldInfo = {
#     "id": "PRODUCT_CODE",
#     "display_name": "PRODUCT_CODE<11:0>",
#     "access": "RO",
#     "length": 12,
#     "global_lsb_index": 0,
#     "global_msb_index": 11,
#     "initial_value_int": 0xRDP, # Example value
#     "description": "This is the product code register.", # 예시 설명 추가
#     "regions_mapping": [
#         # Assuming 0x0000 holds LSB part, 0x0001 holds MSB part based on JSON structure
#         # (address, local_offset, local_width, field_part_lsb, field_part_msb)
#         ("0X0000", 0, 8, 0, 7),   # This region is bits 0-7 of PRODUCT_CODE
#         ("0X0001", 4, 4, 8, 11)   # This region is bits 8-11 of PRODUCT_CODE
#     ]
# }
#
# address_0x0000_layout_example: List[AddressBitMapping] = [
#     {
#         "field_id": "PRODUCT_CODE",
#         "local_lsb": 0,
#         "local_msb": 7,
#         "field_part_lsb_relative_to_field_lsb": 0,
#         "field_part_msb_relative_to_field_lsb": 7
#     },
#     # ... other fields or parts of fields in address 0x0000
# ] 