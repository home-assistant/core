"""Tests for the AVM Fritz!Box integration."""
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
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG, FritzDeviceSwitchMock

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of integration."""
    assert await async_setup_component(hass, FB_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries()
    assert entries
    assert entries[0].data[CONF_HOST] == "fake_host"
    assert entries[0].data[CONF_PASSWORD] == "fake_pass"
    assert entries[0].data[CONF_USERNAME] == "fake_user"
    assert fritz.call_count == 1
    assert fritz.call_args_list == [
        call(host="fake_host", password="fake_pass", user="fake_user")
    ]


async def test_setup_duplicate_config(hass: HomeAssistant, fritz: Mock, caplog):
    """Test duplicate config of integration."""
    DUPLICATE = {
        FB_DOMAIN: {
            CONF_DEVICES: [
                MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
                MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
            ]
        }
    }
    assert not await async_setup_component(hass, FB_DOMAIN, DUPLICATE)
    await hass.async_block_till_done()
    assert not hass.states.async_entity_ids()
    assert not hass.states.async_all()
    assert "duplicate host entries found" in caplog.text


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

    assert await async_setup_component(hass, FB_DOMAIN, {}) is True
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


async def test_raise_config_entry_not_ready_when_offline(hass):
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
