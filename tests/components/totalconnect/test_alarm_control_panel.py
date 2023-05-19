"""Tests for the TotalConnect alarm control panel device."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from total_connect_client.exceptions import ServiceUnavailable, TotalConnectError

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.totalconnect import DOMAIN, SCAN_INTERVAL
from homeassistant.components.totalconnect.alarm_control_panel import (
    SERVICE_ALARM_ARM_AWAY_INSTANT,
    SERVICE_ALARM_ARM_HOME_INSTANT,
    SERVICE_BYPASS_ZONE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt

from .common import (
    LOCATION_ID,
    RESPONSE_ARM_FAILURE,
    RESPONSE_ARM_SUCCESS,
    RESPONSE_ARMED_AWAY,
    RESPONSE_ARMED_CUSTOM,
    RESPONSE_ARMED_NIGHT,
    RESPONSE_ARMED_STAY,
    RESPONSE_ARMING,
    RESPONSE_BYPASS_FAILED,
    RESPONSE_DISARM_FAILURE,
    RESPONSE_DISARM_SUCCESS,
    RESPONSE_DISARMED,
    RESPONSE_DISARMING,
    RESPONSE_SUCCESS,
    RESPONSE_TRIGGERED_CARBON_MONOXIDE,
    RESPONSE_TRIGGERED_FIRE,
    RESPONSE_TRIGGERED_POLICE,
    RESPONSE_UNKNOWN,
    RESPONSE_USER_CODE_INVALID,
    TOTALCONNECT_REQUEST,
    setup_platform,
)

from tests.common import async_fire_time_changed

ENTITY_ID = "alarm_control_panel.test"
ENTITY_ID_2 = "alarm_control_panel.test_partition_2"
CODE = "-1"
DATA = {ATTR_ENTITY_ID: ENTITY_ID}
DELAY = timedelta(seconds=10)


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the alarm control panel attributes are correct."""
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.request",
        return_value=RESPONSE_DISARMED,
    ) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ALARM_DISARMED
        mock_request.assert_called_once()
        assert state.attributes.get(ATTR_FRIENDLY_NAME) == "test"

        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(ENTITY_ID)
        # TotalConnect partition #1 alarm device unique_id is the location_id
        assert entry.unique_id == LOCATION_ID

        entry2 = entity_registry.async_get(ENTITY_ID_2)
        # TotalConnect partition #2 unique_id is the location_id + "_{partition_number}"
        assert entry2.unique_id == LOCATION_ID + "_2"
        assert mock_request.call_count == 1


async def test_arm_home_success(hass: HomeAssistant) -> None:
    """Test arm home method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_STAY]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert hass.states.get(ENTITY_ID_2).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_HOME
        # second partition should not be armed
        assert hass.states.get(ENTITY_ID_2).state == STATE_ALARM_DISARMED


async def test_arm_home_failure(hass: HomeAssistant) -> None:
    """Test arm home method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_USER_CODE_INVALID]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm home test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect usercode is invalid. Did not arm home"
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_arm_home_instant_success(hass: HomeAssistant) -> None:
    """Test arm home instant method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_STAY]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert hass.states.get(ENTITY_ID_2).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            DOMAIN, SERVICE_ALARM_ARM_HOME_INSTANT, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_HOME


async def test_arm_home_instant_failure(hass: HomeAssistant) -> None:
    """Test arm home instant method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_USER_CODE_INVALID]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_ALARM_ARM_HOME_INSTANT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm home instant test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_ALARM_ARM_HOME_INSTANT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert (
            f"{err.value}"
            == "TotalConnect usercode is invalid. Did not arm home instant"
        )
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_arm_away_instant_success(hass: HomeAssistant) -> None:
    """Test arm home instant method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_AWAY]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert hass.states.get(ENTITY_ID_2).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            DOMAIN, SERVICE_ALARM_ARM_AWAY_INSTANT, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY


async def test_arm_away_instant_failure(hass: HomeAssistant) -> None:
    """Test arm home instant method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_USER_CODE_INVALID]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_ALARM_ARM_AWAY_INSTANT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm away instant test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_ALARM_ARM_AWAY_INSTANT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert (
            f"{err.value}"
            == "TotalConnect usercode is invalid. Did not arm away instant"
        )
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_arm_away_success(hass: HomeAssistant) -> None:
    """Test arm away method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_AWAY]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_AWAY, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY


async def test_arm_away_failure(hass: HomeAssistant) -> None:
    """Test arm away method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_USER_CODE_INVALID]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_AWAY, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm away test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_AWAY, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect usercode is invalid. Did not arm away"
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_disarm_success(hass: HomeAssistant) -> None:
    """Test disarm method success."""
    responses = [RESPONSE_ARMED_AWAY, RESPONSE_DISARM_SUCCESS, RESPONSE_DISARMED]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED


async def test_disarm_failure(hass: HomeAssistant) -> None:
    """Test disarm method failure."""
    responses = [
        RESPONSE_ARMED_AWAY,
        RESPONSE_DISARM_FAILURE,
        RESPONSE_USER_CODE_INVALID,
    ]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to disarm test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect usercode is invalid. Did not disarm"
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_arm_night_success(hass: HomeAssistant) -> None:
    """Test arm night method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_NIGHT]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_NIGHT, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_NIGHT


async def test_arm_night_failure(hass: HomeAssistant) -> None:
    """Test arm night method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_USER_CODE_INVALID]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_NIGHT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm night test."
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 2

        # usercode is invalid
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_NIGHT, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect usercode is invalid. Did not arm night"
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        # should have started a re-auth flow
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert mock_request.call_count == 3


async def test_arming(hass: HomeAssistant) -> None:
    """Test arming."""
    responses = [RESPONSE_DISARMED, RESPONSE_SUCCESS, RESPONSE_ARMING]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_NIGHT, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMING


async def test_disarming(hass: HomeAssistant) -> None:
    """Test disarming."""
    responses = [RESPONSE_ARMED_AWAY, RESPONSE_SUCCESS, RESPONSE_DISARMING]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_AWAY
        assert mock_request.call_count == 1

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
        )
        assert mock_request.call_count == 2

        async_fire_time_changed(hass, dt.utcnow() + DELAY)
        await hass.async_block_till_done()
        assert mock_request.call_count == 3
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMING


async def test_triggered_fire(hass: HomeAssistant) -> None:
    """Test triggered by fire."""
    responses = [RESPONSE_TRIGGERED_FIRE]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ALARM_TRIGGERED
        assert state.attributes.get("triggered_source") == "Fire/Smoke"
        assert mock_request.call_count == 1


async def test_triggered_police(hass: HomeAssistant) -> None:
    """Test triggered by police."""
    responses = [RESPONSE_TRIGGERED_POLICE]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ALARM_TRIGGERED
        assert state.attributes.get("triggered_source") == "Police/Medical"
        assert mock_request.call_count == 1


async def test_triggered_carbon_monoxide(hass: HomeAssistant) -> None:
    """Test triggered by carbon monoxide."""
    responses = [RESPONSE_TRIGGERED_CARBON_MONOXIDE]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ALARM_TRIGGERED
        assert state.attributes.get("triggered_source") == "Carbon Monoxide"
        assert mock_request.call_count == 1


async def test_armed_custom(hass: HomeAssistant) -> None:
    """Test armed custom."""
    responses = [RESPONSE_ARMED_CUSTOM]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_ARMED_CUSTOM_BYPASS
        assert mock_request.call_count == 1


async def test_unknown(hass: HomeAssistant) -> None:
    """Test unknown arm status."""
    responses = [RESPONSE_UNKNOWN]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
        assert mock_request.call_count == 1


async def test_other_update_failures(hass: HomeAssistant) -> None:
    """Test other failures seen during updates."""
    responses = [
        RESPONSE_DISARMED,
        ServiceUnavailable,
        RESPONSE_DISARMED,
        TotalConnectError,
        RESPONSE_DISARMED,
        ValueError,
    ]
    await setup_platform(hass, ALARM_DOMAIN)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        # first things work as planned
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 1

        # then an error: ServiceUnavailable --> UpdateFailed
        async_fire_time_changed(hass, dt.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
        assert mock_request.call_count == 2

        # works again
        async_fire_time_changed(hass, dt.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 3

        # then an error: TotalConnectError --> UpdateFailed
        async_fire_time_changed(hass, dt.utcnow() + SCAN_INTERVAL * 3)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
        assert mock_request.call_count == 4

        # works again
        async_fire_time_changed(hass, dt.utcnow() + SCAN_INTERVAL * 4)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert mock_request.call_count == 5

        # unknown TotalConnect status via ValueError
        async_fire_time_changed(hass, dt.utcnow() + SCAN_INTERVAL * 5)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
        assert mock_request.call_count == 6


async def test_bypass_zone(hass: HomeAssistant) -> None:
    """Test bypass_zone service."""
    responses = [
        RESPONSE_DISARMED,
        RESPONSE_SUCCESS,
        RESPONSE_BYPASS_FAILED,
        RESPONSE_USER_CODE_INVALID,
    ]
    # ZONE_ENTITY = "binary_sensor.security"
    SERVICE_DATA_1 = {ATTR_ENTITY_ID: ENTITY_ID, "zone_id": 1}
    SERVICE_DATA_2 = {ATTR_ENTITY_ID: ENTITY_ID, "zone_id": 2}
    SERVICE_DATA_4 = {ATTR_ENTITY_ID: ENTITY_ID, "zone_id": 4}
    SERVICE_DATA_88 = {ATTR_ENTITY_ID: ENTITY_ID, "zone_id": 88}

    mock_entry = await setup_platform(hass, ALARM_DOMAIN)
    location = hass.data[DOMAIN][mock_entry.entry_id].client.locations[LOCATION_ID]

    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        # panel with basic config, zones not bypassed
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_ALARM_DISARMED
        assert location.zones[2].is_bypassed() is False
        assert mock_request.call_count == 1

        # attempt to bypass zone 1 security
        assert location.zones[1].is_bypassed() is False
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_1, blocking=True
        )
        await hass.async_block_till_done()
        assert location.zones[1].is_bypassed() is True
        assert mock_request.call_count == 2

        # attempt to bypass zone 1 security after already bypassed
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_1, blocking=True
        )
        await hass.async_block_till_done()
        assert location.zones[1].is_bypassed() is True
        assert mock_request.call_count == 2

        # attempt to bypass zone 2 fire, but it cannot be bypassed
        assert location.zones[2].is_bypassed() is False
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_2, blocking=True
        )
        await hass.async_block_till_done()
        assert location.zones[2].is_bypassed() is False
        assert mock_request.call_count == 2

        # attempt to bypass zone 4 motion, but fails for some reason
        assert location.zones[4].is_bypassed() is False
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_4, blocking=True
            )
            await hass.async_block_till_done()
            assert f"{err.value}" == "TotalConnect failed to bypass zone 4."
        assert location.zones[4].is_bypassed() is False
        assert mock_request.call_count == 3

        # attempt to bypass zone 4 motion, but usercode is invalid
        assert location.zones[4].is_bypassed() is False
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_4, blocking=True
            )
            await hass.async_block_till_done()
            assert (
                f"{err.value}"
                == "TotalConnect usercode is invalid. Did not bypass zone."
            )
        assert location.zones[4].is_bypassed() is False
        assert mock_request.call_count == 4

        # attempt to bypass zone 88 motion which does not exist, do nothing
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_ZONE, SERVICE_DATA_88, blocking=True
        )
        await hass.async_block_till_done()
        assert mock_request.call_count == 4
