"""Test the WireGuardUpdateCoordinator."""
from unittest.mock import patch

import requests

from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import mocked_requests

from tests.common import MockConfigEntry


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Test WireGuardUpdateCoordinator."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        data={CONF_HOST: DEFAULT_HOST},
    )
    config_entry.add_to_hass(hass)

    with patch("requests.get", side_effect=mocked_requests):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_failed(hass: HomeAssistant) -> None:
    """Test WireGuardUpdateCoordinator."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        data={CONF_HOST: DEFAULT_HOST},
    )
    config_entry.add_to_hass(hass)

    with patch("requests.get", side_effect=requests.RequestException):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
