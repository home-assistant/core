"""Support for sending messages to TRMNL."""

import asyncio
from typing import Any, NoReturn, override

from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MESSAGES_PLUGIN_SETTING_ID,
    CONF_MESSAGES_PLUGIN_SETTING_READY,
    DOMAIN,
    PRIVATE_PLUGIN_ID,
)
from .coordinator import TRMNLConfigEntry, scope_granted

PARALLEL_UPDATES = 1

MESSAGE_MARKUP = """<div class="layout layout--col layout--center gap--large">
  <span class="title title--xlarge text--center">{{ title }}</span>
  <span class="title text--center clamp--4">{{ message }}</span>
</div>
<div class="title_bar">
  <span class="title">Home Assistant</span>
  <span class="instance">{{ sent_at }}</span>
</div>"""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TRMNLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TRMNL notify entity."""
    async_add_entities([TRMNLNotifyEntity(entry)])


class TRMNLNotifyEntity(NotifyEntity):
    """Show a message on TRMNL through a private plugin the entity creates."""

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
            self._raise_content_not_granted()
        await self._entry.runtime_data.async_ensure_token_valid()
        data = {
            "title": title or "",
            "message": message,
            "sent_at": dt_util.now().strftime("%H:%M"),
        }
        client = self._entry.runtime_data.client
        try:
            try:
                await client.update_plugin_setting_data(
                    await self._async_plugin_setting_id(), data
                )
            except TRMNLNotFoundError:
                self._save_options(
                    {
                        CONF_MESSAGES_PLUGIN_SETTING_ID: None,
                        CONF_MESSAGES_PLUGIN_SETTING_READY: False,
                    }
                )
                await client.update_plugin_setting_data(
                    await self._async_plugin_setting_id(), data
                )
        except TRMNLForbiddenError as error:
            self._raise_content_not_granted(error)
        except TRMNLError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="message_error"
            ) from error

    async def _async_plugin_setting_id(self) -> int:
        """Return the messages plugin setting, creating and setting it up when needed."""
        client = self._entry.runtime_data.client
        plugin_setting_id = self._entry.options.get(CONF_MESSAGES_PLUGIN_SETTING_ID)
        if plugin_setting_id is None:
            plugin_setting = await client.create_plugin_setting(
                "Home Assistant messages", PRIVATE_PLUGIN_ID
            )
            plugin_setting_id = plugin_setting.identifier
            # Saved before it is set up, so a failure below cannot lose track of it.
            self._save_options({CONF_MESSAGES_PLUGIN_SETTING_ID: plugin_setting_id})
        if not self._entry.options.get(CONF_MESSAGES_PLUGIN_SETTING_READY):
            await client.update_plugin_setting_fields(
                plugin_setting_id, {"strategy": "webhook"}
            )
            await client.write_markup(plugin_setting_id, "markup_full", MESSAGE_MARKUP)
            self._save_options({CONF_MESSAGES_PLUGIN_SETTING_READY: True})
        return plugin_setting_id

    def _save_options(self, options: dict[str, Any]) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, **options}
        )

    def _raise_content_not_granted(self, error: TRMNLError | None = None) -> NoReturn:
        self._entry.async_start_reauth(self.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="content_not_granted"
        ) from error
