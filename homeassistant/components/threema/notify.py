"""Notify platform for Threema Gateway integration."""

from typing import override

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import ThreemaConfigEntry
from .client import ThreemaAuthError, ThreemaConnectionError, ThreemaSendError
from .const import DOMAIN, SUBENTRY_TYPE_RECIPIENT


def _stored_recipient_name(subentry: ConfigSubentry, recipient_id: str) -> str | None:
    """Return the recipient's display name, or None if none was given.

    Subentries created before the display name was stored separately in
    `data` only have it baked into the title as "Name (RECIPIENT_ID)" —
    recover it from there so older recipients don't lose their name.
    """
    name = subentry.data.get(CONF_NAME)
    if isinstance(name, str) and name:
        return name
    suffix = f" ({recipient_id})"
    if subentry.title.endswith(suffix):
        return subentry.title.removesuffix(suffix)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThreemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Threema notify entities from config entry subentries."""
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_RECIPIENT:
            continue
        async_add_entities(
            [ThreemaNotifyEntity(entry, subentry)],
            config_subentry_id=subentry_id,
        )


class ThreemaNotifyEntity(NotifyEntity):
    """Notify entity for sending messages to a Threema recipient."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        entry: ThreemaConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the notify entity."""
        self._entry = entry
        self._client = entry.runtime_data
        self._recipient_id: str = subentry.data[CONF_RECIPIENT]

        self._attr_unique_id = f"{self._client.gateway_id}_{self._recipient_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Threema",
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=subentry.title,
        )

        # Explicitly suggest the object id: threema_<gateway>_[<name>_]<recipient id>.
        # This is independent of the display name above (which stays
        # "Name (ID)" for disambiguation in the UI).
        name = _stored_recipient_name(subentry, self._recipient_id)
        object_id_parts = ["threema", self._client.gateway_id]
        if name:
            object_id_parts.append(name)
        object_id_parts.append(self._recipient_id)
        self.entity_id = f"{NOTIFY_DOMAIN}.{slugify('_'.join(object_id_parts))}"

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the configured Threema recipient."""
        text = f"*{title}*\n{message}" if title else message
        try:
            await self._client.send_text_message(self._recipient_id, text)
        except ThreemaAuthError as err:
            self._entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except (ThreemaSendError, ThreemaConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_error",
                translation_placeholders={"error": str(err)},
            ) from err
