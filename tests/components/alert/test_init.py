"""The tests for the Alert component."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from homeassistant.components.alert.const import (
    CONF_ALERT_MESSAGE,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DOMAIN,
)
import homeassistant.components.notify as notify
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_mock_service

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


async def test_done_message_state_tracker_reset_on_cancel(
    hass: HomeAssistant, mock_notifier: list[ServiceCall]
) -> None:
    """Test that the done message is reset when canceled."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    # Changing the attributes will not change the state
    hass.states.async_set(
        "sensor.test", STATE_ON, attributes={"some_attribute": "some_value"}
    )
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    # Triggering done message
    hass.states.async_set("sensor.test", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2

    # Once the done message is send the trigger will be reset
    # it will should not trigger again an a state change
    hass.states.async_set("sensor.test", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2


async def test_reload(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
    mock_notifier: list[ServiceCall],
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                f"{NAME}1": {
                    CONF_NAME: f"{NAME}1",
                    CONF_DONE_MESSAGE: DONE_MESSAGE,
                    CONF_ENTITY_ID: f"{TEST_ENTITY}1",
                    CONF_STATE: STATE_ON,
                    CONF_REPEAT: 30,
                    CONF_SKIP_FIRST: False,
                    CONF_NOTIFIERS: [NOTIFIER],
                    CONF_TITLE: TITLE,
                    CONF_DATA: {},
                },
                f"{NAME}2": {
                    CONF_NAME: f"{NAME}2",
                    CONF_DONE_MESSAGE: DONE_MESSAGE,
                    CONF_ENTITY_ID: f"{TEST_ENTITY}2",
                    CONF_STATE: STATE_ON,
                    CONF_REPEAT: 30,
                    CONF_SKIP_FIRST: False,
                    CONF_NOTIFIERS: [NOTIFIER],
                    CONF_TITLE: TITLE,
                    CONF_DATA: {},
                },
            },
        },
    )
    state_1 = hass.states.get("alert.alert_test1")
    state_2 = hass.states.get("alert.alert_test2")
    assert state_1.state == STATE_IDLE
    assert state_2.state == STATE_IDLE
    assert count_start + 2 == len(hass.states.async_entity_ids())

    hass.states.async_set("sensor.test1", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    hass.states.async_set("sensor.test1", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2

    hass.states.async_set("sensor.test1", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 3

    hass.states.async_set("sensor.test1", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 4

    mock_notifier.clear()

    # Now remove config 1, update config 2 and add config 3
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                f"{NAME}2": {
                    CONF_NAME: f"{NAME}2",
                    CONF_DONE_MESSAGE: DONE_MESSAGE,
                    CONF_ENTITY_ID: f"{TEST_ENTITY}2",
                    CONF_STATE: STATE_OFF,
                    CONF_REPEAT: 30,
                    CONF_SKIP_FIRST: False,
                    CONF_NOTIFIERS: [NOTIFIER],
                    CONF_TITLE: TITLE,
                    CONF_DATA: {},
                },
                f"{NAME}3": {
                    CONF_NAME: f"{NAME}3",
                    CONF_DONE_MESSAGE: DONE_MESSAGE,
                    CONF_ENTITY_ID: f"{TEST_ENTITY}3",
                    CONF_STATE: STATE_ON,
                    CONF_REPEAT: 30,
                    CONF_SKIP_FIRST: False,
                    CONF_NOTIFIERS: [NOTIFIER],
                    CONF_TITLE: TITLE,
                    CONF_DATA: {},
                },
            }
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    state_1 = hass.states.get("alert.alert_test1")
    state_2 = hass.states.get("alert.alert_test2")
    state_3 = hass.states.get("alert.alert_test3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None

    assert state_2.state == STATE_IDLE
    assert state_3.state == STATE_IDLE

    # Trigger was changed to `STATE_OFF`
    # `STATE_ON` should not trigger any more on `STATE_ON`
    hass.states.async_set("sensor.test2", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 0

    hass.states.async_set("sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 1

    hass.states.async_set("sensor.test3", STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 2

    hass.states.async_set("sensor.test3", STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == 3

    mock_notifier.clear()

    # Try to reload without a new config
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={},
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    # Assert the previous loaded items
    state_1 = hass.states.get("alert.alert_test1")
    state_2 = hass.states.get("alert.alert_test2")
    state_3 = hass.states.get("alert.alert_test3")

    assert state_1 is None
    assert state_2 is None
    assert state_3 is None
