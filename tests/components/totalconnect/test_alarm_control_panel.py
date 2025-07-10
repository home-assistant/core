"""Tests for the TotalConnect alarm control panel device."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from total_connect_client import ArmingState, ArmType
from total_connect_client.exceptions import BadResultCodeError, UsercodeInvalid

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.totalconnect.alarm_control_panel import (
    SERVICE_ALARM_ARM_AWAY_INSTANT,
    SERVICE_ALARM_ARM_HOME_INSTANT,
)
from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import CODE

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "alarm_control_panel.test"
ENTITY_ID_2 = "alarm_control_panel.test_partition_2"
DATA = {ATTR_ENTITY_ID: ENTITY_ID}
DELAY = timedelta(seconds=10)

ARMING_HELPER = "homeassistant.components.totalconnect.alarm_control_panel.ArmingHelper"


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the alarm control panel attributes are correct."""
    with patch(
        "homeassistant.components.totalconnect.PLATFORMS",
        [Platform.ALARM_CONTROL_PANEL],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("code_required", [False, True])
@pytest.mark.parametrize(
    ("service", "arm_type"),
    [
        (SERVICE_ALARM_ARM_HOME, ArmType.STAY),
        (SERVICE_ALARM_ARM_NIGHT, ArmType.STAY_NIGHT),
        (SERVICE_ALARM_ARM_AWAY, ArmType.AWAY),
    ],
)
async def test_arming(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    arm_type: ArmType,
) -> None:
    """Test arming method success."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    mock_partition.arming_state = ArmingState.ARMING

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, ATTR_CODE: CODE},
        blocking=True,
    )
    assert mock_partition.arm.call_args[1] == {"arm_type": arm_type, "usercode": ""}

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING


@pytest.mark.parametrize("code_required", [True])
@pytest.mark.parametrize(
    ("service", "arm_type"),
    [
        (SERVICE_ALARM_ARM_HOME, ArmType.STAY),
        (SERVICE_ALARM_ARM_NIGHT, ArmType.STAY_NIGHT),
        (SERVICE_ALARM_ARM_AWAY, ArmType.AWAY),
    ],
)
async def test_arming_invalid_usercode(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_location: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    arm_type: ArmType,
) -> None:
    """Test arming method with invalid usercode."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert mock_location.get_panel_meta_data.call_count == 1

    mock_partition.arming_state = ArmingState.ARMING

    with pytest.raises(ServiceValidationError, match="Incorrect code entered"):
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, ATTR_CODE: "invalid_code"},
            blocking=True,
        )
    assert mock_partition.arm.call_count == 0
    assert mock_location.get_panel_meta_data.call_count == 1


@pytest.mark.parametrize("code_required", [False, True])
async def test_disarming(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disarming method success."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    mock_partition.arming_state = ArmingState.ARMING

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: entity_id, ATTR_CODE: CODE},
        blocking=True,
    )
    assert mock_partition.disarm.call_args[1] == {"usercode": ""}

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING


@pytest.mark.parametrize("code_required", [True])
async def test_disarming_invalid_usercode(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_location: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disarming method with invalid usercode."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert mock_location.get_panel_meta_data.call_count == 1

    mock_partition.arming_state = ArmingState.ARMING

    with pytest.raises(ServiceValidationError, match="Incorrect code entered"):
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: entity_id, ATTR_CODE: "invalid_code"},
            blocking=True,
        )
    assert mock_partition.disarm.call_count == 0
    assert mock_location.get_panel_meta_data.call_count == 1


@pytest.mark.parametrize(
    ("service", "arm_type"),
    [
        (SERVICE_ALARM_ARM_HOME_INSTANT, ArmType.STAY_INSTANT),
        (SERVICE_ALARM_ARM_AWAY_INSTANT, ArmType.AWAY_INSTANT),
    ],
)
async def test_instant_arming(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    arm_type: ArmType,
) -> None:
    """Test instant arming method success."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    mock_partition.arming_state = ArmingState.ARMING

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_partition.arm.call_args[1] == {"arm_type": arm_type, "usercode": ""}

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING


@pytest.mark.parametrize(
    ("exception", "suffix"),
    [(UsercodeInvalid, "invalid_code"), (BadResultCodeError, "failed")],
)
@pytest.mark.parametrize(
    ("service", "prefix"),
    [
        (SERVICE_ALARM_ARM_HOME, "arm_home"),
        (SERVICE_ALARM_ARM_NIGHT, "arm_night"),
        (SERVICE_ALARM_ARM_AWAY, "arm_away"),
    ],
)
async def test_arming_exceptions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_location: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    prefix: str,
    exception: Exception,
    suffix: str,
) -> None:
    """Test arming method exceptions."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert mock_location.get_panel_meta_data.call_count == 1

    mock_partition.arm.side_effect = exception

    mock_partition.arming_state = ArmingState.ARMING

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, ATTR_CODE: CODE},
            blocking=True,
        )
    assert mock_partition.arm.call_count == 1

    assert exc.value.translation_key == f"{prefix}_{suffix}"

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert mock_location.get_panel_meta_data.call_count == 1


# async def assert_usercode_invalid(
#     hass: HomeAssistant,
#     freezer: FrozenDateTimeFactory,
#     action,
#     result,
#     alarm_state: AlarmControlPanelState,
# ):
#     """Invalid usercode with this service should cause re-auth."""
#     domain = _pick_domain(action)
#     with (
#         patch(ARMING_HELPER, side_effect=UsercodeInvalid) as arming_mock,
#         pytest.raises(HomeAssistantError),
#     ):
#         await hass.services.async_call(domain, action, DATA, blocking=True)
#     arming_mock.assert_called_once()
#     await assert_state(hass, freezer, result, alarm_state)
#     # should have started a re-auth flow
#     assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
#
#
# async def assert_failure(
#     hass: HomeAssistant,
#     freezer: FrozenDateTimeFactory,
#     action: str,
#     result,
#     alarm_state: AlarmControlPanelState,
# ):
#     """TotalConnect failure raises HomeAssistantError."""
#     domain = _pick_domain(action)
#     with (
#         patch(ARMING_HELPER, side_effect=BadResultCodeError),
#         pytest.raises(HomeAssistantError),
#     ):
#         await hass.services.async_call(domain, action, DATA, blocking=True)
#     await assert_state(hass, freezer, result, alarm_state)
#
#
# async def assert_success(
#     hass: HomeAssistant,
#     freezer: FrozenDateTimeFactory,
#     action,
#     result,
#     alarm_state: AlarmControlPanelState,
#     data: Any = None,
# ):
#     """Assert that alarm successfully gets to the given state."""
#     domain = _pick_domain(action)
#     data = data or DATA
#     with patch(ARMING_HELPER, side_effect=None):
#         await hass.services.async_call(domain, action, data, blocking=True)
#     await assert_state(hass, freezer, result, alarm_state)
#
#
# async def test_arm_home(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test arm home method success."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # failure: usercode invalid
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # failure: can't arm for some reason
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME,
#         PANEL_STATUS_ARMED_HOME,
#         AlarmControlPanelState.ARMED_HOME,
#     )
#
#
# async def test_arm_home_instant(
#     hass: HomeAssistant, freezer: FrozenDateTimeFactory
# ) -> None:
#     """Test arm home instant."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME_INSTANT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME_INSTANT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_HOME_INSTANT,
#         PANEL_STATUS_ARMED_HOME_INSTANT,
#         AlarmControlPanelState.ARMED_HOME,
#     )
#
#
# async def test_arm_away_instant(
#     hass: HomeAssistant, freezer: FrozenDateTimeFactory
# ) -> None:
#     """Test arm home instant."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY_INSTANT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY_INSTANT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY_INSTANT,
#         PANEL_STATUS_ARMED_AWAY_INSTANT,
#         AlarmControlPanelState.ARMED_AWAY,
#     )
#
#
# async def test_arm_away(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test arm away method success."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # failure: usercode invalid
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # failure: can't arm for some reason
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY,
#         PANEL_STATUS_ARMED_AWAY,
#         AlarmControlPanelState.ARMED_AWAY,
#     )
#
#
# async def test_disarm(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test disarm method."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
#     )
#
#     # failure: usercode invalid
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_DISARM,
#         PANEL_STATUS_ARMED_AWAY,
#         AlarmControlPanelState.ARMED_AWAY,
#     )
#
#     # failure: can't arm for some reason
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_DISARM,
#         PANEL_STATUS_ARMED_AWAY,
#         AlarmControlPanelState.ARMED_AWAY,
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_DISARM,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#
# async def test_disarm_code_required(
#     hass: HomeAssistant, freezer: FrozenDateTimeFactory
# ) -> None:
#     """Test disarm with code."""
#     await setup_platform(hass, ALARM_DOMAIN, code_required=True)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
#     )
#
#     # runtime user entered code is bad
#     DATA_WITH_CODE = DATA.copy()
#     DATA_WITH_CODE["code"] = "666"
#     with pytest.raises(ServiceValidationError, match="Incorrect code entered"):
#         await hass.services.async_call(
#             ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA_WITH_CODE, blocking=True
#         )
#     await assert_state(
#         hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
#     )
#
#     # runtime user entered code that is in config
#     DATA_WITH_CODE["code"] = USERCODES[LOCATION_ID]
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_DISARM,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#         data=DATA_WITH_CODE,
#     )
#
#
# async def test_arm_night(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test arm night method."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # failure: usercode invalid
#     await assert_usercode_invalid(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_NIGHT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # failure: can't arm for some reason
#     await assert_failure(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_NIGHT,
#         PANEL_STATUS_DISARMED,
#         AlarmControlPanelState.DISARMED,
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_NIGHT,
#         PANEL_STATUS_ARMED_HOME_NIGHT,
#         AlarmControlPanelState.ARMED_NIGHT,
#     )
#
#
# async def test_arming(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test arming."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_ARM_AWAY,
#         PANEL_STATUS_ARMING,
#         AlarmControlPanelState.ARMING,
#     )
#
#
# async def test_disarming(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test disarming."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
#     )
#
#     # success
#     await assert_success(
#         hass,
#         freezer,
#         SERVICE_ALARM_DISARM,
#         PANEL_STATUS_DISARMING,
#         AlarmControlPanelState.DISARMING,
#     )
#
#
# async def test_triggered(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test triggered responses."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     # TotalConnect triggered fire --> HA triggered
#     await assert_state(
#         hass, freezer, PANEL_STATUS_TRIGGERED_FIRE, AlarmControlPanelState.TRIGGERED
#     )
#     # TotalConnect triggered police --> HA triggered
#     await assert_state(
#         hass, freezer, PANEL_STATUS_TRIGGERED_POLICE, AlarmControlPanelState.TRIGGERED
#     )
#     # TotalConnect triggered gas/carbon monoxide --> HA triggered
#     await assert_state(
#         hass, freezer, PANEL_STATUS_TRIGGERED_GAS, AlarmControlPanelState.TRIGGERED
#     )
#
#
# async def test_armed_custom(
#     hass: HomeAssistant, freezer: FrozenDateTimeFactory
# ) -> None:
#     """Test armed custom."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(
#         hass,
#         freezer,
#         PANEL_STATUS_ARMED_CUSTOM,
#         AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
#     )
#
#
# async def test_unknown(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
#     """Test unknown arm status."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     await assert_state(hass, freezer, PANEL_STATUS_UNKNOWN, STATE_UNAVAILABLE)
#
#
# async def test_other_update_failures(
#     hass: HomeAssistant, freezer: FrozenDateTimeFactory
# ) -> None:
#     """Test other failures seen during updates."""
#     await setup_platform(hass, ALARM_DOMAIN)
#     # first things work as planned
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # then an error: TotalConnect ServiceUnavailable --> HA UpdateFailed
#     freezer.tick(SCAN_INTERVAL)
#     async_fire_time_changed(hass)
#     await hass.async_block_till_done(wait_background_tasks=True)
#     assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
#
#     # works again
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # then an error: TotalConnectError --> UpdateFailed
#     freezer.tick(SCAN_INTERVAL)
#     async_fire_time_changed(hass)
#     await hass.async_block_till_done(wait_background_tasks=True)
#     assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
#
#     # works again
#     await assert_state(
#         hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
#     )
#
#     # unknown TotalConnect status via ValueError
#     freezer.tick(SCAN_INTERVAL)
#     async_fire_time_changed(hass)
#     await hass.async_block_till_done(wait_background_tasks=True)
#     assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
#
#
# async def test_authentication_error(hass: HomeAssistant) -> None:
#     """Test other failures seen during updates."""
#     entry = await setup_platform(hass, ALARM_DOMAIN)
#
#     with patch(
#         "homeassistant.components.totalconnect.TotalConnectClient.http_request",
#         side_effect=AuthenticationError,
#     ):
#         await async_update_entity(hass, ENTITY_ID)
#         await hass.async_block_till_done()
#
#     assert entry.state is ConfigEntryState.LOADED
#
#     flows = hass.config_entries.flow.async_progress()
#     assert len(flows) == 1
#
#     flow = flows[0]
#     assert flow.get("step_id") == "reauth_confirm"
#     assert flow.get("handler") == DOMAIN
#
#     assert "context" in flow
#     assert flow["context"].get("source") == SOURCE_REAUTH
#     assert flow["context"].get("entry_id") == entry.entry_id
