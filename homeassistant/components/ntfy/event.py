"""Event platform for ntfy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiontfy import Event, Notification
from yarl import URL

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NtfyConfigEntry
from .const import CONF_TOPIC, DOMAIN, NTFY_EVENT
from .coordinator import NtfyDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    coordinator = config_entry.runtime_data

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [NtfyEventEntity(coordinator, subentry)], config_subentry_id=subentry_id
        )


class NtfyEventEntity(CoordinatorEntity[NtfyDataUpdateCoordinator], EventEntity):
    """An event entity."""

    _attr_has_entity_name = True
    entity_description = EventEntityDescription(
        key="subscribe",
        translation_key="subscribe",
        name=None,
        has_entity_name=True,
        event_types=["triggered"],
    )

    def __init__(
        self,
        coordinator: NtfyDataUpdateCoordinator,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        self.topic = subentry.data[CONF_TOPIC]
        super().__init__(coordinator, context=self.topic)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{subentry.subentry_id}_{self.entity_description.key}"

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            model_id=coordinator.config_entry.data[CONF_URL],
            name=self.topic,
            configuration_url=URL(coordinator.config_entry.data[CONF_URL]) / self.topic,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{subentry.subentry_id}")
            },
        )

    @callback
    def _async_handle_event(self, notification: Notification) -> None:
        """Handle the ntfy event."""
        if notification.topic == self.topic and notification.event is Event.MESSAGE:
            event = (
                f"{notification.title}: {notification.message}"
                if notification.title
                else notification.message
            )
            if TYPE_CHECKING:
                assert event
            self._attr_event_types = [event]
            self._trigger_event(event, notification.to_dict())
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register event listener."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{NTFY_EVENT}_{self.coordinator.config_entry.entry_id}",
                self._async_handle_event,
            )
        )
        await self.coordinator.async_request_refresh()
        return await super().async_added_to_hass()

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.state_attributes.get("icon") or super().entity_picture
