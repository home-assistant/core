"""Event entities for the WeatherFlow integration."""

from __future__ import annotations

from pyweatherflowudp.device import EVENT_RAIN_START, EVENT_STRIKE, WeatherFlowDevice

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER, format_dispatch_call

RAIN_START_DESCRIPTION = EventEntityDescription(
    key="rain_start_event",
    translation_key="rain_start_event",
    name="Rain start",
    event_types=["rain_start"],
)

LIGHTNING_STRIKE_DESCRIPTION = EventEntityDescription(
    key="lightning_strike_event",
    translation_key="lightning_strike_event",
    name="Lightning strike",
    event_types=["strike"],
)


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
            [
                WeatherFlowRainStartEventEntity(device),
                WeatherFlowLightningStrikeEventEntity(device),
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_dispatch_call(config_entry),
            async_add_events,
        )
    )


class _WeatherFlowEventEntity(EventEntity):
    """Base WeatherFlow event entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        device: WeatherFlowDevice,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the base WeatherFlow event entity."""

        self.device = device
        self.entity_description = description

        translation_key = description.translation_key
        self._attr_translation_key = (
            translation_key if isinstance(translation_key, str) else None
        )
        name = description.name
        self._attr_name = name if isinstance(name, str) else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            manufacturer="WeatherFlow",
            model=device.model,
            name=device.serial_number,
            sw_version=device.firmware_revision,
        )
        self._attr_unique_id = f"{device.serial_number}_{description.key}"
        self._attr_entity_id = (
            f"event.weatherflow_{device.serial_number}_{description.key}"
        )


class WeatherFlowRainStartEventEntity(_WeatherFlowEventEntity):
    """Event entity that fires when rain starts."""

    entity_description = RAIN_START_DESCRIPTION
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, device: WeatherFlowDevice) -> None:
        """Initialize a rain start event entity."""

        super().__init__(device, RAIN_START_DESCRIPTION)

    async def async_added_to_hass(self) -> None:
        """Subscribe to rain start events."""
        self.async_on_remove(self.device.on(EVENT_RAIN_START, self._handle_event))

    @callback
    def _handle_event(self, event) -> None:
        self._trigger_event(
            "rain_start",
            {},
        )
        self.async_write_ha_state()


class WeatherFlowLightningStrikeEventEntity(_WeatherFlowEventEntity):
    """Event entity that fires when lightning strikes."""

    entity_description = LIGHTNING_STRIKE_DESCRIPTION
    _attr_icon = "mdi:weather-lightning"

    def __init__(self, device: WeatherFlowDevice) -> None:
        """Initialize a lightning strike event entity."""

        super().__init__(device, LIGHTNING_STRIKE_DESCRIPTION)

    async def async_added_to_hass(self) -> None:
        """Subscribe to lightning strike events."""
        self.async_on_remove(self.device.on(EVENT_STRIKE, self._handle_event))

    @callback
    def _handle_event(self, event) -> None:
        self._trigger_event(
            "strike",
            {},
        )
        self.async_write_ha_state()
