"""The Legrand RFLC integration light platform."""

from collections.abc import Mapping
from typing import Final

import lc7001.aio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Legrand RFLC integration light platform.

    Adds a Dimmer or Switch for each like zone on this entry's hub.
    """
    hub = hass.data[DOMAIN][entry.entry_id]
    entry_unique_id = entry.unique_id

    async def zones(message: Mapping) -> None:
        async def zone(message: Mapping) -> None:
            zid = message[hub.ZID]
            properties = message[hub.PROPERTY_LIST]
            device_type = properties[hub.DEVICE_TYPE]
            if device_type == hub.DIMMER:
                async_add_entities(
                    [LegrandRflcDimmer(entry_unique_id, hub, zid, properties)], False
                )
            elif device_type == hub.SWITCH:
                async_add_entities(
                    [LegrandRflcSwitch(entry_unique_id, hub, zid, properties)], False
                )

        hub.StatusError(message).raise_if()
        for item in message[hub.ZONE_LIST]:
            await hub.handle_send(
                zone, hub.compose_report_zone_properties(item[hub.ZID])
            )

    await hub.handle_send(zones, hub.compose_list_zones())


class LegrandRflcSwitch(LightEntity):
    """A Legrand RFLC Switch is based on a Home Assistant LightEntity."""

    _attr_should_poll = False

    _attr_color_mode = COLOR_MODE_ONOFF
    _attr_supported_color_modes = {COLOR_MODE_ONOFF}

    def __init__(
        self, entry_unique_id, hub: lc7001.aio.Hub, zid: int, properties: Mapping
    ):
        """Initialize the Legrand RFLC Switch."""
        self._hub = hub
        self._zid = zid
        self._attr_unique_id = f"{entry_unique_id}:{zid}"
        self._attr_name = properties[hub.NAME]
        self._attr_is_on = properties[hub.POWER]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Legrand",
            model=properties[hub.DEVICE_TYPE],
            name=self._attr_name,
            via_device=(DOMAIN, entry_unique_id),
        )

    @property
    def available(self) -> bool:
        """Yes, if we can communicate with its hub."""
        return self._hub.connected and self._hub.authenticated

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        hub = self._hub
        hub.on(
            f"{hub.EVENT_ZONE_PROPERTIES_CHANGED}:{self._zid}",
            self._zone_properties_changed,
        )
        hub.on(hub.EVENT_CONNECTED, self._available)
        hub.on(hub.EVENT_DISCONNECTED, self._available)
        hub.on(hub.EVENT_AUTHENTICATED, self._available)
        hub.on(hub.EVENT_UNAUTHENTICATED, self._available)

    async def _available(self) -> None:
        self.async_write_ha_state()

    def _zone_properties_changed_switch(self, message: Mapping) -> None:
        hub = self._hub
        if hub.PROPERTY_LIST in message:
            properties = message[hub.PROPERTY_LIST]
            if hub.POWER in properties:
                self._attr_is_on = properties[hub.POWER]

    async def _zone_properties_changed(self, message: Mapping) -> None:
        self._zone_properties_changed_switch(message)
        self.async_write_ha_state()

    async def _async_switch_handle(self, message: Mapping):
        self._hub.StatusError(message).raise_if()

    async def _async_switch(self, power: bool) -> None:
        await self._hub.handle_send(
            self._async_switch_handle,
            self._hub.compose_set_zone_properties(self._zid, power=power),
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        await self._async_switch(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        await self._async_switch(False)


class LegrandRflcDimmer(LegrandRflcSwitch):
    """A Legrand RFLC Dimmer is based on a Legrand RFLC Switch."""

    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
    _attr_supported_features = SUPPORT_TRANSITION

    @staticmethod
    def _normalize(value: int, ceiling: int) -> float:
        """Normalize [0, ceiling] to [0.0, 1.0]."""
        return value / ceiling

    @staticmethod
    def _quantize(value: float, ceiling: int) -> int:
        """Quantize [0.0, 1.0] to [0, ceiling]."""
        return round(value * ceiling)

    # dimming ceilings for homeassistant and us (LC7001)
    HA: Final[int] = 255
    US: Final[int] = 100

    @staticmethod
    def _to_ha(value: int) -> int:
        return LegrandRflcDimmer._quantize(
            LegrandRflcDimmer._normalize(value, LegrandRflcDimmer.US),
            LegrandRflcDimmer.HA,
        )

    @staticmethod
    def _from_ha(value) -> int:
        return LegrandRflcDimmer._quantize(
            LegrandRflcDimmer._normalize(value, LegrandRflcDimmer.HA),
            LegrandRflcDimmer.US,
        )

    def __init__(
        self, entry_unique_id, hub: lc7001.aio.Hub, zid: int, properties: Mapping
    ):
        """Initialize the Legrand RFLC Dimmer."""
        super().__init__(entry_unique_id, hub, zid, properties)
        self._attr_brightness = self._to_ha(properties[hub.POWER_LEVEL])

    async def _zone_properties_changed(self, message: Mapping) -> None:
        self._zone_properties_changed_switch(message)
        hub = self._hub
        if hub.PROPERTY_LIST in message:
            properties = message[hub.PROPERTY_LIST]
            if hub.POWER_LEVEL in properties:
                self._attr_brightness = self._to_ha(properties[hub.POWER_LEVEL])
        self.async_write_ha_state()

    async def _async_dimmer(self, power: bool, **kwargs) -> None:
        hub = self._hub

        async def handle(message: Mapping) -> None:
            hub.StatusError(message).raise_if()

        properties: dict = {"power": power}
        if ATTR_BRIGHTNESS in kwargs:
            brightness = self._from_ha(kwargs[ATTR_BRIGHTNESS])
            properties["power_level"] = brightness
        else:
            if power:
                brightness = self._from_ha(self.brightness)
            else:
                brightness = 0
        if ATTR_TRANSITION in kwargs:
            change = abs(brightness - self._from_ha(self.brightness))
            properties["ramp_rate"] = min(
                max(int(change / kwargs[ATTR_TRANSITION]), 1), 100
            )
        await hub.handle_send(
            handle,
            hub.compose_set_zone_properties(self._zid, **properties),
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn dimmer on."""
        await self._async_dimmer(True, **kwargs)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn dimmer off."""
        await self._async_dimmer(False, **kwargs)
