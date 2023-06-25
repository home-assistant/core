"""Test ESPHome enum mapper."""

from aioesphomeapi import APIIntEnum

from homeassistant.backports.enum import StrEnum
from homeassistant.components.esphome.enum_mapper import EsphomeEnumMapper


class MockEnum(APIIntEnum):
    """Mock enum."""

    ESPHOME_FOO = 1
    ESPHOME_BAR = 2


class MockStrEnum(StrEnum):
    """Mock enum."""

    HA_FOO = "foo"
    HA_BAR = "bar"


MOCK_MAPPING: EsphomeEnumMapper[MockEnum, MockStrEnum] = EsphomeEnumMapper(
    {
        MockEnum.ESPHOME_FOO: MockStrEnum.HA_FOO,
        MockEnum.ESPHOME_BAR: MockStrEnum.HA_BAR,
    }
)


async def test_map_esphome_to_ha() -> None:
    """Test mapping from ESPHome to HA."""

    assert MOCK_MAPPING.from_esphome(MockEnum.ESPHOME_FOO) == MockStrEnum.HA_FOO
    assert MOCK_MAPPING.from_esphome(MockEnum.ESPHOME_BAR) == MockStrEnum.HA_BAR


async def test_map_ha_to_esphome() -> None:
    """Test mapping from HA to ESPHome."""

    assert MOCK_MAPPING.from_hass(MockStrEnum.HA_FOO) == MockEnum.ESPHOME_FOO
    assert MOCK_MAPPING.from_hass(MockStrEnum.HA_BAR) == MockEnum.ESPHOME_BAR
