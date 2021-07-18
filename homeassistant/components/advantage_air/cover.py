"""Cover platform for Advantage Air integration."""

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DAMPER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.core import callback

from .const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
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

    _attr_device_class = DEVICE_CLASS_DAMPER
    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Cover Class."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]}'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}'
        )

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._attr_is_closed = self._zone["state"] == ADVANTAGE_AIR_STATE_CLOSE
        self._attr_current_cover_position = 0
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            self._attr_current_cover_position = self._zone["value"]
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
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

    async def async_close_cover(self, **kwargs):
        """Fully close zone vent."""
        await self.async_change(
            {
                self.ac_key: {
                    "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_CLOSE}}
                }
            }
        )

    async def async_set_cover_position(self, **kwargs):
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
