"""Tests for the TRMNL notify platform."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError
from trmnl.models import PluginSetting

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.trmnl.const import (
    CONF_MESSAGES_PLUGIN_SETTING_ID,
    DOMAIN,
    PLUGIN_KEYNAME,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)

from . import setup_integration

MESSAGES_PLUGIN_SETTING = PluginSetting(
    identifier=7, name="Home Assistant messages", plugin_id=452
)


@pytest.fixture
def messages_entry(mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """Return an entry that already has its messages plugin setting."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=mock_config_entry.title,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_MESSAGES_PLUGIN_SETTING_ID: 7},
    )


def reauth_started(hass: HomeAssistant) -> bool:
    """Return True if a reauth flow is in progress."""
    return [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH]


@pytest.mark.freeze_time("2026-11-13 12:00:00+00:00")
async def test_send_message_creates_plugin_once(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the first message creates the messages plugin setting and later ones reuse it."""
    mock_trmnl_client.create_plugin_setting.return_value = MESSAGES_PLUGIN_SETTING
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    for message in ("Washing done", "Door open"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.trmnl_message",
                ATTR_MESSAGE: message,
                ATTR_TITLE: "Home",
            },
            blocking=True,
        )

    mock_trmnl_client.create_plugin_setting.assert_awaited_once_with(
        "Home Assistant messages", plugin_keyname=PLUGIN_KEYNAME
    )
    mock_trmnl_client.update_plugin_setting_fields.assert_awaited_once_with(
        7, {"view": "messages"}
    )
    assert mock_config_entry.data[CONF_MESSAGES_PLUGIN_SETTING_ID] == 7
    assert mock_trmnl_client.update_plugin_setting_data.await_args.args == snapshot


async def send(hass: HomeAssistant) -> None:
    """Send one message through the TRMNL notify entity."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: "notify.trmnl_message", ATTR_MESSAGE: "Hi"},
        blocking=True,
    )


async def test_send_message_without_content_scope(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a message asks for a new sign in when the content scope was not granted."""
    token = {**mock_config_entry.data["token"], "scope": "openid read devices"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=mock_config_entry.title,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, "token": token},
    )
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, entry)

    with pytest.raises(HomeAssistantError) as raised:
        await send(hass)

    assert raised.value.translation_key == "content_not_granted"
    mock_trmnl_client.create_plugin_setting.assert_not_called()
    assert reauth_started(hass)


@pytest.mark.parametrize(
    "error",
    [
        TRMNLError("status 500"),
        ClientError("Connection reset"),
        TimeoutError(),
        OAuth2TokenRequestConnectionError(domain=DOMAIN),
    ],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    messages_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test a failed or unreachable push becomes a translated Home Assistant error."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = error
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, messages_entry)

    with pytest.raises(HomeAssistantError) as raised:
        await send(hass)

    assert raised.value.translation_key == "message_error"


async def test_deleted_messages_plugin_is_made_again(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    messages_entry: MockConfigEntry,
) -> None:
    """Test a messages plugin setting the user deleted on TRMNL is created again."""
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=8, name="Home Assistant messages", plugin_id=452
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLNotFoundError("Plugin setting not found"),
        None,
    ]
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, messages_entry)

    await send(hass)

    assert messages_entry.data[CONF_MESSAGES_PLUGIN_SETTING_ID] == 8
    assert [
        args.args[0]
        for args in mock_trmnl_client.update_plugin_setting_data.await_args_list
    ] == [7, 8]


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (TRMNLForbiddenError("Missing capability: content"), "content_not_granted"),
        (
            OAuth2TokenRequestReauthError(
                domain=DOMAIN, request_info=Mock(), status=400
            ),
            "authentication_error",
        ),
    ],
)
async def test_send_message_refused_starts_reauth(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    messages_entry: MockConfigEntry,
    error: Exception,
    translation_key: str,
) -> None:
    """Test TRMNL refusing the sign in or its scope asks for a new sign in."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = error
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, messages_entry)

    with pytest.raises(HomeAssistantError) as raised:
        await send(hass)

    assert raised.value.translation_key == translation_key
    assert reauth_started(hass)


async def test_failed_view_setup_saves_nothing(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a plugin setting whose view could not be set is not used for messages."""
    mock_trmnl_client.create_plugin_setting.return_value = MESSAGES_PLUGIN_SETTING
    mock_trmnl_client.update_plugin_setting_fields.side_effect = TRMNLError(
        "status 500"
    )
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await send(hass)

    assert CONF_MESSAGES_PLUGIN_SETTING_ID not in mock_config_entry.data
    mock_trmnl_client.update_plugin_setting_data.assert_not_called()


async def test_remove_during_first_message_deletes_the_new_plugin(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removal waits for a message that is creating its plugin, then deletes it."""
    created = asyncio.Event()

    async def create_plugin_setting(*_: Any, **__: Any) -> PluginSetting:
        await created.wait()
        return MESSAGES_PLUGIN_SETTING

    mock_trmnl_client.create_plugin_setting.side_effect = create_plugin_setting
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)
    message = hass.async_create_task(send(hass))
    while not mock_trmnl_client.create_plugin_setting.await_count:
        await asyncio.sleep(0)
    wait = asyncio.wait

    async def give_up_at_once(tasks: Any, timeout: float | None = None) -> Any:
        # Only the config entry's 10 second wait for its tasks gives up at once.
        return await wait(tasks, timeout=0 if timeout == 10 else timeout)

    with patch("homeassistant.config_entries.asyncio.wait", give_up_at_once):
        remove = hass.async_create_task(
            hass.config_entries.async_remove(mock_config_entry.entry_id)
        )
        for _ in range(20):
            await asyncio.sleep(0)
        assert not remove.done()
        created.set()
        await remove
    await message

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(7)


async def test_no_message_starts_while_the_entity_is_removed(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a message that reaches the entity while it is being removed is refused."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)
    entity = hass.data["entity_components"][NOTIFY_DOMAIN].get_entity(
        "notify.trmnl_message"
    )
    await entity.async_will_remove_from_hass()

    with pytest.raises(HomeAssistantError) as error:
        await entity.async_send_message("Hi")

    assert error.value.translation_key == "unloading"
    mock_trmnl_client.create_plugin_setting.assert_not_called()
