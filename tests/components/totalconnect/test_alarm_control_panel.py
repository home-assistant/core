"""Tests for the TotalConnect alarm control panel device."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests_mock
from syrupy import SnapshotAssertion
from total_connect_client.exceptions import (
    AuthenticationError,
    BadResultCodeError,
    UsercodeInvalid,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.totalconnect.alarm_control_panel import (
    SERVICE_ALARM_ARM_AWAY_INSTANT,
    SERVICE_ALARM_ARM_HOME_INSTANT,
)
from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.components.totalconnect.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .common import (
    ENDPOINT_FULL_STATUS,
    LOCATION_ID,
    PANEL_STATUS_ARMED_AWAY,
    PANEL_STATUS_ARMED_AWAY_INSTANT,
    PANEL_STATUS_ARMED_CUSTOM,
    PANEL_STATUS_ARMED_HOME,
    PANEL_STATUS_ARMED_HOME_INSTANT,
    PANEL_STATUS_ARMED_HOME_NIGHT,
    PANEL_STATUS_ARMING,
    PANEL_STATUS_DISARMED,
    PANEL_STATUS_DISARMING,
    PANEL_STATUS_TRIGGERED_FIRE,
    PANEL_STATUS_TRIGGERED_GAS,
    PANEL_STATUS_TRIGGERED_POLICE,
    PANEL_STATUS_UNKNOWN,
    TOTALCONNECT_REQUEST,
    USERCODES,
    setup_platform,
)

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = "alarm_control_panel.test"
ENTITY_ID_2 = "alarm_control_panel.test_partition_2"
CODE = "-1"
DATA = {ATTR_ENTITY_ID: ENTITY_ID}
DELAY = timedelta(seconds=10)

ARMING_HELPER = "homeassistant.components.totalconnect.alarm_control_panel.ArmingHelper"


async def test_attributes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the alarm control panel attributes are correct."""
    entry = await setup_platform(hass, ALARM_DOMAIN)
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            ENDPOINT_FULL_STATUS,
            json=PANEL_STATUS_DISARMED,
        )

        await async_update_entity(hass, ENTITY_ID)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def assert_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    result,
    alarm_state: AlarmControlPanelState,
):
    """Assert the alarm is in the given state."""
    with requests_mock.Mocker() as mock_request:
        mock_request.get(ENDPOINT_FULL_STATUS, json=result)
        freezer.tick(DELAY)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == alarm_state


async def assert_usercode_invalid(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    action,
    result,
    alarm_state: AlarmControlPanelState,
):
    """Invalid usercode with this service should cause re-auth."""
    with (
        patch(ARMING_HELPER, side_effect=UsercodeInvalid),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(ALARM_DOMAIN, action, DATA, blocking=True)
    await assert_state(hass, freezer, result, alarm_state)
    # should have started a re-auth flow
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def assert_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    action,
    result,
    alarm_state: AlarmControlPanelState,
):
    """TotalConnect failure raises HomeAssistantError."""
    with (
        patch(ARMING_HELPER, side_effect=BadResultCodeError),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(ALARM_DOMAIN, action, DATA, blocking=True)
    await assert_state(hass, freezer, result, alarm_state)


async def assert_success(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    action,
    result,
    alarm_state: AlarmControlPanelState,
    data: Any = None,
):
    """Assert that alarm successfully gets to the given state."""
    data = data or DATA
    with patch(ARMING_HELPER, side_effect=None):
        await hass.services.async_call(ALARM_DOMAIN, action, data, blocking=True)
    await assert_state(hass, freezer, result, alarm_state)


async def test_arm_home(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test arm home method success."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # failure: usercode invalid
    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # failure: can't arm for some reason
    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME,
        PANEL_STATUS_ARMED_HOME,
        AlarmControlPanelState.ARMED_HOME,
    )


async def test_arm_home_instant(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test arm home instant."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME_INSTANT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME_INSTANT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_HOME_INSTANT,
        PANEL_STATUS_ARMED_HOME_INSTANT,
        AlarmControlPanelState.ARMED_HOME,
    )


async def test_arm_away_instant(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test arm home instant."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY_INSTANT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY_INSTANT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY_INSTANT,
        PANEL_STATUS_ARMED_AWAY_INSTANT,
        AlarmControlPanelState.ARMED_AWAY,
    )


async def test_arm_away(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test arm away method success."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # failure: usercode invalid
    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # failure: can't arm for some reason
    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY,
        PANEL_STATUS_ARMED_AWAY,
        AlarmControlPanelState.ARMED_AWAY,
    )


async def test_disarm(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test disarm method."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
    )

    # failure: usercode invalid
    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_DISARM,
        PANEL_STATUS_ARMED_AWAY,
        AlarmControlPanelState.ARMED_AWAY,
    )

    # failure: can't arm for some reason
    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_DISARM,
        PANEL_STATUS_ARMED_AWAY,
        AlarmControlPanelState.ARMED_AWAY,
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_DISARM,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )


async def test_disarm_code_required(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test disarm with code."""
    await setup_platform(hass, ALARM_DOMAIN, code_required=True)
    await assert_state(
        hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
    )

    # runtime user entered code is bad
    DATA_WITH_CODE = DATA.copy()
    DATA_WITH_CODE["code"] = "666"
    with pytest.raises(ServiceValidationError, match="Incorrect code entered"):
        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA_WITH_CODE, blocking=True
        )
    await assert_state(
        hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
    )

    # runtime user entered code that is in config
    DATA_WITH_CODE["code"] = USERCODES[LOCATION_ID]
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_DISARM,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
        data=DATA_WITH_CODE,
    )


async def test_arm_night(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test arm night method."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # failure: usercode invalid
    await assert_usercode_invalid(
        hass,
        freezer,
        SERVICE_ALARM_ARM_NIGHT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # failure: can't arm for some reason
    await assert_failure(
        hass,
        freezer,
        SERVICE_ALARM_ARM_NIGHT,
        PANEL_STATUS_DISARMED,
        AlarmControlPanelState.DISARMED,
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_NIGHT,
        PANEL_STATUS_ARMED_HOME_NIGHT,
        AlarmControlPanelState.ARMED_NIGHT,
    )


async def test_arming(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test arming."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_ARM_AWAY,
        PANEL_STATUS_ARMING,
        AlarmControlPanelState.ARMING,
    )


async def test_disarming(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test disarming."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass, freezer, PANEL_STATUS_ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY
    )

    # success
    await assert_success(
        hass,
        freezer,
        SERVICE_ALARM_DISARM,
        PANEL_STATUS_DISARMING,
        AlarmControlPanelState.DISARMING,
    )


async def test_triggered(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test triggered responses."""
    await setup_platform(hass, ALARM_DOMAIN)
    # TotalConnect triggered fire --> HA triggered
    await assert_state(
        hass, freezer, PANEL_STATUS_TRIGGERED_FIRE, AlarmControlPanelState.TRIGGERED
    )
    # TotalConnect triggered police --> HA triggered
    await assert_state(
        hass, freezer, PANEL_STATUS_TRIGGERED_POLICE, AlarmControlPanelState.TRIGGERED
    )
    # TotalConnect triggered gas/carbon monoxide --> HA triggered
    await assert_state(
        hass, freezer, PANEL_STATUS_TRIGGERED_GAS, AlarmControlPanelState.TRIGGERED
    )


async def test_armed_custom(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test armed custom."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(
        hass,
        freezer,
        PANEL_STATUS_ARMED_CUSTOM,
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    )


async def test_unknown(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test unknown arm status."""
    await setup_platform(hass, ALARM_DOMAIN)
    await assert_state(hass, freezer, PANEL_STATUS_UNKNOWN, STATE_UNAVAILABLE)


async def test_other_update_failures(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test other failures seen during updates."""
    await setup_platform(hass, ALARM_DOMAIN)
    # first things work as planned
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # then an error: TotalConnect ServiceUnavailable --> HA UpdateFailed
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # works again
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # then an error: TotalConnectError --> UpdateFailed
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # works again
    await assert_state(
        hass, freezer, PANEL_STATUS_DISARMED, AlarmControlPanelState.DISARMED
    )

    # unknown TotalConnect status via ValueError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_authentication_error(hass: HomeAssistant) -> None:
    """Test other failures seen during updates."""
    entry = await setup_platform(hass, ALARM_DOMAIN)

    with patch(TOTALCONNECT_REQUEST, side_effect=AuthenticationError):
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
