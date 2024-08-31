"""Test the Nina init file."""
from typing import Any
from unittest.mock import patch

from pynina import ApiError

from homeassistant.components.nina.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import mocked_request_function

from tests.common import MockConfigEntry

ENTRY_DATA: dict[str, Any] = {
    "slots": 5,
    "headline_filter": ".*corona.*",
    "area_filter": ".*",
    "regions": {"083350000000": "Aach, Stadt"},
}


async def init_integration(hass) -> MockConfigEntry:
    """Set up the NINA integration in Home Assistant."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )
        entry.add_to_hass(hass)

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        return entry


async def test_config_migration(hass: HomeAssistant) -> None:
    """Test the migration to a new configuration layout."""

    old_entry_data: dict[str, Any] = {
        "slots": 5,
        "corona_filter": True,
        "regions": {"083350000000": "Aach, Stadt"},
    }

    old_conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=old_entry_data
    )

    old_conf_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_conf_entry.entry_id)
    await hass.async_block_till_done()

    assert dict(old_conf_entry.data) == ENTRY_DATA


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the configuration entry."""
    entry: MockConfigEntry = await init_integration(hass)

    assert entry.state == ConfigEntryState.LOADED


async def test_sensors_connection_error(hass: HomeAssistant) -> None:
    """Test the creation and values of the NINA sensors with no connected."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to Api"),
    ):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )

        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state == ConfigEntryState.SETUP_RETRY
