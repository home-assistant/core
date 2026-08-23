"""Tests for the Notifications for Android TV / Fire TV notify platform."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

from notifications_android_tv.notifications import ConnectError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import NAME

from tests.common import AsyncMock, MockConfigEntry, snapshot_platform

LEGACY_SERVICE_NAME = "android_tv_fire_tv_1_2_3_4"


@pytest.fixture(autouse=True)
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.nfandroidtv.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the notify platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message."""
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "World",
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World"
    )


async def test_send_message_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_notifications_android_tv.send.side_effect = ConnectError

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.android_tv_fire_tv_1_2_3_4",
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
            },
            blocking=True,
        )

    assert err.value.translation_key == "notify_connection_error"
    assert err.value.translation_placeholders == {CONF_NAME: NAME}

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World"
    )


@pytest.fixture
def mock_legacy_notifications() -> Generator[MagicMock]:
    """Mock the client used by the legacy notify service."""
    with patch(
        "homeassistant.components.nfandroidtv.notify.Notifications",
        autospec=True,
    ) as mock_client:
        yield mock_client.return_value


@pytest.mark.usefixtures("mock_notifications_android_tv")
@pytest.mark.parametrize(
    ("service_data", "translation_key"),
    [
        pytest.param({"duration": "invalid"}, "invalid_duration", id="duration"),
        pytest.param({"duration": None}, "invalid_duration", id="duration_none"),
        pytest.param({"interrupt": "invalid"}, "invalid_interrupt", id="interrupt"),
    ],
)
async def test_legacy_send_message_invalid_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_legacy_notifications: MagicMock,
    service_data: dict[str, str | None],
    translation_key: str,
) -> None:
    """Test that invalid service data raises and sends nothing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, LEGACY_SERVICE_NAME)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            LEGACY_SERVICE_NAME,
            {"message": "Hello", "data": service_data},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    mock_legacy_notifications.send.assert_not_called()
