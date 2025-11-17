"""Event entities for the WeatherFlow integration."""

from __future__ import annotations

from dataclasses import dataclass

from pyweatherflowudp.device import EVENT_RAIN_START, EVENT_STRIKE, WeatherFlowDevice

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER, format_dispatch_call


@dataclass(frozen=True, kw_only=True)
class WeatherFlowEventEntityDescription(EventEntityDescription):
    """Describes a WeatherFlow event entity."""

    wf_event: str
    event_types: list[str]


EVENT_DESCRIPTIONS: list[WeatherFlowEventEntityDescription] = [
    WeatherFlowEventEntityDescription(
        key="precip_start_event",
        translation_key="precip_start_event",
        event_types=["precipitation_start"],
        wf_event=EVENT_RAIN_START,
    ),
    WeatherFlowEventEntityDescription(
        key="lightning_strike_event",
        translation_key="lightning_strike_event",
        event_types=["lightning_strike"],
        wf_event=EVENT_STRIKE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WeatherFlow event entities using config entry."""

    @callback
    def async_add_events(device: WeatherFlowDevice) -> None:
        LOGGER.debug("Adding events for %s", device)
        async_add_entities(
            WeatherFlowEventEntity(device, description)
            for description in EVENT_DESCRIPTIONS
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_dispatch_call(config_entry),
            async_add_events,
        )
    )


class WeatherFlowEventEntity(EventEntity):
    """Generic WeatherFlow event entity."""

    _attr_has_entity_name = True
    entity_description: WeatherFlowEventEntityDescription

    def __init__(
        self,
        device: WeatherFlowDevice,
        description: WeatherFlowEventEntityDescription,
    ) -> None:
        """Initialize the WeatherFlow event entity."""

        self.device = device
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            manufacturer="WeatherFlow",
            model=device.model,
            name=device.serial_number,
            sw_version=device.firmware_revision,
        )
        self._attr_unique_id = f"{device.serial_number}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to the configured WeatherFlow device event."""
        self.async_on_remove(
            self.device.on(self.entity_description.wf_event, self._handle_event)
        )

    @callback
    def _handle_event(self, event) -> None:
        self._trigger_event(
            self.entity_description.event_types[0],
            {},
        )
        self.async_write_ha_state()
