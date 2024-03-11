"""Tests for gree component."""

from unittest.mock import patch

from greeclimate.exceptions import DeviceTimeoutError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID_LIGHT_PANEL = f"{DOMAIN}.fake_device_1_panel_light"
ENTITY_ID_HEALTH_MODE = f"{DOMAIN}.fake_device_1_health_mode"
ENTITY_ID_QUIET = f"{DOMAIN}.fake_device_1_quiet"
ENTITY_ID_FRESH_AIR = f"{DOMAIN}.fake_device_1_fresh_air"
ENTITY_ID_XFAN = f"{DOMAIN}.fake_device_1_xfan"


async def async_setup_gree(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the gree switch platform."""
    entry = MockConfigEntry(domain=GREE_DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, GREE_DOMAIN, {GREE_DOMAIN: {DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.gree.PLATFORMS", [DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for entity registry settings (disabled_by, unique_id)."""
    entry = await async_setup_gree(hass)

    state = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert state == snapshot


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_LIGHT_PANEL,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XFAN,
    ],
)
async def test_send_switch_on(
    hass: HomeAssistant, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_LIGHT_PANEL,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XFAN,
    ],
)
async def test_send_switch_on_device_timeout(
    hass: HomeAssistant, device, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_LIGHT_PANEL,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XFAN,
    ],
)
async def test_send_switch_off(
    hass: HomeAssistant, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_LIGHT_PANEL,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XFAN,
    ],
)
async def test_send_switch_toggle(
    hass: HomeAssistant, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    # Turn the service on first
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_ON

    # Toggle it off
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_OFF

    # Toggle is back on
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for entity registry settings (disabled_by, unique_id)."""
    await async_setup_gree(hass)

    state = hass.states.async_all(DOMAIN)
    assert state == snapshot
