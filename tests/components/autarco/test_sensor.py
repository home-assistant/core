"""Test the sensor provided by the Autarco integration."""

from unittest.mock import MagicMock, patch

from autarco import Solar

from homeassistant.components.autarco.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture


async def test_solar_sensors(
    hass: HomeAssistant,
    mock_autarco_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Autarco - Solar sensor."""
    with patch("homeassistant.components.autarco.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    mock_autarco_client.get_solar.return_value = Solar.from_dict(
        load_json_object_fixture("solar.json", DOMAIN)
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4
