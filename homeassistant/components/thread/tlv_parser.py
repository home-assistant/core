"""Parse datasets TLV encoded as specified by Thread."""
from __future__ import annotations

from enum import IntEnum

from homeassistant.exceptions import HomeAssistantError


class MeshcopTLVType(IntEnum):
    """Types."""

    CHANNEL = 0
    PANID = 1
    EXTPANID = 2
    NETWORKNAME = 3
    PSKC = 4
    NETWORKKEY = 5
    NETWORK_KEY_SEQUENCE = 6
    MESHLOCALPREFIX = 7
    STEERING_DATA = 8
    BORDER_AGENT_RLOC = 9
    COMMISSIONER_ID = 10
    COMM_SESSION_ID = 11
    SECURITYPOLICY = 12
    GET = 13
    ACTIVETIMESTAMP = 14
    COMMISSIONER_UDP_PORT = 15
    STATE = 16
    JOINER_DTLS = 17
    JOINER_UDP_PORT = 18
    JOINER_IID = 19
    JOINER_RLOC = 20
    JOINER_ROUTER_KEK = 21
    PROVISIONING_URL = 32
    VENDOR_NAME_TLV = 33
    VENDOR_MODEL_TLV = 34
    VENDOR_SW_VERSION_TLV = 35
    VENDOR_DATA_TLV = 36
    VENDOR_STACK_VERSION_TLV = 37
    UDP_ENCAPSULATION_TLV = 48
    IPV6_ADDRESS_TLV = 49
    PENDINGTIMESTAMP = 51
    DELAYTIMER = 52
    CHANNELMASK = 53
    COUNT = 54
    PERIOD = 55
    SCAN_DURATION = 56
    ENERGY_LIST = 57
    DISCOVERYREQUEST = 128
    DISCOVERYRESPONSE = 129
    JOINERADVERTISEMENT = 241


def _parse_item(tag: MeshcopTLVType, data: bytes) -> str:
    """Parse a TLV encoded dataset item."""
    if tag == MeshcopTLVType.NETWORKNAME:
        try:
            return data.decode()
        except UnicodeDecodeError as err:
            raise HomeAssistantError(f"invalid network name '{data.hex()}'") from err

    return data.hex()


def parse_tlv(data: str) -> dict[MeshcopTLVType, str]:
    """Parse a TLV encoded dataset.

    Raises if the TLV is invalid.
    """
    try:
        data_bytes = bytes.fromhex(data)
    except ValueError as err:
        raise HomeAssistantError("invalid tlvs") from err
    result = {}
    pos = 0
    while pos < len(data_bytes):
        try:
            tag = MeshcopTLVType(data_bytes[pos])
        except ValueError as err:
            raise HomeAssistantError(f"unknown type {data_bytes[pos]}") from err
        pos += 1
        _len = data_bytes[pos]
        pos += 1
        val = data_bytes[pos : pos + _len]
        if len(val) < _len:
            raise HomeAssistantError(
                f"expected {_len} bytes for {tag.name}, got {len(val)}"
            )
        pos += _len
        if tag in result:
            raise HomeAssistantError(f"duplicated tag {tag.name}")
        result[tag] = _parse_item(tag, val)
    return result
