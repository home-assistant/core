"""Tests for the LaMetric services."""

from unittest.mock import MagicMock

from demetriek import (
    Chart,
    LaMetricError,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    NotificationSoundCategory,
    Simple,
    Sound,
    SoundURL,
)
import probatio
import pytest

from homeassistant.components.lametric.const import (
    CONF_CYCLES,
    CONF_DATA,
    CONF_ICON_TYPE,
    CONF_MESSAGE,
    CONF_PRIORITY,
    CONF_SOUND,
    CONF_SOUND_URL,
    DOMAIN,
    SERVICE_CHART,
    SERVICE_MESSAGE,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_service_chart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric chart service."""

    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry
    assert entry.device_id

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHART,
        {
            CONF_DEVICE_ID: entry.device_id,
            CONF_DATA: [1, 2, 3, 4, 5, 4, 3, 2, 1],
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
    assert type(frame) is Chart
    assert frame.data == [1, 2, 3, 4, 5, 4, 3, 2, 1]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHART,
        {
            CONF_DATA: [1, 2, 3, 4, 5, 4, 3, 2, 1],
            CONF_DEVICE_ID: entry.device_id,
            CONF_CYCLES: 3,
            CONF_ICON_TYPE: "info",
            CONF_PRIORITY: "critical",
            CONF_SOUND: "cat",
        },
        blocking=True,
    )

    assert len(mock_lametric.notify.mock_calls) == 2

    notification: Notification = mock_lametric.notify.mock_calls[1][2]["notification"]
    assert notification.icon_type is NotificationIconType.INFO
    assert notification.life_time is None
    assert notification.model.cycles == 3
    assert notification.model.sound is not None
    assert notification.model.sound.category is NotificationSoundCategory.NOTIFICATIONS
    assert notification.model.sound.sound is NotificationSound.CAT
    assert notification.model.sound.repeat == 1
    assert notification.notification_id is None
    assert notification.notification_type is None
    assert notification.priority is NotificationPriority.CRITICAL

    assert len(notification.model.frames) == 1
    frame = notification.model.frames[0]
    assert type(frame) is Chart
    assert frame.data == [1, 2, 3, 4, 5, 4, 3, 2, 1]

    mock_lametric.notify.side_effect = LaMetricError("Fail to validate")
    with pytest.raises(
        HomeAssistantError,
        match="Could not send the notification to the LaMetric device: Fail to validate",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHART,
            {
                CONF_DEVICE_ID: entry.device_id,
                CONF_DATA: [1, 2, 3, 4, 5],
            },
            blocking=True,
        )

    assert len(mock_lametric.notify.mock_calls) == 3


async def test_service_message(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric message service."""

    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry
    assert entry.device_id

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MESSAGE,
        {
            CONF_DEVICE_ID: entry.device_id,
            CONF_MESSAGE: "Hi!",
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
    assert frame.icon is None
    assert frame.text == "Hi!"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MESSAGE,
        {
            CONF_DEVICE_ID: entry.device_id,
            CONF_MESSAGE: "Meow!",
            CONF_CYCLES: 3,
            CONF_ICON_TYPE: "info",
            CONF_PRIORITY: "critical",
            CONF_SOUND: "cat",
            CONF_ICON: "6916",
        },
        blocking=True,
    )

    assert len(mock_lametric.notify.mock_calls) == 2

    notification: Notification = mock_lametric.notify.mock_calls[1][2]["notification"]
    assert notification.icon_type is NotificationIconType.INFO
    assert notification.life_time is None
    assert notification.model.cycles == 3
    assert notification.model.sound is not None
    assert notification.model.sound.category is NotificationSoundCategory.NOTIFICATIONS
    assert notification.model.sound.sound is NotificationSound.CAT
    assert notification.model.sound.repeat == 1
    assert notification.notification_id is None
    assert notification.notification_type is None
    assert notification.priority is NotificationPriority.CRITICAL

    assert len(notification.model.frames) == 1
    frame = notification.model.frames[0]
    assert type(frame) is Simple
    assert frame.icon == "6916"
    assert frame.text == "Meow!"

    mock_lametric.notify.side_effect = LaMetricError("Fail to validate")
    with pytest.raises(
        HomeAssistantError,
        match="Could not send the notification to the LaMetric device: Fail to validate",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MESSAGE,
            {
                CONF_DEVICE_ID: entry.device_id,
                CONF_MESSAGE: "Epic failure!",
            },
            blocking=True,
        )

    assert len(mock_lametric.notify.mock_calls) == 3


@pytest.mark.parametrize("device_fixture", ["device_sa5_bluetooth_unavailable"])
async def test_service_message_without_audio(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the sound is left out for a device that cannot play it.

    A device without audio, like a SKY, would refuse the whole notification.
    """
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "SA52100000000TBNC"), mock_config_entry.entry_id
    )
    assert device

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MESSAGE,
        {CONF_DEVICE_ID: device.id, CONF_MESSAGE: "Meow!", CONF_SOUND: "cat"},
        blocking=True,
    )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound is None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {CONF_SOUND_URL: "https://example.com/doorbell.mp3"},
            SoundURL(url="https://example.com/doorbell.mp3"),
        ),
        # A built-in sound given as well plays when the URL cannot be fetched.
        (
            {CONF_SOUND_URL: "https://example.com/doorbell.mp3", CONF_SOUND: "cat"},
            SoundURL(
                url="https://example.com/doorbell.mp3",
                fallback=Sound(sound=NotificationSound.CAT),
            ),
        ),
    ],
    ids=["url", "url_with_fallback"],
)
async def test_service_message_sound_url(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lametric: MagicMock,
    data: dict[str, str],
    expected: SoundURL,
) -> None:
    """Test sending a notification with a sound from a URL."""
    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MESSAGE,
        {CONF_DEVICE_ID: entry.device_id, CONF_MESSAGE: "Ding dong!", **data},
        blocking=True,
    )

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound == expected


async def test_service_message_invalid_sound_url(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lametric: MagicMock,
) -> None:
    """Test a sound URL that is no URL is refused."""
    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MESSAGE,
            {
                CONF_DEVICE_ID: entry.device_id,
                CONF_MESSAGE: "Ding dong!",
                CONF_SOUND_URL: "doorbell",
            },
            blocking=True,
        )

    mock_lametric.notify.assert_not_called()
