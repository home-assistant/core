"""Common tests for the Cielo Home climate."""

from unittest.mock import MagicMock

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_climate_set_temperature_calls_library(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cielo_device_api: MagicMock,
) -> None:
    """Test setting temperature calls into the library client/device API."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.living_room_living_room"

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 25},
        blocking=True,
    )

    mock_cielo_device_api.async_set_temperature.assert_awaited_once_with(
        UnitOfTemperature.CELSIUS,
        temperature=25.0,
    )
