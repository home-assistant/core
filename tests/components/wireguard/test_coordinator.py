"""Test the WireGuardUpdateCoordinator."""
from unittest.mock import patch

from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import mocked_requests

from tests.common import MockConfigEntry


async def test_wireguard_data_update_coordinator(hass: HomeAssistant) -> None:
    """Test WireGuardUpdateCoordinator."""
    with patch("requests.get", side_effect=mocked_requests):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="UNIQUE_TEST_ID",
            data={CONF_HOST: DEFAULT_HOST},
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.dummy_connectivity")
    assert state is not None
    assert state.state == "off"
