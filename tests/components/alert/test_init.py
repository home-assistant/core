"""The tests for the Alert component."""

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

import homeassistant.components.alert as alert
from homeassistant.components.alert.const import (
    ATTR_SNOOZE_UNTIL,
    CONF_ALERT_MESSAGE,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DOMAIN,
    NOTIFICATION_SNOOZE,
    SERVICE_NOTIFICATION_CONTROL,
    SNOOZE_NOTIFICATIONS_DISABLED,
    SNOOZE_NOTIFICATIONS_ENABLED,
)
import homeassistant.components.notify as notify
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
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import now

from tests.common import async_mock_service, mock_restore_cache

NAME = "alert_test"
DONE_MESSAGE = "alert_gone"
NOTIFIER = "test"
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
    snooze_until = hass.states.get(ENTITY_ID).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_ENABLED


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
    entity = alert.Alert(hass, *TEST_NOACK)
    entity._cancel = lambda *args: None
    assert entity._send_done_message is False
    entity._send_done_message = True
    hass.async_add_job(entity.end_alerting)
    await hass.async_block_till_done()
    assert entity._send_done_message is False


async def test_ignore_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test notifications."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert len(mock_notifier) == 0

    # Disable notifications. No notifications should be sent
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFICATION_CONTROL,
        {ATTR_ENTITY_ID: ENTITY_ID, "enable": STATE_OFF},
        blocking=True,
    )
    snooze_until = hass.states.get(ENTITY_ID).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_DISABLED

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    # Re-enable notifications. Now notifications should be sent.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFICATION_CONTROL,
        {ATTR_ENTITY_ID: ENTITY_ID, "enable": STATE_ON},
        blocking=True,
    )
    snooze_until = hass.states.get(ENTITY_ID).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_ENABLED

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2


async def test_snooze_notification(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test snoozing notifications."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert len(mock_notifier) == 0

    # Snooze notifications for an hour
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFICATION_CONTROL,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "enable": NOTIFICATION_SNOOZE,
            "snooze_hours": 1,
        },
        blocking=True,
    )
    snooze_until = hass.states.get(ENTITY_ID).attributes[ATTR_SNOOZE_UNTIL]
    assert isinstance(snooze_until, datetime)
    assert snooze_until > now()

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    # TODO - it'd be nice to test that if enough time passes, the notifications will start firing,
    # but I think that'd require somehow mocking out datetime.


ENTITY_ID1 = f"{DOMAIN}.{NAME}1"
ENTITY_ID2 = f"{DOMAIN}.{NAME}2"
ENTITY_ID3 = f"{DOMAIN}.{NAME}3"


async def test_restore_snooze_state(hass: HomeAssistant) -> None:
    """Test alert snooze state restore on restart."""

    # We test restoring 3 entities. First has notifications disabled. Second has them enabled.
    # Third has notifications snoozed for the next hour.
    mock_restore_cache(
        hass,
        (
            State(
                ENTITY_ID,
                STATE_IDLE,
                {ATTR_SNOOZE_UNTIL: SNOOZE_NOTIFICATIONS_DISABLED},
            ),
            State(
                ENTITY_ID1,
                STATE_IDLE,
                {ATTR_SNOOZE_UNTIL: SNOOZE_NOTIFICATIONS_ENABLED},
            ),
            State(
                ENTITY_ID2,
                STATE_IDLE,
                {ATTR_SNOOZE_UNTIL: str(now() + timedelta(hours=1))},
            ),
            State(
                ENTITY_ID3,
                STATE_IDLE,
                {ATTR_SNOOZE_UNTIL: str(now() - timedelta(hours=1))},
            ),
        ),
    )
    TEST_CONFIG2 = deepcopy(TEST_CONFIG)
    TEST_CONFIG2[DOMAIN][NAME + "1"] = deepcopy(TEST_CONFIG[DOMAIN][NAME])
    TEST_CONFIG2[DOMAIN][NAME + "2"] = deepcopy(TEST_CONFIG[DOMAIN][NAME])
    TEST_CONFIG2[DOMAIN][NAME + "3"] = deepcopy(TEST_CONFIG[DOMAIN][NAME])
    TEST_CONFIG2[DOMAIN][NAME + "1"][CONF_NAME] = NAME + "1"
    TEST_CONFIG2[DOMAIN][NAME + "2"][CONF_NAME] = NAME + "2"
    TEST_CONFIG2[DOMAIN][NAME + "3"][CONF_NAME] = NAME + "3"

    hass.state = CoreState.not_running
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG2)

    hass.states.get(ENTITY_ID)
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    snooze_until = hass.states.get(ENTITY_ID).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_DISABLED

    hass.states.get(ENTITY_ID1)
    assert hass.states.get(ENTITY_ID1).state == STATE_IDLE
    snooze_until = hass.states.get(ENTITY_ID1).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_ENABLED

    hass.states.get(ENTITY_ID2)
    assert hass.states.get(ENTITY_ID2).state == STATE_IDLE
    snooze_until = hass.states.get(ENTITY_ID2).attributes[ATTR_SNOOZE_UNTIL]
    assert isinstance(snooze_until, datetime)
    assert snooze_until > now()

    hass.states.get(ENTITY_ID3)
    assert hass.states.get(ENTITY_ID3).state == STATE_IDLE
    snooze_until = hass.states.get(ENTITY_ID3).attributes[ATTR_SNOOZE_UNTIL]
    assert snooze_until == SNOOZE_NOTIFICATIONS_ENABLED
