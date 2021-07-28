"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from unittest.mock import Mock, call, patch

from pyfritzhome import LoginError
from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FritzDeviceSwitchMock, setup_config_entry
from .const import CONF_FAKE_AIN, CONF_FAKE_NAME, MOCK_CONFIG

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


async def test_update_unique_id(hass: HomeAssistant, fritz: Mock):
    """Test unique_id update of integration."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        FB_DOMAIN,
        CONF_FAKE_AIN,
        unit_of_measurement=TEMP_CELSIUS,
        config_entry=entry,
    )
    assert entity.unique_id == CONF_FAKE_AIN
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{CONF_FAKE_AIN}_temperature"


async def test_update_unique_id_no_change(hass: HomeAssistant, fritz: Mock):
    """Test unique_id is not updated of integration."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        FB_DOMAIN,
        f"{CONF_FAKE_AIN}_temperature",
        unit_of_measurement=TEMP_CELSIUS,
        config_entry=entry,
    )
    assert entity.unique_id == f"{CONF_FAKE_AIN}_temperature"
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{CONF_FAKE_AIN}_temperature"


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
    entity_id = f"{SWITCH_DOMAIN}.{CONF_FAKE_NAME}"

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

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state

    await hass.config_entries.async_unload(entry.entry_id)

    assert fritz().logout.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert fritz().logout.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(entity_id)
    assert state is None


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant):
    """Config entry state is SETUP_RETRY when fritzbox is offline."""
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
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
