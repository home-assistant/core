"""Tests for the Notifications for Android TV / Fire TV notify platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import NAME

from tests.common import AsyncMock, MockConfigEntry, snapshot_platform


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
