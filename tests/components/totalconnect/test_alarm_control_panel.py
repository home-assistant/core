"""Tests for the TotalConnect alarm control panel device."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
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

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

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
    ("exception", "suffix", "flows"),
    [(UsercodeInvalid, "invalid_code", 1), (BadResultCodeError, "failed", 0)],
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
    flows: int,
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

    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == flows


@pytest.mark.parametrize(
    ("exception", "suffix", "flows"),
    [(UsercodeInvalid, "invalid_code", 1), (BadResultCodeError, "failed", 0)],
)
@pytest.mark.parametrize(
    ("service", "prefix"),
    [
        (SERVICE_ALARM_ARM_HOME_INSTANT, "arm_home_instant"),
        (SERVICE_ALARM_ARM_AWAY_INSTANT, "arm_away_instant"),
    ],
)
async def test_instant_arming_exceptions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_location: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    prefix: str,
    exception: Exception,
    suffix: str,
    flows: int,
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
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert mock_partition.arm.call_count == 1

    assert exc.value.translation_key == f"{prefix}_{suffix}"

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert mock_location.get_panel_meta_data.call_count == 1

    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == flows


@pytest.mark.parametrize(
    ("arming_state", "state"),
    [
        (ArmingState.DISARMED, AlarmControlPanelState.DISARMED),
        (ArmingState.DISARMED_BYPASS, AlarmControlPanelState.DISARMED),
        (ArmingState.DISARMED_ZONE_FAULTED, AlarmControlPanelState.DISARMED),
        (ArmingState.ARMED_STAY_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (ArmingState.ARMED_STAY_NIGHT_BYPASS_PROA7, AlarmControlPanelState.ARMED_NIGHT),
        (
            ArmingState.ARMED_STAY_NIGHT_INSTANT_PROA7,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (
            ArmingState.ARMED_STAY_NIGHT_INSTANT_BYPASS_PROA7,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (ArmingState.ARMED_STAY, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_PROA7, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_BYPASS, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_BYPASS_PROA7, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_INSTANT, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_INSTANT_PROA7, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_STAY_INSTANT_BYPASS, AlarmControlPanelState.ARMED_HOME),
        (
            ArmingState.ARMED_STAY_INSTANT_BYPASS_PROA7,
            AlarmControlPanelState.ARMED_HOME,
        ),
        (ArmingState.ARMED_STAY_OTHER, AlarmControlPanelState.ARMED_HOME),
        (ArmingState.ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (ArmingState.ARMED_AWAY_BYPASS, AlarmControlPanelState.ARMED_AWAY),
        (ArmingState.ARMED_AWAY_INSTANT, AlarmControlPanelState.ARMED_AWAY),
        (ArmingState.ARMED_AWAY_INSTANT_BYPASS, AlarmControlPanelState.ARMED_AWAY),
        (ArmingState.ARMED_CUSTOM_BYPASS, AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        (ArmingState.ARMING, AlarmControlPanelState.ARMING),
        (ArmingState.DISARMING, AlarmControlPanelState.DISARMING),
        (ArmingState.ALARMING, AlarmControlPanelState.TRIGGERED),
        (ArmingState.ALARMING_FIRE_SMOKE, AlarmControlPanelState.TRIGGERED),
        (ArmingState.ALARMING_CARBON_MONOXIDE, AlarmControlPanelState.TRIGGERED),
        (ArmingState.ALARMING_CARBON_MONOXIDE_PROA7, AlarmControlPanelState.TRIGGERED),
    ],
)
async def test_arming_state(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_partition: AsyncMock,
    mock_location: AsyncMock,
    mock_config_entry: MockConfigEntry,
    arming_state: ArmingState,
    state: AlarmControlPanelState,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test arming state transitions."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "alarm_control_panel.test"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    mock_partition.arming_state = arming_state

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == state
