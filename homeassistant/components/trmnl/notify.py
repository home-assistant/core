"""Support for sending messages to TRMNL."""

from typing import override

from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_MESSAGES_PLUGIN_SETTING_ID, DOMAIN, PRIVATE_PLUGIN_ID
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
        self._attr_unique_id = f"{entry.unique_id}_message"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry.unique_id}")},
            name=entry.title,
            manufacturer="TRMNL",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Push the message to the messages plugin."""
        if not scope_granted(self._entry, "content"):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="content_not_granted"
            )
        await self._entry.runtime_data.async_ensure_token_valid()
        data = {
            "title": title or "",
            "message": message,
            "sent_at": dt_util.now().strftime("%H:%M"),
        }
        client = self._entry.runtime_data.client
        try:
            plugin_setting_id = self._entry.options.get(CONF_MESSAGES_PLUGIN_SETTING_ID)
            if plugin_setting_id is None:
                plugin_setting_id = await self._async_create_plugin_setting()
            try:
                await client.update_plugin_setting_data(plugin_setting_id, data)
            except TRMNLNotFoundError:
                await client.update_plugin_setting_data(
                    await self._async_create_plugin_setting(), data
                )
        except TRMNLForbiddenError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="content_not_granted"
            ) from error
        except TRMNLError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"error": str(error)},
            ) from error

    async def _async_create_plugin_setting(self) -> int:
        client = self._entry.runtime_data.client
        plugin_setting = await client.create_plugin_setting(
            "Home Assistant messages", PRIVATE_PLUGIN_ID
        )
        plugin_setting_id = plugin_setting.identifier
        await client.update_plugin_setting_fields(
            plugin_setting_id, {"strategy": "webhook"}
        )
        await client.write_markup(plugin_setting_id, "markup_full", MESSAGE_MARKUP)
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={
                **self._entry.options,
                CONF_MESSAGES_PLUGIN_SETTING_ID: plugin_setting_id,
            },
        )
        return plugin_setting_id
