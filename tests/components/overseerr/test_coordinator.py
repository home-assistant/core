"""Test the OverseerrUpdateCoordinator."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    overseerr_request_data: MagicMock,
) -> None:
    """Test OverseerrUpdateCoordinator."""
    config_entry.add_to_hass(hass)
    overseerr_request_data.side_effect = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    overseerr_request_data: MagicMock,
) -> None:
    """Test OverseerrUpdateCoordinator if client fails."""
    config_entry.add_to_hass(hass)
    overseerr_request_data.side_effect = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Raise exception in request data
    overseerr_request_data.fetch_data.side_effect = Exception("Boom")

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    with pytest.raises(Exception):
        await coordinator._async_update_data()
        assert not coordinator.last_update_success
