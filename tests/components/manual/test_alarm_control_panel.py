"""The tests for the manual Alarm Control Panel component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.demo import alarm_control_panel as demo
from homeassistant.components.manual.alarm_control_panel import (
    ATTR_NEXT_STATE,
    ATTR_PREVIOUS_STATE,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_component, mock_restore_cache
from tests.components.alarm_control_panel import common

CODE = "HELLO_CODE"


async def test_setup_demo_platform(hass: HomeAssistant) -> None:
    """Test setup."""
    mock = MagicMock()
    add_entities = mock.MagicMock()
    await demo.async_setup_entry(hass, {}, add_entities)
    assert add_entities.call_count == 1


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

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
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

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
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: CODE},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING

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
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    with pytest.raises(ServiceValidationError, match=r"^Invalid alarm code provided$"):
        await hass.services.async_call(
            alarm_control_panel.DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: "alarm_control_panel.test",
                ATTR_CODE: f"{CODE}2",
            },
            blocking=True,
        )

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

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
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
        (SERVICE_ALARM_ARM_VACATION, AlarmControlPanelState.ARMED_VACATION),
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
        {ATTR_ENTITY_ID: "alarm_control_panel.test", ATTR_CODE: "1234"},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING

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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    future = dt_util.utcnow() + timedelta(seconds=60)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    state = hass.states.get(entity_id)
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=2)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future += timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.PENDING
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future += timedelta(seconds=1)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    future = dt_util.utcnow() + timedelta(seconds=2)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE, entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE, entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    await common.async_alarm_disarm(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert (
        hass.states.get(entity_id).attributes[alarm_control_panel.ATTR_CODE_FORMAT]
        == alarm_control_panel.CodeFormat.NUMBER
    )

    await common.async_alarm_trigger(hass)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    with pytest.raises(ServiceValidationError, match=r"^Invalid alarm code provided$"):
        await common.async_alarm_disarm(hass, entity_id=entity_id)

    assert hass.states.get(entity_id).state == AlarmControlPanelState.PENDING

    future = dt_util.utcnow() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.manual.alarm_control_panel.dt_util.utcnow",
        return_value=future,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.state == AlarmControlPanelState.TRIGGERED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_home(hass, "def")

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.ARMED_HOME

    with pytest.raises(ServiceValidationError, match=r"^Invalid alarm code provided$"):
        await common.async_alarm_disarm(hass, "def")

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.ARMED_HOME

    await common.async_alarm_disarm(hass, "abc")

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.DISARMED


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

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await common.async_alarm_arm_away(hass, CODE)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.ARMING
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.attributes["next_state"] == AlarmControlPanelState.ARMED_AWAY

    await common.async_alarm_trigger(hass, entity_id=entity_id)

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.ARMING
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.attributes["next_state"] == AlarmControlPanelState.ARMED_AWAY

    future = dt_util.utcnow() + timedelta(seconds=1)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == AlarmControlPanelState.ARMED_AWAY

        await common.async_alarm_trigger(hass, entity_id=entity_id)

        state = hass.states.get(entity_id)
        assert state.state == AlarmControlPanelState.PENDING
        assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
        assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED

    future += timedelta(seconds=1)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["previous_state"] == AlarmControlPanelState.ARMED_AWAY
    assert state.state == AlarmControlPanelState.TRIGGERED


@pytest.mark.parametrize(
    "expected_state",
    [
        (AlarmControlPanelState.ARMED_AWAY),
        (AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        (AlarmControlPanelState.ARMED_HOME),
        (AlarmControlPanelState.ARMED_NIGHT),
        (AlarmControlPanelState.ARMED_VACATION),
        (AlarmControlPanelState.DISARMED),
    ],
)
async def test_restore_state(hass: HomeAssistant, expected_state) -> None:
    """Ensure state is restored on startup."""
    mock_restore_cache(hass, (State("alarm_control_panel.test", expected_state),))

    hass.set_state(CoreState.starting)
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
        (AlarmControlPanelState.ARMED_AWAY),
        (AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        (AlarmControlPanelState.ARMED_HOME),
        (AlarmControlPanelState.ARMED_NIGHT),
        (AlarmControlPanelState.ARMED_VACATION),
    ],
)
async def test_restore_state_arming(hass: HomeAssistant, expected_state) -> None:
    """Ensure ARMING state is restored on startup."""
    time = dt_util.utcnow() - timedelta(seconds=15)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": AlarmControlPanelState.DISARMED,
        "next_state": expected_state,
    }
    mock_restore_cache(
        hass, (State(entity_id, expected_state, attributes, last_updated=time),)
    )

    hass.set_state(CoreState.starting)
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
    assert state.attributes["previous_state"] == AlarmControlPanelState.DISARMED
    assert state.attributes["next_state"] == expected_state
    assert state.state == AlarmControlPanelState.ARMING

    future = time + timedelta(seconds=61)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == expected_state


@pytest.mark.parametrize(
    "previous_state",
    [
        (AlarmControlPanelState.ARMED_AWAY),
        (AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        (AlarmControlPanelState.ARMED_HOME),
        (AlarmControlPanelState.ARMED_NIGHT),
        (AlarmControlPanelState.ARMED_VACATION),
        (AlarmControlPanelState.DISARMED),
    ],
)
async def test_restore_state_pending(hass: HomeAssistant, previous_state) -> None:
    """Ensure PENDING state is restored on startup."""
    time = dt_util.utcnow() - timedelta(seconds=15)
    entity_id = "alarm_control_panel.test"
    attributes = {
        "previous_state": previous_state,
        "next_state": AlarmControlPanelState.TRIGGERED,
    }
    mock_restore_cache(
        hass,
        (
            State(
                entity_id,
                AlarmControlPanelState.TRIGGERED,
                attributes,
                last_updated=time,
            ),
        ),
    )

    hass.set_state(CoreState.starting)
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
    assert state.attributes["next_state"] == AlarmControlPanelState.TRIGGERED
    assert state.state == AlarmControlPanelState.PENDING

    future = time + timedelta(seconds=61)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == AlarmControlPanelState.TRIGGERED

    future = time + timedelta(seconds=121)
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == previous_state


@pytest.mark.parametrize(
    "previous_state",
    [
        (AlarmControlPanelState.ARMED_AWAY),
        (AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        (AlarmControlPanelState.ARMED_HOME),
        (AlarmControlPanelState.ARMED_NIGHT),
        (AlarmControlPanelState.ARMED_VACATION),
        (AlarmControlPanelState.DISARMED),
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
        (
            State(
                entity_id,
                AlarmControlPanelState.TRIGGERED,
                attributes,
                last_updated=time,
            ),
        ),
    )

    hass.set_state(CoreState.starting)
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
    assert state.attributes[ATTR_PREVIOUS_STATE] == previous_state
    assert state.attributes[ATTR_NEXT_STATE] is None
    assert state.state == AlarmControlPanelState.TRIGGERED

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
        "previous_state": AlarmControlPanelState.ARMED_AWAY,
    }
    mock_restore_cache(
        hass,
        (
            State(
                entity_id,
                AlarmControlPanelState.TRIGGERED,
                attributes,
                last_updated=time,
            ),
        ),
    )

    hass.set_state(CoreState.starting)
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
    assert state.state == AlarmControlPanelState.DISARMED


async def test_default_arming_states(hass: HomeAssistant) -> None:
    """Test default arming_states."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test")
    assert state.attributes["supported_features"] == (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )


async def test_arming_states(hass: HomeAssistant) -> None:
    """Test arming_states."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_states": ["armed_away", "armed_home"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test")
    assert state.attributes["supported_features"] == (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )


async def test_invalid_arming_states(hass: HomeAssistant) -> None:
    """Test invalid arming_states."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            "alarm_control_panel": {
                "platform": "manual",
                "name": "test",
                "arming_states": ["invalid", "armed_home"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test")
    assert state is None
