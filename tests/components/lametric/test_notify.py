"""Tests for the LaMetric notify platform."""

from unittest.mock import MagicMock, patch

from demetriek import (
    LaMetricConnectionError,
    LaMetricError,
    Model,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    NotificationSoundCategory,
    Simple,
    Sound,
    SoundURL,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lametric.const import DOMAIN
from homeassistant.components.media_source import PlayMedia
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
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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


async def test_notification_unknown_sound(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test an unknown sound is refused, naming the sound."""
    with pytest.raises(ServiceValidationError, match="Unknown sound: nope"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            NOTIFY_SERVICE,
            {
                ATTR_MESSAGE: "Silence is golden",
                ATTR_DATA: {"sound": "nope"},
            },
            blocking=True,
        )

    mock_lametric.notify.assert_not_called()


async def test_notification_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric notification error."""
    mock_lametric.notify.side_effect = LaMetricError("Fail to validate")

    with pytest.raises(
        HomeAssistantError,
        match="Could not send the notification to the LaMetric device: Fail to validate",
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

    mock_lametric.notify.assert_called_once_with(
        notification=Notification(
            icon_type=NotificationIconType.NONE,
            priority=NotificationPriority.INFO,
            model=Model(
                frames=[
                    Simple(
                        text="The way to get started is to quit talking and begin doing"
                    )
                ]
            ),
        )
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


@pytest.mark.parametrize(
    ("side_effect", "translation_key", "expected_state"),
    [
        pytest.param(
            LaMetricError,
            "invalid_response",
            STATE_UNKNOWN,
            id="error",
        ),
        pytest.param(
            LaMetricConnectionError,
            "communication_error",
            STATE_UNAVAILABLE,
            id="connection_error",
        ),
    ],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    side_effect: type[LaMetricError],
    translation_key: str,
    expected_state: str,
) -> None:
    """Test error handling of the LaMetric notify entity."""
    mock_lametric.notify.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MESSAGE: "It's failure that gives you the proper perspective",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize("device_fixture", ["device_sa5_bluetooth_unavailable"])
async def test_notification_without_audio(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test the sound is left out for a device that cannot play it."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "sky",
        {ATTR_MESSAGE: "Meow!", ATTR_DATA: {"sound": "cat"}},
        blocking=True,
    )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound is None


@pytest.mark.parametrize("device_fixture", ["device_sa5_bluetooth_unavailable"])
async def test_notification_unknown_sound_without_audio(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test an unknown sound is still refused for a device without audio."""
    with pytest.raises(ServiceValidationError, match="Unknown sound: nope"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "sky",
            {ATTR_MESSAGE: "Silence is golden", ATTR_DATA: {"sound": "nope"}},
            blocking=True,
        )

    mock_lametric.notify.assert_not_called()


async def test_notification_sound_url(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test sending a notification with a sound from a URL, and a fallback."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        NOTIFY_SERVICE,
        {
            ATTR_MESSAGE: "Ding dong!",
            ATTR_DATA: {
                "sound_url": "https://example.com/doorbell.mp3",
                "sound": "cat",
            },
        },
        blocking=True,
    )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound == SoundURL(
        url="https://example.com/doorbell.mp3",
        fallback=Sound(sound=NotificationSound.CAT),
    )


async def test_notification_invalid_sound_url(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test a sound URL that is no URL is refused, naming it."""
    with pytest.raises(ServiceValidationError, match="Invalid sound URL: doorbell"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            NOTIFY_SERVICE,
            {ATTR_MESSAGE: "Ding dong!", ATTR_DATA: {"sound_url": "doorbell"}},
            blocking=True,
        )

    mock_lametric.notify.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["device_sa5_bluetooth_unavailable"])
async def test_notification_sound_url_without_audio(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test a sound URL is left out for a device that cannot play it."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "sky",
        {
            ATTR_MESSAGE: "Ding dong!",
            ATTR_DATA: {"sound_url": "https://example.com/doorbell.mp3"},
        },
        blocking=True,
    )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound is None


async def test_notification_sound_from_media(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test a sound picked from the media in Home Assistant, in the notify data."""
    await async_process_ha_core_config(hass, {"internal_url": "http://10.0.0.2:8123"})

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=PlayMedia(url="/media/local/doorbell.mp3", mime_type="audio/mpeg"),
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            NOTIFY_SERVICE,
            {
                ATTR_MESSAGE: "Ding dong!",
                ATTR_DATA: {
                    "sound_url": {
                        "media_content_id": "media-source://media_source/local/doorbell.mp3",
                        "media_content_type": "audio/mpeg",
                    }
                },
            },
            blocking=True,
        )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert isinstance(notification.model.sound, SoundURL)
    assert notification.model.sound.url.startswith(
        "http://10.0.0.2:8123/media/local/doorbell.mp3?authSig="
    )
