"""Support for sending messages to TRMNL."""

import asyncio
from typing import Any, NoReturn, override

from aiohttp import ClientError
from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, OAuth2TokenRequestReauthError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_MESSAGES_PLUGIN_SETTING_ID, DOMAIN, PLUGIN_KEYNAME
from .coordinator import TRMNLConfigEntry, scope_granted

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TRMNLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TRMNL notify entity."""
    async_add_entities([TRMNLNotifyEntity(entry)])


class TRMNLNotifyEntity(NotifyEntity):
    """Show a message on TRMNL through the Messages view of its Home Assistant plugin."""

    _attr_has_entity_name = True
    _attr_translation_key = "message"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: TRMNLConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._sends: set[asyncio.Task[None]] = set()
        self._removing = False
        self._attr_unique_id = f"{entry.unique_id}_message"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry.unique_id}")},
            name=entry.title,
            manufacturer="TRMNL",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Push the message, as a task the entity's removal waits for."""
        if self._removing:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unloading"
            )
        send = self._entry.async_create_task(
            self.hass, self._async_send(message, title), "trmnl_message"
        )
        self._sends.add(send)
        send.add_done_callback(self._sends.discard)
        await send

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Refuse new messages and wait for any under way, so their plugin id is saved."""
        self._removing = True
        if self._sends:
            await asyncio.wait(self._sends)

    async def _async_send(self, message: str, title: str | None) -> None:
        if not scope_granted(self._entry, "content"):
            self._raise_reauth("content_not_granted")
        sent_at = dt_util.utcnow().isoformat()
        data = {"message": {"title": title or "", "text": message, "sent_at": sent_at}}
        try:
            await self._entry.runtime_data.async_ensure_token_valid()
            await self._async_push(data)
        except OAuth2TokenRequestReauthError as error:
            self._raise_reauth("authentication_error", error)
        except TRMNLForbiddenError as error:
            self._raise_reauth("content_not_granted", error)
        except (TRMNLError, ClientError, TimeoutError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="message_error"
            ) from error

    async def _async_push(self, data: dict[str, Any]) -> None:
        """Push to the messages plugin setting, made again if the user deleted it."""
        client = self._entry.runtime_data.client
        plugin_setting_id = self._entry.data.get(CONF_MESSAGES_PLUGIN_SETTING_ID)
        if plugin_setting_id is None:
            plugin_setting_id = await self._async_create_plugin_setting()
        try:
            await client.update_plugin_setting_data(plugin_setting_id, data)
        except TRMNLNotFoundError:
            await client.update_plugin_setting_data(
                await self._async_create_plugin_setting(), data
            )

    async def _async_create_plugin_setting(self) -> int:
        """Create a plugin setting that shows the Messages view and save its id."""
        client = self._entry.runtime_data.client
        plugin_setting = await client.create_plugin_setting(
            "Home Assistant messages", plugin_keyname=PLUGIN_KEYNAME
        )
        await client.update_plugin_setting_fields(
            plugin_setting.identifier, {"view": "messages"}
        )
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_MESSAGES_PLUGIN_SETTING_ID: plugin_setting.identifier,
            },
        )
        return plugin_setting.identifier

    def _raise_reauth(
        self, translation_key: str, error: Exception | None = None
    ) -> NoReturn:
        self._entry.async_start_reauth(self.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key=translation_key
        ) from error
