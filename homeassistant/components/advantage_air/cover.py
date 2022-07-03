"""Cover platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir cover platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        for zone_key, zone in ac_device["zones"].items():
            # Only add zone vent controls when zone in vent control mode.
            if zone["type"] == 0:
                entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
    async_add_entities(entities)


class AdvantageAirZoneVent(AdvantageAirEntity, CoverEntity):
    """Advantage Air Cover Class."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Cover Class."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]}'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}'
        )

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
        await self.async_change(
            {
                self.ac_key: {
                    "zones": {
                        self.zone_key: {"state": ADVANTAGE_AIR_STATE_OPEN, "value": 100}
                    }
                }
            }
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close zone vent."""
        await self.async_change(
            {
                self.ac_key: {
                    "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_CLOSE}}
                }
            }
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Change vent position."""
        position = round(kwargs[ATTR_POSITION] / 5) * 5
        if position == 0:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_CLOSE}}
                    }
                }
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {
                            self.zone_key: {
                                "state": ADVANTAGE_AIR_STATE_OPEN,
                                "value": position,
                            }
                        }
                    }
                }
            )
