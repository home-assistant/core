"""Test Modem Caller ID integration."""
from unittest.mock import patch

from phone_modem import exceptions

from homeassistant.components.modem_callerid.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_SETUP_RETRY

from . import CONF_DATA

from tests.common import MockConfigEntry


async def test_setup_config(hass):
    """Test Modem Caller ID setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.modem_callerid.PhoneModem",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state == ENTRY_STATE_LOADED


async def test_async_setup_entry_not_ready(hass):
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.modem_callerid.PhoneModem",
        side_effect=exceptions.SerialError(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(hass):
    """Test unload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.modem_callerid.async_setup_entry",
        return_value=True,
    ) as modem_setup:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(modem_setup.mock_calls) == 1
        assert config_entry.state == ENTRY_STATE_LOADED

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await hass.config_entries.async_unload(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert unload.call_count == 1

    assert not hass.data.get(DOMAIN)


async def test_failed_unload_config_entry(hass):
    """Test failed unload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.modem_callerid.async_setup_entry",
        return_value=True,
    ) as modem_setup:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(modem_setup.mock_calls) == 1
        assert config_entry.state == ENTRY_STATE_LOADED

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=False
    ) as unload:
        assert await hass.config_entries.async_unload(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert unload.call_count == 1

    assert config_entry.state == ENTRY_STATE_LOADED
