"""Tests for the Bond switch device."""

from datetime import timedelta

from bond_async import Action, DeviceType
import pytest

from homeassistant.components.bond.const import DOMAIN
from homeassistant.components.bond.services import (
    ATTR_POWER_STATE,
    SERVICE_SET_POWER_TRACKED_STATE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import utcnow

from .common import (
    help_test_entity_available,
    patch_bond_action,
    patch_bond_action_returns_clientresponseerror,
    patch_bond_device_state,
    setup_group_platform,
    setup_platform,
)

from tests.common import async_fire_time_changed


def generic_device(name: str):
    """Create a generic device with given name."""
    return {"name": name, "type": DeviceType.GENERIC_DEVICE}


def generic_group(name: str):
    """Create a generic group with given name."""
    return {
        "name": name,
        "types": [DeviceType.GENERIC_DEVICE],
        "locations": ["Den"],
        "actions": [Action.TURN_ON, Action.TURN_OFF],
    }


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(
        hass,
        SWITCH_DOMAIN,
        generic_device("name-1"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    entity = entity_registry.entities["switch.name_1"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_group_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that Bond groups are registered in the entity registry."""
    await setup_group_platform(
        hass,
        SWITCH_DOMAIN,
        generic_group("name-1"),
        bond_version={"bondid": "test-hub-id"},
        bond_group_id="test-group-id",
    )

    entity = entity_registry.entities["switch.name_1"]
    assert entity.unique_id == "test-hub-id_group_test-group-id"


async def test_turn_on_switch(hass: HomeAssistant) -> None:
    """Tests that turn on command delegates to API."""
    await setup_platform(
        hass, SWITCH_DOMAIN, generic_device("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_on, patch_bond_device_state():
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_on.assert_called_once_with("test-device-id", Action.turn_on())


async def test_turn_off_switch(hass: HomeAssistant) -> None:
    """Tests that turn off command delegates to API."""
    await setup_platform(
        hass, SWITCH_DOMAIN, generic_device("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once_with("test-device-id", Action.turn_off())


async def test_switch_set_power_belief(hass: HomeAssistant) -> None:
    """Tests that the set power belief service delegates to API."""
    await setup_platform(
        hass, SWITCH_DOMAIN, generic_device("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "switch.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_power_state_belief(False)
    )


async def test_switch_set_power_belief_api_error(hass: HomeAssistant) -> None:
    """Tests that the set power belief service throws HomeAssistantError in the event of an api error."""
    await setup_platform(
        hass, SWITCH_DOMAIN, generic_device("name-1"), bond_device_id="test-device-id"
    )

    with (
        pytest.raises(HomeAssistantError),
        patch_bond_action_returns_clientresponseerror(),
        patch_bond_device_state(),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "switch.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )


async def test_group_reports_unknown(hass: HomeAssistant) -> None:
    """Tests that group state is unknown when Bond reports indeterminate power."""
    await setup_group_platform(
        hass,
        SWITCH_DOMAIN,
        generic_group("name-1"),
        state={"power": None},
    )

    assert hass.states.get("switch.name_1").state == "unknown"


async def test_initial_state_defaults_off(hass: HomeAssistant) -> None:
    """Tests that a device defaults to off when Bond has no initial power state."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    assert hass.states.get("switch.name_1").state == "off"


async def test_update_reports_switch_is_on(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the device is on."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_device_state(return_value={"power": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("switch.name_1").state == "on"


async def test_update_reports_switch_is_off(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the device is off."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_device_state(return_value={"power": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("switch.name_1").state == "off"


async def test_switch_available(hass: HomeAssistant) -> None:
    """Tests that available state is updated based on API errors."""
    await help_test_entity_available(
        hass, SWITCH_DOMAIN, generic_device("name-1"), "switch.name_1"
    )
