"""Tests for the AVM Fritz!Box integration."""
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG, FritzDeviceSwitchMock

from tests.async_mock import Mock, call
from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistantType, fritz: Mock):
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


async def test_setup_duplicate_config(hass: HomeAssistantType, fritz: Mock, caplog):
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


async def test_unload(hass: HomeAssistantType, fritz: Mock):
    """Test unload of integration."""
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
    assert state is None
