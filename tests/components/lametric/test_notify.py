"""Tests for the LaMetric notify platform."""

from unittest.mock import MagicMock

from demetriek import (
    LaMetricConnectionError,
    LaMetricError,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    NotificationSoundCategory,
    Simple,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

NOTIFY_SERVICE = "frenck_s_lametric"
ENTITY_ID = "notify.frenck_s_lametric_message"

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.NOTIFY], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_notification_defaults(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric notification defaults."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        NOTIFY_SERVICE,
        {
            ATTR_MESSAGE: (
                "Try not to become a man of success. Rather become a man of value"
            ),
        },
        blocking=True,
    )

    assert len(mock_lametric.notify.mock_calls) == 1

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.icon_type is NotificationIconType.NONE
    assert notification.life_time is None
    assert notification.model.cycles == 1
    assert notification.model.sound is None
    assert notification.notification_id is None
    assert notification.notification_type is None
    assert notification.priority is NotificationPriority.INFO

    assert len(notification.model.frames) == 1
    frame = notification.model.frames[0]
    assert type(frame) is Simple
    assert frame.icon == "a7956"
    assert (
        frame.text == "Try not to become a man of success. Rather become a man of value"
    )


async def test_notification_options(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric notification options."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        NOTIFY_SERVICE,
        {
            ATTR_MESSAGE: "The secret of getting ahead is getting started",
            ATTR_DATA: {
                "icon": "1234",
                "sound": "positive1",
                "cycles": 3,
                "icon_type": "alert",
                "priority": "critical",
            },
        },
        blocking=True,
    )

    assert len(mock_lametric.notify.mock_calls) == 1

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.icon_type is NotificationIconType.ALERT
    assert notification.life_time is None
    assert notification.model.cycles == 3
    assert notification.model.sound is not None
    assert notification.model.sound.category is NotificationSoundCategory.NOTIFICATIONS
    assert notification.model.sound.sound is NotificationSound.POSITIVE1
    assert notification.model.sound.repeat == 1
    assert notification.notification_id is None
    assert notification.notification_type is None
    assert notification.priority is NotificationPriority.CRITICAL

    assert len(notification.model.frames) == 1
    frame = notification.model.frames[0]
    assert type(frame) is Simple
    assert frame.icon == "1234"
    assert frame.text == "The secret of getting ahead is getting started"


async def test_notification_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric notification error."""
    mock_lametric.notify.side_effect = LaMetricError

    with pytest.raises(
        HomeAssistantError, match="Could not send LaMetric notification"
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            NOTIFY_SERVICE,
            {
                ATTR_MESSAGE: "It's failure that gives you the proper perspective",
            },
            blocking=True,
        )


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2022-09-19 12:07:30")
async def test_send_message(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test sending a message through the LaMetric notify entity."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "The way to get started is to quit talking and begin doing",
        },
        blocking=True,
    )

    assert len(mock_lametric.notify.mock_calls) == 1

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.icon_type is NotificationIconType.NONE
    assert notification.priority is NotificationPriority.INFO
    assert notification.model.sound is None

    assert len(notification.model.frames) == 1
    frame = notification.model.frames[0]
    assert type(frame) is Simple
    assert frame.icon is None
    assert frame.text == "The way to get started is to quit talking and begin doing"

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


@pytest.mark.parametrize(
    ("side_effect", "error_message", "expected_state"),
    [
        pytest.param(
            LaMetricError,
            "Invalid response from the LaMetric device",
            STATE_UNKNOWN,
            id="error",
        ),
        pytest.param(
            LaMetricConnectionError,
            "Error communicating with the LaMetric device",
            STATE_UNAVAILABLE,
            id="connection_error",
        ),
    ],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    side_effect: type[LaMetricError],
    error_message: str,
    expected_state: str,
) -> None:
    """Test error handling of the LaMetric notify entity."""
    mock_lametric.notify.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MESSAGE: "It's failure that gives you the proper perspective",
            },
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state
