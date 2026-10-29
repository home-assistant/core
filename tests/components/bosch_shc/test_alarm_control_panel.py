"""Tests for the bosch_shc alarm control panel platform."""

from collections.abc import Callable, Generator
from unittest.mock import ANY, MagicMock, patch

from boschshcpy import SHCIntrusionSystem
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import intrusion_system_device, setup_integration

ENTITY_ID = "alarm_control_panel.alarm_system"
NEW_ENTITY_ID = "alarm_control_panel.renamed_alarm_system"
UNIQUE_ID = "test-mac_com.bosch.tt.intrusion.system"
ArmingState = SHCIntrusionSystem.ArmingState
AlarmState = SHCIntrusionSystem.AlarmState
Profile = SHCIntrusionSystem.Profile


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the alarm control panel platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        yield


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, AlarmControlPanelState.DISARMED),
        (
            {"arming_state": ArmingState.SYSTEM_ARMING},
            AlarmControlPanelState.ARMING,
        ),
        (
            {"arming_state": ArmingState.SYSTEM_ARMED},
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.PARTIAL_PROTECTION,
            },
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.CUSTOM_PROTECTION,
            },
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.UNKNOWN,
            },
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            {"alarm_state": AlarmState.PRE_ALARM},
            AlarmControlPanelState.PENDING,
        ),
        (
            {"alarm_state": AlarmState.ALARM_ON},
            AlarmControlPanelState.TRIGGERED,
        ),
        (
            {"alarm_state": AlarmState.ALARM_MUTED},
            AlarmControlPanelState.TRIGGERED,
        ),
    ],
)
async def test_alarm_state(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    kwargs: dict,
    expected: AlarmControlPanelState,
) -> None:
    """The SHC arming, alarm and profile state map to the panel state."""
    mock_session.intrusion_system = intrusion_system_device(**kwargs)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_ALARM_DISARM, "disarm"),
        (SERVICE_ALARM_ARM_AWAY, "arm_full_protection"),
        (SERVICE_ALARM_ARM_HOME, "arm_partial_protection"),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, "arm_individual_protection"),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Each alarm service calls the matching SHC command."""
    device = intrusion_system_device()
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(device, method).assert_called_once_with()


async def test_unavailable(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The panel is unavailable when the system reports unavailable."""
    device = intrusion_system_device()
    device.system_availability = False
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == "unavailable"


async def test_push_update(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A pushed SHC state change updates the panel state."""
    device = intrusion_system_device()
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED

    device.alarm_state = AlarmState.ALARM_ON
    device.subscribe_callback.call_args.args[1]()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.TRIGGERED


@pytest.mark.parametrize(
    "remove_entity",
    [
        pytest.param(
            lambda entity_registry: entity_registry.async_remove(NEW_ENTITY_ID),
            id="remove",
        ),
        pytest.param(
            lambda entity_registry: entity_registry.async_update_entity(
                NEW_ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
            ),
            id="disable",
        ),
    ],
)
async def test_entity_id_change_in_place(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    remove_entity: Callable[[er.EntityRegistry], object],
) -> None:
    """The SHC subscription survives an entity_id change and is released on removal."""
    device = intrusion_system_device()
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity(ENTITY_ID, new_entity_id=NEW_ENTITY_ID)
    await hass.async_block_till_done()

    # Renamed in place, not removed and re-added.
    device.subscribe_callback.assert_called_once_with(UNIQUE_ID, ANY)
    device.unsubscribe_callback.assert_not_called()

    device.alarm_state = AlarmState.ALARM_ON
    device.subscribe_callback.call_args.args[1]()
    await hass.async_block_till_done()
    assert hass.states.get(NEW_ENTITY_ID).state == AlarmControlPanelState.TRIGGERED

    remove_entity(entity_registry)
    await hass.async_block_till_done()

    assert hass.states.get(NEW_ENTITY_ID) is None
    device.unsubscribe_callback.assert_called_once_with(UNIQUE_ID)
