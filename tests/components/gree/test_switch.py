"""Tests for gree component."""

from unittest.mock import MagicMock, patch

from greeclimate.exceptions import DeviceTimeoutError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gree.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID_PANEL_LIGHT = f"{SWITCH_DOMAIN}.fake_device_1_panel_light"
ENTITY_ID_HEALTH_MODE = f"{SWITCH_DOMAIN}.fake_device_1_health_mode"
ENTITY_ID_QUIET_MODE = f"{SWITCH_DOMAIN}.fake_device_1_quiet_mode"
ENTITY_ID_FRESH_AIR = f"{SWITCH_DOMAIN}.fake_device_1_fresh_air"
ENTITY_ID_XTRA_FAN = f"{SWITCH_DOMAIN}.fake_device_1_xtra_fan"


async def async_setup_gree(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the gree switch platform."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {SWITCH_DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.gree.PLATFORMS", [SWITCH_DOMAIN])
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
        ENTITY_ID_PANEL_LIGHT,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET_MODE,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XTRA_FAN,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_switch_on(hass: HomeAssistant, entity: str) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
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
        ENTITY_ID_PANEL_LIGHT,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET_MODE,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XTRA_FAN,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_switch_on_device_timeout(
    hass: HomeAssistant, device, entity: str
) -> None:
    """Test for sending power on command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
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
        ENTITY_ID_PANEL_LIGHT,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET_MODE,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XTRA_FAN,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_switch_off(hass: HomeAssistant, entity: str) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
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
        ENTITY_ID_PANEL_LIGHT,
        ENTITY_ID_HEALTH_MODE,
        ENTITY_ID_QUIET_MODE,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XTRA_FAN,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_switch_toggle(hass: HomeAssistant, entity: str) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    # Turn the service on first
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_ON

    # Toggle it off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity},
        blocking=True,
    )

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_OFF

    # Toggle is back on
    await hass.services.async_call(
        SWITCH_DOMAIN,
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

    state = hass.states.async_all(SWITCH_DOMAIN)
    assert state == snapshot


@pytest.mark.parametrize(
    ("member", "entity"),
    [
        pytest.param("light", ENTITY_ID_PANEL_LIGHT, id="light"),
        pytest.param("quiet", ENTITY_ID_QUIET_MODE, id="quiet"),
        pytest.param("fresh_air", ENTITY_ID_FRESH_AIR, id="fresh_air"),
        pytest.param("xfan", ENTITY_ID_XTRA_FAN, id="xfan"),
        pytest.param("anion", ENTITY_ID_HEALTH_MODE, id="health_mode"),
    ],
)
@pytest.mark.parametrize(
    ("restored_value", "restored_state"),
    [
        pytest.param(False, STATE_OFF, id="off"),
        pytest.param(True, STATE_ON, id="on"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_missing_switch_state(
    hass: HomeAssistant,
    device: MagicMock,
    member: str,
    entity: str,
    restored_value: bool,
    restored_state: str,
) -> None:
    """Test missing readings stay unknown until the device reports a value."""
    device().light = False
    device().quiet = False
    device().fresh_air = False
    device().xfan = False
    device().anion = False
    setattr(device(), member, None)

    entry = await async_setup_gree(hass)
    coordinator = entry.runtime_data.coordinators[0]

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    siblings = {
        ENTITY_ID_PANEL_LIGHT,
        ENTITY_ID_QUIET_MODE,
        ENTITY_ID_FRESH_AIR,
        ENTITY_ID_XTRA_FAN,
        ENTITY_ID_HEALTH_MODE,
    } - {entity}
    for sibling in siblings:
        state = hass.states.get(sibling)
        assert state is not None
        assert state.state == STATE_OFF

    setattr(device(), member, restored_value)
    coordinator.async_set_updated_data({member: restored_value})
    await hass.async_block_till_done()

    state = hass.states.get(entity)
    assert state is not None
    assert state.state == restored_state

    coordinator.async_set_update_error(UpdateFailed("Device unavailable"))
    await hass.async_block_till_done()

    for switch in siblings | {entity}:
        state = hass.states.get(switch)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
