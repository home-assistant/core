"""The tests for the Alert component."""

from copy import deepcopy
from unittest.mock import patch

import pytest

import homeassistant.components.alert as alert
from homeassistant.components.alert.const import (
    CONF_ALERT_MESSAGE,
    CONF_CAN_ACK,
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
    CONF_ID,
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
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_mock_service

NAME = "alert_test"
NAME_MODIFIED = "alert_test_modified"
DONE_MESSAGE = "alert_gone"
DONE_MESSAGE_MODIFIED = "alert_gone_modified"
NOTIFIER = "test"
BAD_NOTIFIER = "bad_notifier"
TEMPLATE = "{{ states.sensor.test.entity_id }}"
TEST_ENTITY = "sensor.test"
TEST_ENTITY_MODIFIED = "sensor.test2"
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
TEST_NOACK = {
    CONF_NAME: NAME,
    CONF_ENTITY_ID: "sensor.test",
    CONF_STATE: STATE_ON,
    CONF_REPEAT: [30],
    CONF_SKIP_FIRST: False,
    CONF_NOTIFIERS: NOTIFIER,
    CONF_CAN_ACK: False,
}
ENTITY_ID = f"{DOMAIN}.{NAME}"
ENTITY_ID_MODIFIED = f"{DOMAIN}.{NAME_MODIFIED}"


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


async def test_done_message_state_tracker_reset_on_cancel(hass: HomeAssistant) -> None:
    """Test that the done message is reset when canceled."""
    entity = alert.Alert(TEST_NOACK)
    entity.entity_id = ENTITY_ID
    entity.hass = hass
    await entity.async_added_to_hass()
    entity._cancel = lambda *args: None
    assert entity._send_done_message is False
    entity._send_done_message = True
    hass.async_add_job(entity.end_alerting)
    await hass.async_block_till_done()
    assert entity._send_done_message is False


async def test_reload(
    hass: HomeAssistant, mock_notifier: list[ServiceCall], hass_admin_user: MockUser
) -> None:
    """Test reloading the YAML config."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    expected_notifications = 0
    hass.states.async_set(TEST_ENTITY, STATE_ON)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(hass.states.async_entity_ids()) == 2
    assert len(mock_notifier) == expected_notifications

    hass.states.async_set(TEST_ENTITY, STATE_OFF)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    assert len(mock_notifier) == expected_notifications
    state_1 = hass.states.get(ENTITY_ID)

    assert state_1 is not None
    assert state_1.name == NAME

    # Change properties of the original entity name
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_NAME] = NAME_MODIFIED
    config[DOMAIN][NAME][CONF_ENTITY_ID] = TEST_ENTITY_MODIFIED
    config[DOMAIN][NAME][CONF_DONE_MESSAGE] = DONE_MESSAGE_MODIFIED

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert len(hass.states.async_entity_ids()) == 2

    state_1 = hass.states.get(ENTITY_ID)

    assert state_1 is not None
    assert state_1.name == NAME_MODIFIED

    # Assert the original watched entity and check that the alert/notification does not fire
    hass.states.async_set(TEST_ENTITY, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE

    # Deassert the original watched entity and check that the done notification does not fire
    hass.states.async_set(TEST_ENTITY, STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE

    # Assert the new watched entity and check that the modified alert does fire
    hass.states.async_set(TEST_ENTITY_MODIFIED, STATE_ON)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == NAME_MODIFIED
    assert len(hass.states.async_entity_ids()) == 3

    # Deassert the new watched entity and check that the modified alert does send done message
    hass.states.async_set(TEST_ENTITY_MODIFIED, STATE_OFF)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == DONE_MESSAGE_MODIFIED

    # Change the entity id to a new id
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME_MODIFIED] = config[DOMAIN][NAME]
    del config[DOMAIN][NAME]

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert len(hass.states.async_entity_ids()) == 3
    assert ENTITY_ID_MODIFIED in hass.states.async_entity_ids()
    assert ENTITY_ID not in hass.states.async_entity_ids()

    state_1 = hass.states.get(ENTITY_ID_MODIFIED)
    assert state_1 is not None
    assert state_1.name == NAME

    # Assert the new watched entity and check that the alert/notification does not fire
    hass.states.async_set(TEST_ENTITY_MODIFIED, STATE_ON)
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID_MODIFIED).state == STATE_IDLE

    # Deassert the new watched entity and check that the done notification does not fire
    hass.states.async_set(TEST_ENTITY_MODIFIED, STATE_OFF)
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID_MODIFIED).state == STATE_IDLE

    # Assert the original watched entity and check that the modified alert does fire
    hass.states.async_set(TEST_ENTITY, STATE_ON)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_MODIFIED).state == STATE_ON
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == NAME
    assert len(hass.states.async_entity_ids()) == 3

    # Deassert the original watched entity and check that the modified alert does send done message
    hass.states.async_set(TEST_ENTITY, STATE_OFF)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_MODIFIED).state == STATE_IDLE
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == DONE_MESSAGE


async def test_reload_activate_deactivate(
    hass: HomeAssistant, mock_notifier: list[ServiceCall], hass_admin_user: MockUser
) -> None:
    """Test reloading the YAML config."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    expected_notifications = 0
    hass.states.async_set(TEST_ENTITY, STATE_OFF)

    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    assert len(mock_notifier) == expected_notifications

    # Change the watch state to match the current state, and reload. The notification shall fire, and the alert shall turn on
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_STATE] = STATE_OFF
    expected_notifications += 1

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Reload one time, same config, while the alert is on. Make sure it does not send a new notification.
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Change the watch state to not matching the current state, and reload. The alert shall turn off, and no notification will fire.
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_STATE] = STATE_ON

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


async def test_reload_with_templates(
    hass: HomeAssistant, mock_notifier: list[ServiceCall], hass_admin_user: MockUser
) -> None:
    """Test reloading the YAML config with templates."""
    config = deepcopy(TEST_CONFIG)
    config[DOMAIN][NAME][CONF_ALERT_MESSAGE] = "Alert Message"
    config[DOMAIN][NAME][CONF_DONE_MESSAGE] = "Done Message"
    config[DOMAIN][NAME][CONF_TITLE] = "Done Message"

    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    expected_notifications = 0

    # Change strings to templates
    config[DOMAIN][NAME][CONF_ALERT_MESSAGE] = TEMPLATE
    config[DOMAIN][NAME][CONF_DONE_MESSAGE] = TEMPLATE
    config[DOMAIN][NAME][CONF_TITLE] = TEMPLATE

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications

    hass.states.async_set(TEST_ENTITY, STATE_ON)
    expected_notifications += 1
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == TEST_ENTITY
    assert last_event.data[notify.ATTR_TITLE] == TEST_ENTITY

    hass.states.async_set(TEST_ENTITY, STATE_OFF)
    expected_notifications += 1
    await hass.async_block_till_done()
    assert len(mock_notifier) == expected_notifications
    last_event = mock_notifier[-1]
    assert last_event.data[notify.ATTR_MESSAGE] == TEST_ENTITY
    assert last_event.data[notify.ATTR_TITLE] == TEST_ENTITY


async def test_delete_and_reload(
    hass: HomeAssistant, mock_notifier: list[ServiceCall], hass_admin_user: MockUser
) -> None:
    """Test reload after deleting alerts (for code coverage)."""
    assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    expected_notifications = 0
    hass.states.async_set(TEST_ENTITY, STATE_ON)
    expected_notifications += 1
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(hass.states.async_entity_ids()) == 2
    assert len(mock_notifier) == expected_notifications

    state_1 = hass.states.get(ENTITY_ID)
    assert state_1 is not None
    assert state_1.name == NAME

    # Delete the alert from yaml, leaving only the domain, with no alerts
    config = deepcopy(TEST_CONFIG)
    del config[DOMAIN][NAME]

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert len(hass.states.async_entity_ids()) == 1
    assert TEST_ENTITY in hass.states.async_entity_ids()

    state_1 = hass.states.get(ENTITY_ID)
    assert state_1 is None

    # Delete the domain completely, and reload again
    config = deepcopy(TEST_CONFIG)
    del config[DOMAIN]
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(mock_notifier) == expected_notifications
    assert len(hass.states.async_entity_ids()) == 1
    assert TEST_ENTITY in hass.states.async_entity_ids()

    state_1 = hass.states.get(ENTITY_ID)
    assert state_1 is None


async def test_from_storage(hass: HomeAssistant) -> None:
    """Test the from_storage method of the alert."""
    config = deepcopy(TEST_CONFIG[DOMAIN][NAME])
    config[CONF_ID] = NAME
    config[CONF_CAN_ACK] = False
    config[CONF_REPEAT] = []
    entity = alert.Alert.from_storage(config)
    entity.entity_id = ENTITY_ID

    assert entity._watched_entity_id == TEST_ENTITY
