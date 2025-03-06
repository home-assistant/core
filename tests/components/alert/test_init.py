"""The tests for the Alert component."""

from copy import deepcopy

import pytest

from homeassistant.components import alert, notify
from homeassistant.components.alert.const import (
    CONF_ALERT_MESSAGE,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockEntityPlatform, async_mock_service

NAME = "alert_test"
DONE_MESSAGE = "alert_gone"
NOTIFIER = "test"
BAD_NOTIFIER = "bad_notifier"
TEMPLATE = "{{ states.sensor.test.entity_id }}"
TEST_ENTITY = "sensor.test"
TITLE = "{{ states.sensor.test.entity_id }}"
TEST_TITLE = "sensor.test"
TEST_DATA = {"data": {"inline_keyboard": ["Close garage:/close_garage"]}}
TEST_CONFIG = {
    DOMAIN: {
        NAME: {
            CONF_NAME: NAME,
            CONF_DONE_MESSAGE: DONE_MESSAGE,
            CONF_ENTITY_ID: TEST_ENTITY,
            CONF_STATE: STATE_ON,
            CONF_REPEAT: 30,
            CONF_SKIP_FIRST: False,
            CONF_NOTIFIERS: [NOTIFIER],
            CONF_TITLE: TITLE,
            CONF_DATA: {},
        }
    }
}
TEST_NOACK = [
    NAME,
    NAME,
    "sensor.test",
    STATE_ON,
    [30],
    False,
    None,
    None,
    NOTIFIER,
    False,
    None,
    None,
]
ENTITY_ID = f"{DOMAIN}.{NAME}"


@pytest.fixture
def mock_notifier(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock for notifier."""
    return async_mock_service(hass, notify.DOMAIN, NOTIFIER)


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup method."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


async def test_fire(hass: HomeAssistant, mock_notifier: list[ServiceCall]) -> None:
    """Test the alert firing."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_silence(hass: HomeAssistant, mock_notifier: list[ServiceCall]) -> None:
    """Test silencing the alert."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # alert should not be silenced on next fire
    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_silence_can_acknowledge_false(hass: HomeAssistant) -> None:
    """Test that attempting to silence an alert with can_acknowledge=False will not silence."""
    # Create copy of config where can_acknowledge is False
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME]["can_acknowledge"] = False

    # Setup the alert component
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Ensure the alert is currently on
    hass.states.async_set(ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Attempt to acknowledge
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    # The state should still be ON because can_acknowledge=False
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_reset(hass: HomeAssistant, mock_notifier: list[ServiceCall]) -> None:
    """Test resetting the alert."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_toggle(hass: HomeAssistant, mock_notifier: list[ServiceCall]) -> None:
    """Test toggling alert."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_notification_no_done_message(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    config = deepcopy(TEST_CONFIG)
    del config[DOMAIN][NAME][CONF_DONE_MESSAGE]

    assert await async_setup_component(hass, DOMAIN, config)
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1


async def test_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2


async def test_bad_notifier(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test a broken notifier does not break the alert."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_NOTIFIERS] = [BAD_NOTIFIER, NOTIFIER]
    assert await async_setup_component(hass, DOMAIN, config)
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


async def test_no_notifiers(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test we send no notifications when there are not no."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                NAME: {
                    CONF_NAME: NAME,
                    CONF_ENTITY_ID: TEST_ENTITY,
                    CONF_STATE: STATE_ON,
                    CONF_REPEAT: 30,
                }
            }
        },
    )
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0


async def test_sending_non_templated_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == NAME


async def test_sending_templated_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test templated notification."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_ALERT_MESSAGE] = TEMPLATE
    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == TEST_ENTITY


async def test_sending_templated_done_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test templated notification."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_DONE_MESSAGE] = TEMPLATE
    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set(TEST_ENTITY, STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == TEST_ENTITY


async def test_sending_titled_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_TITLE] = TITLE
    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_TITLE] == TEST_TITLE


async def test_sending_data_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_DATA] = TEST_DATA
    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_DATA] == TEST_DATA


async def test_skipfirst(hass: HomeAssistant, mock_notifier: list[ServiceCall]) -> None:
    """Test skipping first notification."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_SKIP_FIRST] = True
    assert await async_setup_component(hass, DOMAIN, config)
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0


async def test_done_message_state_tracker_reset_on_cancel(hass: HomeAssistant) -> None:
    """Test that the done message is reset when canceled."""
    entity = alert.AlertEntity(hass, *TEST_NOACK)
    entity.platform = MockEntityPlatform(hass)
    entity._cancel = lambda *args: None
    assert entity._send_done_message is False
    entity._send_done_message = True
    await entity.end_alerting()
    await hass.async_block_till_done()
    assert entity._send_done_message is False
