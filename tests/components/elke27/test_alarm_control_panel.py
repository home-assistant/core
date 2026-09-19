"""Tests for Elke27 alarm control panel areas."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from elke27_lib import AreaState, ArmMode, PanelSnapshot, ZoneState
from elke27_lib.errors import Elke27PinRequiredError
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    build_snapshot,
    connection_state_changed_event,
    csm_snapshot_updated_event,
    setup_integration,
    zone_status_updated_event,
)

from tests.common import MockConfigEntry

AREA_1_ENTITY_ID = "alarm_control_panel.area_1"


async def test_area_entities_and_devices(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test area entities are created with per-area devices."""
    mock_client.get_snapshot.return_value = build_snapshot(
        areas={
            1: AreaState(area_id=1, name="Area 1"),
            2: AreaState(area_id=2, name="Area 2", arm_mode=ArmMode.ARMED_AWAY),
        }
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AREA_1_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED
    assert state.attributes["code_format"] == "number"
    assert state.attributes["supported_features"] == (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )
    state = hass.states.get("alarm_control_panel.area_2")
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    entity_entry = entity_registry.async_get(AREA_1_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == "1234:1"

    panel_device = device_registry.async_get_device({(DOMAIN, "1234")})
    assert panel_device is not None
    area_device = device_registry.async_get_device({(DOMAIN, "1234:area:1")})
    assert area_device is not None
    assert area_device.name == "Area 1"
    assert area_device.via_device_id == panel_device.id


@pytest.mark.parametrize(
    ("area", "expected_state"),
    [
        pytest.param(
            AreaState(area_id=1, name="Area 1"),
            AlarmControlPanelState.DISARMED,
            id="no-arm-mode",
        ),
        pytest.param(
            AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.DISARMED),
            AlarmControlPanelState.DISARMED,
            id="disarmed",
        ),
        pytest.param(
            AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_STAY),
            AlarmControlPanelState.ARMED_HOME,
            id="armed-stay",
        ),
        pytest.param(
            AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_NIGHT),
            AlarmControlPanelState.ARMED_NIGHT,
            id="armed-night",
        ),
        pytest.param(
            AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_AWAY),
            AlarmControlPanelState.ARMED_AWAY,
            id="armed-away",
        ),
        pytest.param(
            AreaState(area_id=1, name="Area 1", alarm_active=True),
            AlarmControlPanelState.TRIGGERED,
            id="triggered",
        ),
    ],
)
async def test_area_state_mapping(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    area: AreaState,
    expected_state: AlarmControlPanelState,
) -> None:
    """Test panel area states map to alarm control panel states."""
    mock_client.get_snapshot.return_value = build_snapshot(areas={1: area})

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AREA_1_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    "event_factory",
    [
        pytest.param(csm_snapshot_updated_event, id="csm-snapshot"),
        pytest.param(lambda _snapshot: zone_status_updated_event(1), id="zone-status"),
    ],
)
async def test_panel_events_update_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    event_factory: Callable[[PanelSnapshot], Any],
) -> None:
    """Test pushed panel events update the entity state."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(AREA_1_ENTITY_ID).state == AlarmControlPanelState.DISARMED

    snapshot = build_snapshot(
        areas={1: AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_STAY)},
        version=2,
    )
    mock_client.get_snapshot.return_value = snapshot
    mock_client.event_callback(event_factory(snapshot))
    await hass.async_block_till_done()

    assert hass.states.get(AREA_1_ENTITY_ID).state == AlarmControlPanelState.ARMED_HOME


@pytest.mark.parametrize(
    ("service", "expected_mode"),
    [
        pytest.param(SERVICE_ALARM_ARM_AWAY, ArmMode.ARMED_AWAY, id="away"),
        pytest.param(SERVICE_ALARM_ARM_HOME, ArmMode.ARMED_STAY, id="home"),
        pytest.param(SERVICE_ALARM_ARM_NIGHT, ArmMode.ARMED_NIGHT, id="night"),
    ],
)
async def test_arm_services_call_client(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_mode: ArmMode,
) -> None:
    """Test arm services send the mapped arm mode to the panel."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "1234"},
        blocking=True,
    )

    mock_client.async_arm_area.assert_awaited_once_with(
        1,
        mode=expected_mode,
        pin="1234",
        auto_stay_cancel=False,
        exit_delay_cancel=False,
    )


async def test_disarm_service_calls_client(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the disarm service sends the disarm command to the panel."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "1234"},
        blocking=True,
    )

    mock_client.async_disarm_area.assert_awaited_once_with(
        1,
        pin="1234",
        auto_stay_cancel=False,
        exit_delay_cancel=False,
    )


async def test_custom_bypass_bypasses_area_faulted_zones(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test custom bypass bypasses this area's faulted zones, then arms away."""
    mock_client.get_snapshot.return_value = build_snapshot(
        areas={1: AreaState(area_id=1, name="Area 1")},
        zones={
            1: ZoneState(
                zone_id=1, name="Front Door", area_id=1, open=True, bypassed=False
            ),
            2: ZoneState(
                zone_id=2, name="Window", area_id=2, open=True, bypassed=False
            ),
            3: ZoneState(zone_id=3, name="Garage", area_id=1, open=True, bypassed=True),
        },
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "1234"},
        blocking=True,
    )

    mock_client.async_set_zone_bypass.assert_awaited_once_with(
        1, bypassed=True, pin="1234"
    )
    mock_client.async_arm_area.assert_awaited_once_with(
        1,
        mode=ArmMode.ARMED_AWAY,
        pin="1234",
        auto_stay_cancel=False,
        exit_delay_cancel=False,
    )


async def test_custom_bypass_aborts_when_bypass_rejected(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test custom bypass stops on the first rejected zone bypass."""
    mock_client.get_snapshot.return_value = build_snapshot(
        areas={1: AreaState(area_id=1, name="Area 1")},
        zones={
            1: ZoneState(
                zone_id=1, name="Front Door", area_id=1, open=True, bypassed=False
            ),
            2: ZoneState(
                zone_id=2, name="Window", area_id=1, open=True, bypassed=False
            ),
        },
    )
    await setup_integration(hass, mock_config_entry)
    mock_client.async_set_zone_bypass.side_effect = [True, False]

    with pytest.raises(HomeAssistantError, match="Zone 2 bypass was not acknowledged."):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "1234"},
            blocking=True,
        )

    assert mock_client.async_set_zone_bypass.await_count == 2
    mock_client.async_arm_area.assert_not_awaited()


@pytest.mark.parametrize(
    ("side_effect", "return_value", "error_match"),
    [
        pytest.param(
            None, False, "Area arm command was not acknowledged", id="not-acknowledged"
        ),
        pytest.param(
            Elke27PinRequiredError(),
            None,
            "PIN required to perform this action",
            id="pin-rejected",
        ),
        pytest.param(
            None,
            SimpleNamespace(ok=False, error="bad"),
            "Area arming failed: bad",
            id="command-rejected",
        ),
    ],
)
async def test_arm_service_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception | None,
    return_value: Any,
    error_match: str,
) -> None:
    """Test failed arm commands raise Home Assistant errors."""
    await setup_integration(hass, mock_config_entry)
    mock_client.async_arm_area.side_effect = side_effect
    mock_client.async_arm_area.return_value = return_value

    with pytest.raises(HomeAssistantError, match=error_match):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "1234"},
            blocking=True,
        )


async def test_disarm_without_code_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disarming without a code fails before reaching the panel."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: AREA_1_ENTITY_ID},
            blocking=True,
        )

    mock_client.async_disarm_area.assert_not_awaited()


async def test_arm_without_code_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test arming without a code fails before reaching the panel."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: AREA_1_ENTITY_ID},
            blocking=True,
        )

    mock_client.async_arm_area.assert_not_awaited()


async def test_non_numeric_code_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a non-numeric code is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="Code must be numeric."):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: AREA_1_ENTITY_ID, ATTR_CODE: "12ab"},
            blocking=True,
        )

    mock_client.async_disarm_area.assert_not_awaited()


async def test_entities_unavailable_when_disconnected(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable on disconnect and recover on reconnect."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(AREA_1_ENTITY_ID).state == AlarmControlPanelState.DISARMED

    mock_client.is_ready = False
    mock_client.connection_callback(connection_state_changed_event(connected=False))
    await hass.async_block_till_done()

    assert hass.states.get(AREA_1_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_client.is_ready = True
    mock_client.connection_callback(connection_state_changed_event(connected=True))
    await hass.async_block_till_done()

    assert hass.states.get(AREA_1_ENTITY_ID).state == AlarmControlPanelState.DISARMED


async def test_entity_unavailable_when_area_missing(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entity becomes unavailable when its area leaves the snapshot."""
    await setup_integration(hass, mock_config_entry)

    snapshot = build_snapshot(version=2)
    mock_client.get_snapshot.return_value = snapshot
    mock_client.event_callback(csm_snapshot_updated_event(snapshot))
    await hass.async_block_till_done()

    assert hass.states.get(AREA_1_ENTITY_ID).state == STATE_UNAVAILABLE
