"""Test the LaCrosse View initialization."""
from unittest.mock import patch

from lacrosse_view import HTTPError, LoginError

from homeassistant.components.lacrosse_view.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, TEST_SENSOR

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the unload entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", return_value=True), patch(
        "lacrosse_view.LaCrosse.get_sensors",
        return_value=[TEST_SENSOR],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state == ConfigEntryState.NOT_LOADED


async def test_login_error(hass: HomeAssistant) -> None:
    """Test login error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", side_effect=LoginError("Test")):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.SETUP_RETRY


async def test_http_error(hass: HomeAssistant) -> None:
    """Test http error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", return_value=True), patch(
        "lacrosse_view.LaCrosse.get_sensors", side_effect=HTTPError
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.SETUP_RETRY
