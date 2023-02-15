"""The tests for the manual Alarm Control Panel component."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.demo import alarm_control_panel as demo
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_component, mock_restore_cache
from tests.components.alarm_control_panel import common

CODE = "HELLO_CODE"


async def test_setup_demo_platform(hass: HomeAssistant) -> None:
    """Test setup."""
    mock = MagicMock()
    add_entities = mock.MagicMock()
    await demo.async_setup_platform(hass, {}, add_entities)
    assert add_entities.call_count == 1


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_no_pending(hass: HomeAssistant, service, expected_state) -> None:
    """Test no pending after arming."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_no_pending_when_code_not_req(
    hass: HomeAssistant, service, expected_state
) -> None:
    """Test no pending when code not required."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "code_arm_required": False,
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_with_pending(hass: HomeAssistant, service, expected_state) -> None:
    """Test with pending after arming."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "arming_time": 1,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMING

    state = hass.states.get(entity_id)
    assert state.attributes["next_state"] == expected_state

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == expected_state

    # Do not go to the pending state when updating to the same state
    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_with_invalid_code(hass: HomeAssistant, service, expected_state) -> None:
    """Attempt to arm without a valid code."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "arming_time": 1,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE + "2"},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_with_template_code(hass: HomeAssistant, service, expected_state) -> None:
    """Attempt to arm with a template-based code."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code_template": '{{ "abc" }}',
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: "abc"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_with_specific_pending(
    hass: HomeAssistant, service, expected_state
) -> None:
    """Test arming with specific pending."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 10,
                expected_state: {"arming_time": 2},
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test"},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMING

    future = dt_util.utcnow() + timedelta(seconds=2)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == expected_state


async def test_trigger_no_pending(hass: HomeAssistant) -> None:
    """Test triggering when no pending submitted method."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 1,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    future = dt_util.utcnow() + timedelta(seconds=60)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_with_delay(hass: HomeAssistant) -> None:
    """Test trigger method and switch from pending to triggered."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "delay_time": 1,
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_zero_trigger_time(hass: HomeAssistant) -> None:
    """Test disabled trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 0,
                "trigger_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_zero_trigger_time_with_pending(hass: HomeAssistant) -> None:
    """Test disabled trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 2,
                "trigger_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_pending(hass: HomeAssistant) -> None:
    """Test arm home method."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "delay_time": 2,
                "trigger_time": 3,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    state = hass.states.get(entity_id)
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=2)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_DISARMED


async def test_trigger_with_unused_specific_delay(hass: HomeAssistant) -> None:
    """Test trigger method and switch from pending to triggered."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "delay_time": 5,
                "arming_time": 0,
                "armed_home": {"delay_time": 10},
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_with_specific_delay(hass: HomeAssistant) -> None:
    """Test trigger method and switch from pending to triggered."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "delay_time": 10,
                "arming_time": 0,
                "armed_away": {"delay_time": 1},
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_with_pending_and_delay(hass: HomeAssistant) -> None:
    """Test trigger method and switch from pending to triggered."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "delay_time": 2,
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future += timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_with_pending_and_specific_delay(hass: HomeAssistant) -> None:
    """Test trigger method and switch from pending to triggered."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "delay_time": 10,
                "arming_time": 0,
                "armed_away": {"delay_time": 2},
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_PENDING
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future += timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


async def test_trigger_with_specific_pending(hass: HomeAssistant) -> None:
    """Test arm home method."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "delay_time": 10,
                "disarmed": {"delay_time": 2},
                "trigger_time": 3,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    future = dt_util.utcnow() + timedelta(seconds=2)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_disarm_after_trigger(hass: HomeAssistant) -> None:
    """Test disarm after trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "delay_time": 0,
                "disarm_after_trigger": True,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_zero_specific_trigger_time(hass: HomeAssistant) -> None:
    """Test trigger method."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "disarmed": {"trigger_time": 0},
                "arming_time": 0,
                "disarm_after_trigger": True,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_unused_zero_specific_trigger_time(
    hass: HomeAssistant,
) -> None:
    """Test disarm after trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "armed_home": {"trigger_time": 0},
                "delay_time": 0,
                "disarm_after_trigger": True,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_specific_trigger_time(hass: HomeAssistant) -> None:
    """Test disarm after trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "disarmed": {"trigger_time": 5},
                "delay_time": 0,
                "disarm_after_trigger": True,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_trigger_with_no_disarm_after_trigger(hass: HomeAssistant) -> None:
    """Test disarm after trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "arming_time": 0,
                "delay_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE, entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY


async def test_back_to_back_trigger_with_no_disarm_after_trigger(
    hass: HomeAssistant,
) -> None:
    """Test disarm after trigger."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "arming_time": 0,
                "delay_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE, entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY


async def test_disarm_while_pending_trigger(hass: HomeAssistant) -> None:
    """Test disarming while pending state."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "trigger_time": 5,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    await common.async_alarm_disarm(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED


async def test_disarm_during_trigger_with_invalid_code(hass: HomeAssistant) -> None:
    """Test disarming while code is invalid."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "delay_time": 5,
                "code": "12345",
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED
    assert (
        hass.states.get(entity_id).attributes[alarm_control_panel.ATTR_CODE_FORMAT]
        == alarm_control_panel.CodeFormat.NUMBER
    )

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    await common.async_alarm_disarm(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == STATE_ALARM_PENDING

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.state == STATE_ALARM_TRIGGERED


async def test_disarm_with_template_code(hass: HomeAssistant) -> None:
    """Attempt to disarm with a valid or invalid template-based code."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code_template": '{{ "" if from_state == "disarmed" else "abc" }}',
                "arming_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_home(hass, "def")

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_ARMED_HOME

    await common.async_alarm_disarm(hass, "def")

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_ARMED_HOME

    await common.async_alarm_disarm(hass, "abc")

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_DISARMED


async def test_arm_away_after_disabled_disarmed(hass: HomeAssistant) -> None:
    """Test pending state with and without zero trigger time."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "code": CODE,
                "arming_time": 0,
                "delay_time": 1,
                "armed_away": {"arming_time": 1},
                "disarmed": {"trigger_time": 0},
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_ARMING
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.attributes["next_state"] == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_ARMING
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.attributes["next_state"] == STATE_ALARM_ARMED_AWAY

    future = dt_util.utcnow() + timedelta(seconds=1)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ALARM_ARMED_AWAY

        await common.async_alarm_trigger(hass, entity_id=entity_id)

        state = hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
        assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED

    future += timedelta(seconds=1)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == STATE_ALARM_ARMED_AWAY
    assert state.state == STATE_ALARM_TRIGGERED


@pytest.mark.parametrize(
    "expected_state",
    [
        (STATE_ALARM_ARMED_AWAY),
        (STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (STATE_ALARM_ARMED_HOME),
        (STATE_ALARM_ARMED_NIGHT),
        (STATE_ALARM_ARMED_VACATION),
        (STATE_ALARM_DISARMED),
    ],
)
async def test_restore_state(hass: HomeAssistant, expected_state) -> None:
    """Ensure state is restored on startup."""
    mock_restore_cache(hass, (State("alarm_control_panel.test", expected_state),))

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 0,
                "trigger_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test")
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    "expected_state",
    [
        (STATE_ALARM_ARMED_AWAY),
        (STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (STATE_ALARM_ARMED_HOME),
        (STATE_ALARM_ARMED_NIGHT),
        (STATE_ALARM_ARMED_VACATION),
    ],
)
async def test_restore_state_arming(hass: HomeAssistant, expected_state) -> None:
    """Ensure ARMING state is restored on startup."""
    time = dt_util.utcnow() - timedelta(seconds=15)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": STATE_ALARM_DISARMED,
        "next_state": expected_state,
    }
    mock_restore_cache(
        hass, (State(entity_id, expected_state, attributes, last_updated=time),)
    )

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 60,
                "trigger_time": 0,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["previous_state"] == STATE_ALARM_DISARMED
    assert state.attributes["next_state"] == expected_state
    assert state.state == STATE_ALARM_ARMING

    future = time + timedelta(seconds=61)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == expected_state


@pytest.mark.parametrize(
    "previous_state",
    [
        (STATE_ALARM_ARMED_AWAY),
        (STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (STATE_ALARM_ARMED_HOME),
        (STATE_ALARM_ARMED_NIGHT),
        (STATE_ALARM_ARMED_VACATION),
        (STATE_ALARM_DISARMED),
    ],
)
async def test_restore_state_pending(hass: HomeAssistant, previous_state) -> None:
    """Ensure PENDING state is restored on startup."""
    time = dt_util.utcnow() - timedelta(seconds=15)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": previous_state,
        "next_state": STATE_ALARM_TRIGGERED,
    }
    mock_restore_cache(
        hass,
        (State(entity_id, STATE_ALARM_TRIGGERED, attributes, last_updated=time),),
    )

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 0,
                "delay_time": 60,
                "trigger_time": 60,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["previous_state"] == previous_state
    assert state.attributes["next_state"] == STATE_ALARM_TRIGGERED
    assert state.state == STATE_ALARM_PENDING

    future = time + timedelta(seconds=61)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_TRIGGERED

    future = time + timedelta(seconds=121)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == previous_state


@pytest.mark.parametrize(
    "previous_state",
    [
        (STATE_ALARM_ARMED_AWAY),
        (STATE_ALARM_ARMED_CUSTOM_BYPASS),
        (STATE_ALARM_ARMED_HOME),
        (STATE_ALARM_ARMED_NIGHT),
        (STATE_ALARM_ARMED_VACATION),
        (STATE_ALARM_DISARMED),
    ],
)
async def test_restore_state_triggered(hass: HomeAssistant, previous_state) -> None:
    """Ensure PENDING state is resolved to TRIGGERED on startup."""
    time = dt_util.utcnow() - timedelta(seconds=75)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": previous_state,
    }
    mock_restore_cache(
        hass,
        (State(entity_id, STATE_ALARM_TRIGGERED, attributes, last_updated=time),),
    )

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 0,
                "delay_time": 60,
                "trigger_time": 60,
                "disarm_after_trigger": False,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["previous_state"] == previous_state
    assert "next_state" not in state.attributes
    assert state.state == STATE_ALARM_TRIGGERED

    future = time + timedelta(seconds=121)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == previous_state


async def test_restore_state_triggered_long_ago(hass: HomeAssistant) -> None:
    """Ensure TRIGGERED state is resolved on startup."""
    time = dt_util.utcnow() - timedelta(seconds=125)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": STATE_ALARM_ARMED_AWAY,
    }
    mock_restore_cache(
        hass,
        (State(entity_id, STATE_ALARM_TRIGGERED, attributes, last_updated=time),),
    )

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_time": 0,
                "delay_time": 60,
                "trigger_time": 60,
                "disarm_after_trigger": True,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ALARM_DISARMED
