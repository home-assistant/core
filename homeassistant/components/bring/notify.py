"""Notify platform for the Bring! integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bring_api.exceptions import BringRequestException
from bring_api.types import BringNotificationType
import voluptuous as vol

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import ATTR_ITEM_NAME, ATTR_NOTIFICATION_TYPE, MANUFACTURER, SERVICE_NAME
from .coordinator import BringData, BringDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bring notify entity platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        BringNotify(coordinator, bring_list=bring_list, entry=config_entry)
        for bring_list in coordinator.data.values()
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "send_message",
        make_entity_service_schema(
            {
                vol.Required(ATTR_NOTIFICATION_TYPE): vol.All(
                    vol.Upper, cv.enum(BringNotificationType)
                ),
                vol.Optional(ATTR_ITEM_NAME): cv.string,
            }
        ),
        "async_send_bring_message",
    )


class BringNotify(NotifyEntity):
    """Representation of a Bring notify entity."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Notify entity."""
        if TYPE_CHECKING:
            assert entry.unique_id

        self.coordinator = coordinator
        self._list_uuid = bring_list["listUuid"]
        self._attr_name = bring_list["name"]

        self._attr_unique_id = f"{entry.unique_id}_{self._list_uuid}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=SERVICE_NAME,
        )

    async def async_send_message(self, message: str) -> None:
        """Implement for base class.

        Cannot be overridden with custom fields,
        so calling async_send_bring_message instead.
        """

    async def async_send_bring_message(
        self,
        *,
        message: str | None = None,
        notification_type: BringNotificationType,
    ) -> None:
        """Send a push notification to members of a To-Do list."""

        try:
            await self.coordinator.bring.notify(
                self._list_uuid, notification_type, message
            )
        except BringRequestException as e:
            raise HomeAssistantError(
                "Unable to send push notification for bring"
            ) from e
        except ValueError as e:
            raise HomeAssistantError(
                "Item name is required for Breaking news notification"
            ) from e
        else:
            await super()._async_send_message(message=message or "item_name")
