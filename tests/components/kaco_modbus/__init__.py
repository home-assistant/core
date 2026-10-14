"""Tests for the KACO Modbus integration."""

from kaco_modbus.testing import BASE_ADDRESS

from homeassistant.components.kaco_modbus.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

END_OF_CHAIN = 0xFFFF

MOCK_SERIAL = "8.6TL00000000"
MOCK_MODEL = "blueplanet 8.6 TL3 INT"

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}


def model_registers(image: dict[int, int], model_id: int) -> range:
    """Return the registers *model_id* occupies in a captured image.

    Walks the SunSpec model chain rather than hard-coding an offset, so a
    test can make one block unreadable and leave the rest answering.
    """
    address = BASE_ADDRESS + 2  # past the "SunS" marker
    while (found := image[address]) != END_OF_CHAIN:
        length = image[address + 1]
        if found == model_id:
            return range(address, address + 2 + length)
        address += 2 + length
    raise KeyError(f"model {model_id} is not in this image")
