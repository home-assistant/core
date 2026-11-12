"""Tests for the TRMNL notify platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
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
    PRIVATE_PLUGIN_ID,
)
from homeassistant.components.trmnl.notify import MESSAGE_MARKUP
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration


async def test_send_message_creates_plugin_once(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the first message creates the messages plugin and later ones reuse it."""
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=7, name="Home Assistant messages", plugin_id=PRIVATE_PLUGIN_ID
    )
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

    mock_trmnl_client.create_plugin_setting.assert_awaited_once()
    mock_trmnl_client.update_plugin_setting_fields.assert_awaited_once_with(
        7, {"strategy": "webhook"}
    )
    mock_trmnl_client.write_markup.assert_awaited_once_with(
        7, "markup_full", MESSAGE_MARKUP
    )
    assert mock_config_entry.options[CONF_MESSAGES_PLUGIN_SETTING_ID] == 7
    plugin_setting_id, data = (
        mock_trmnl_client.update_plugin_setting_data.await_args.args
    )
    assert (plugin_setting_id, data["message"]) == (7, "Door open")


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
    """Test a message asks for a new sign in when the content scope was unticked."""
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

    with pytest.raises(HomeAssistantError) as error:
        await send(hass)

    assert error.value.translation_key == "content_not_granted"
    mock_trmnl_client.create_plugin_setting.assert_not_called()


async def test_send_message_error(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed push becomes a Home Assistant error."""
    mock_trmnl_client.create_plugin_setting.side_effect = TRMNLError("status 403")
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as error:
        await send(hass)

    assert error.value.translation_key == "action_error"


async def test_deleted_messages_plugin_is_made_again(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a messages plugin the user deleted on TRMNL is created again."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MESSAGES_PLUGIN_SETTING_ID: 7}
    )
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=8, name="Home Assistant messages", plugin_id=PRIVATE_PLUGIN_ID
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLNotFoundError("Plugin setting not found"),
        None,
    ]
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    await send(hass)

    assert mock_config_entry.options[CONF_MESSAGES_PLUGIN_SETTING_ID] == 8
    assert [
        args.args[0]
        for args in mock_trmnl_client.update_plugin_setting_data.await_args_list
    ] == [7, 8]


async def test_send_message_refused_for_scope(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TRMNL refusing the message for a revoked scope asks for a new sign in."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MESSAGES_PLUGIN_SETTING_ID: 7}
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = TRMNLForbiddenError(
        "Missing capability: content"
    )
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as error:
        await send(hass)

    assert error.value.translation_key == "content_not_granted"
