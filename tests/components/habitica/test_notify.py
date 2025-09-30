"""Tests for the Habitica notify platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory, freeze_time
from habiticalib import HabiticaGroupMembersResponse
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DOMAIN
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ERROR_BAD_REQUEST,
    ERROR_NOT_AUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_TOO_MANY_REQUESTS,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_fixture,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.usefixtures("habitica")
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


@pytest.mark.parametrize(
    ("entity_id", "call_method", "call_args"),
    [
        (
            "notify.test_user_party_chat",
            "send_group_message",
            {"group_id": UUID("1e87097c-4c03-4f8c-a475-67cc7da7f409")},
        ),
        (
            "notify.test_user_private_message_test_partymember_displayname",
            "send_private_message",
            {"to_user_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7")},
        ),
    ],
)
@freeze_time("2025-08-13T00:00:00+00:00")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    entity_id: str,
    call_method: str,
    call_args: dict[str, Any],
) -> None:
    """Test send message."""

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
            ATTR_MESSAGE: "Greetings, fellow adventurer",
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2025-08-13T00:00:00+00:00"
    getattr(habitica, call_method).assert_called_once_with(
        message="Greetings, fellow adventurer", **call_args
    )


@pytest.mark.parametrize(
    "exception",
    [
        ERROR_BAD_REQUEST,
        ERROR_NOT_AUTHORIZED,
        ERROR_NOT_FOUND,
        ERROR_TOO_MANY_REQUESTS,
        ClientError,
    ],
)
async def test_send_message_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    exception: Exception,
) -> None:
    """Test send message exceptions."""

    habitica.send_group_message.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.test_user_party_chat",
                ATTR_MESSAGE: "Greetings, fellow adventurer",
            },
            blocking=True,
        )


async def test_remove_stale_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing stale private message entities."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get(
        "notify.test_user_private_message_test_partymember_displayname"
    )

    habitica.get_group_members.return_value = HabiticaGroupMembersResponse.from_json(
        await async_load_fixture(hass, "party_members_2.json", DOMAIN)
    )

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("notify.test_user_private_message_test_partymember_displayname")
        is None
    )
