"""Cover platform for Advantage Air integration."""

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdvantageAirDataConfigEntry
from .const import ADVANTAGE_AIR_STATE_CLOSE, ADVANTAGE_AIR_STATE_OPEN
from .entity import AdvantageAirThingEntity, AdvantageAirZoneEntity
from .models import AdvantageAirData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdvantageAirDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir cover platform."""

    instance = config_entry.runtime_data

    entities: list[CoverEntity] = []
    if aircons := instance.coordinator.data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            for zone_key, zone in ac_device["zones"].items():
                # Only add zone vent controls when zone in vent control mode.
                if zone["type"] == 0:
                    entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
    if things := instance.coordinator.data.get("myThings"):
        for thing in things["things"].values():
            if thing["channelDipState"] in [1, 2]:  # 1 = "Blind", 2 = "Blind 2"
                entities.append(
                    AdvantageAirThingCover(instance, thing, CoverDeviceClass.BLIND)
                )
            elif thing["channelDipState"] == 3:  # 3 = "Garage door"
                entities.append(
                    AdvantageAirThingCover(instance, thing, CoverDeviceClass.GARAGE)
                )
    async_add_entities(entities)


class AdvantageAirZoneVent(AdvantageAirZoneEntity, CoverEntity):
    """Advantage Air Zone Vent."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone Vent."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = self._zone["name"]

    @property
    def is_closed(self) -> bool:
        """Return if vent is fully closed."""
        return self._zone["state"] == ADVANTAGE_AIR_STATE_CLOSE

    @property
    def current_cover_position(self) -> int:
        """Return vents current position as a percentage."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return self._zone["value"]
        return 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Fully open zone vent."""
        await self.async_update_zone(
            {"state": ADVANTAGE_AIR_STATE_OPEN, "value": 100},
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close zone vent."""
        await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_CLOSE})

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Change vent position."""
        position = round(kwargs[ATTR_POSITION] / 5) * 5
        if position == 0:
            await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_CLOSE})
        else:
            await self.async_update_zone(
                {
                    "state": ADVANTAGE_AIR_STATE_OPEN,
                    "value": position,
                }
            )


class AdvantageAirThingCover(AdvantageAirThingEntity, CoverEntity):
    """Representation of Advantage Air Cover controlled by MyPlace."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        instance: AdvantageAirData,
        thing: dict[str, Any],
        device_class: CoverDeviceClass,
    ) -> None:
        """Initialize an Advantage Air Things Cover."""
        super().__init__(instance, thing)
        self._attr_device_class = device_class

    @property
    def is_closed(self) -> bool:
        """Return if cover is fully closed."""
        return self._data["value"] == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Fully open zone vent."""
        return await self.async_turn_on()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close zone vent."""
        return await self.async_turn_off()
