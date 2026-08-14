"""Tests for AVM Fritz!Box switch component."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import FritzDeviceSwitchMock, FritzTriggerMock, set_devices, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

SWITCH_ENTITY_ID = f"{SWITCH_DOMAIN}.{CONF_FAKE_NAME}"
TRIGGER_ENTITY_ID = f"{SWITCH_DOMAIN}.fake_trigger"


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform."""
    device = FritzDeviceSwitchMock()
    trigger = FritzTriggerMock()

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.SWITCH]):
        entry = await setup_config_entry(
            hass,
            MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
            device=device,
            fritz=fritz,
            trigger=trigger,
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_switch_turn_on(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn switch device on."""
    device = FritzDeviceSwitchMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], device=device, fritz=fritz
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SWITCH_ENTITY_ID}, True
    )
    assert device.set_switch_state_on.call_count == 1


async def test_switch_turn_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn switch device off."""
    device = FritzDeviceSwitchMock()

    await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], device=device, fritz=fritz
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SWITCH_ENTITY_ID}, True
    )

    assert device.set_switch_state_off.call_count == 1


async def test_switch_toggle_while_locked(hass: HomeAssistant, fritz: Mock) -> None:
    """Test toggling while switch device is locked."""
    device = FritzDeviceSwitchMock()
    device.lock = True

    await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], device=device, fritz=fritz
    )

    with pytest.raises(
        HomeAssistantError,
        match="Can't toggle switch while manual switching is disabled for the device",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SWITCH_ENTITY_ID}, True
        )

    with pytest.raises(
        HomeAssistantError,
        match="Can't toggle switch while manual switching is disabled for the device",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SWITCH_ENTITY_ID}, True
        )


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceSwitchMock()
    trigger = FritzTriggerMock()
    await setup_config_entry(
        hass,
        MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        device=device,
        fritz=fritz,
        trigger=trigger,
    )
    assert fritz().update_devices.call_count == 1
    assert fritz().update_triggers.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 2
    assert fritz().update_triggers.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceSwitchMock()
    fritz().update_devices.side_effect = ["", HTTPError("Boom"), ""]
    entry = await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], device=device, fritz=fritz
    )
    assert entry.state is ConfigEntryState.LOADED

    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=35)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 3
    assert fritz().login.call_count == 2


async def test_assume_device_unavailable(hass: HomeAssistant, fritz: Mock) -> None:
    """Test assume device as unavailable."""
    device = FritzDeviceSwitchMock()
    device.voltage = 0
    device.energy = 0
    device.power = 0
    await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], device=device, fritz=fritz
    )

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceSwitchMock()
    trigger = FritzTriggerMock()
    await setup_config_entry(
        hass,
        MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        device=device,
        fritz=fritz,
        trigger=trigger,
    )

    assert hass.states.get(SWITCH_ENTITY_ID)
    assert hass.states.get(TRIGGER_ENTITY_ID)

    # add new switch device
    new_device = FritzDeviceSwitchMock()
    new_device.ain = "7890 1234"
    new_device.name = "new_switch"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(f"{SWITCH_DOMAIN}.new_switch")

    # add new trigger
    new_trigger = FritzTriggerMock()
    new_trigger.ain = "trg7890 1234"
    new_trigger.name = "new_trigger"
    set_devices(fritz, triggers=[trigger, new_trigger])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(f"{SWITCH_DOMAIN}.new_trigger")


async def test_activate_trigger(hass: HomeAssistant, fritz: Mock) -> None:
    """Test activating a FRITZ! trigger."""
    trigger = FritzTriggerMock()
    await setup_config_entry(
        hass,
        MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        fritz=fritz,
        trigger=trigger,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TRIGGER_ENTITY_ID}, True
    )
    assert fritz().set_trigger_active.call_count == 1


async def test_deactivate_trigger(hass: HomeAssistant, fritz: Mock) -> None:
    """Test deactivating a FRITZ! trigger."""
    trigger = FritzTriggerMock()
    await setup_config_entry(
        hass,
        MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        fritz=fritz,
        trigger=trigger,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: TRIGGER_ENTITY_ID}, True
    )
    assert fritz().set_trigger_inactive.call_count == 1
