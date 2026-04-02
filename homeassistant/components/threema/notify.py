"""Notify platform for Threema Gateway integration."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThreemaConfigEntry
from .client import (
    ThreemaAPIClient,
    ThreemaAuthError,
    ThreemaConnectionError,
    ThreemaSendError,
)
from .const import CONF_RECIPIENT, DOMAIN, SUBENTRY_TYPE_RECIPIENT


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
            [ThreemaNotifyEntity(entry.runtime_data, subentry)],
            config_subentry_id=subentry_id,
        )


class ThreemaNotifyEntity(NotifyEntity):
    """Notify entity for sending messages to a Threema recipient."""

    _attr_has_entity_name = True
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        client: ThreemaAPIClient,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the notify entity."""
        self._client = client
        self._recipient_id: str = subentry.data[CONF_RECIPIENT]

        self._attr_unique_id = f"{client.gateway_id}_{self._recipient_id}"
        self._attr_name = subentry.title
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Threema",
            identifiers={(DOMAIN, client.gateway_id)},
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the configured Threema recipient."""
        text = f"*{title}*\n{message}" if title else message
        try:
            await self._client.send_text_message(self._recipient_id, text)
        except ThreemaAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ThreemaSendError, ThreemaConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_error",
                translation_placeholders={"error": str(err)},
            ) from err
