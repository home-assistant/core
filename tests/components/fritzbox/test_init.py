"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from unittest.mock import Mock, call, patch

from pyfritzhome import LoginError
from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG, FritzDeviceSwitchMock, setup_config_entry

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of integration."""
    assert await setup_config_entry(hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0])
    entries = hass.config_entries.async_entries()
    assert entries
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == "fake_host"
    assert entries[0].data[CONF_PASSWORD] == "fake_pass"
    assert entries[0].data[CONF_USERNAME] == "fake_user"
    assert fritz.call_count == 1
    assert fritz.call_args_list == [
        call(host="fake_host", password="fake_pass", user="fake_user")
    ]


async def test_coordinator_update_after_reboot(hass: HomeAssistant, fritz: Mock):
    """Test coordinator after reboot."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().get_devices.side_effect = [HTTPError(), ""]

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().get_devices.call_count == 2
    assert fritz().login.call_count == 2


async def test_coordinator_update_after_password_change(
    hass: HomeAssistant, fritz: Mock
):
    """Test coordinator after password change."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().get_devices.side_effect = HTTPError()
    fritz().login.side_effect = ["", HTTPError()]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().get_devices.call_count == 1
    assert fritz().login.call_count == 2


async def test_unload_remove(hass: HomeAssistant, fritz: Mock):
    """Test unload and remove of integration."""
    fritz().get_devices.return_value = [FritzDeviceSwitchMock()]
    entity_id = f"{SWITCH_DOMAIN}.fake_name"

    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id=entity_id,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(FB_DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_LOADED
    state = hass.states.get(entity_id)
    assert state

    await hass.config_entries.async_unload(entry.entry_id)

    assert fritz().logout.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert fritz().logout.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    state = hass.states.get(entity_id)
    assert state is None


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant):
    """Config entry state is ENTRY_STATE_SETUP_RETRY when fritzbox is offline."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data={CONF_HOST: "any", **MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0]},
        unique_id="any",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fritzbox.Fritzhome.login",
        side_effect=LoginError("user"),
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_login.assert_called_once()

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.state == ENTRY_STATE_SETUP_ERROR
