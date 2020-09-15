from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DAMPER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN

from .const import ADVANTAGE_AIR_ZONE_CLOSE, ADVANTAGE_AIR_ZONE_OPEN, DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyAir cover platform."""

    my = hass.data[DOMAIN][config_entry.data.get("url")]

    entities = []
    for _, acx in enumerate(my["coordinator"].data["aircons"]):
        for _, zx in enumerate(my["coordinator"].data["aircons"][acx]["zones"]):
            # Only add zone damper controls when zone in damper control.
            if my["coordinator"].data["aircons"][acx]["zones"][zx]["type"] == 0:
                entities.append(MyAirZoneDamper(my, acx, zx))
    async_add_entities(entities)
    return True


class MyAirZoneDamper(CoverEntity):
    """MyAir Zone Damper"""

    def __init__(self, my, acx, zx):
        self.coordinator = my["coordinator"]
        self.async_set_data = my["async_set_data"]
        self.device = my["device"]
        self.acx = acx
        self.zx = zx

    @property
    def name(self):
        return f"{self.coordinator.data['aircons'][self.acx]['zones'][self.zx]['name']} Vent"

    @property
    def unique_id(self):
        return f"{self.coordinator.data['system']['rid']}-{self.acx}-{self.zx}-cover"

    @property
    def device_class(self):
        return DEVICE_CLASS_DAMPER

    @property
    def supported_features(self):
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        return (
            self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["state"]
            == ADVANTAGE_AIR_ZONE_CLOSE
        )

    @property
    def is_opening(self):
        return False

    @property
    def is_closing(self):
        return False

    @property
    def current_cover_position(self):
        if (
            self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["state"]
            == ADVANTAGE_AIR_ZONE_OPEN
        ):
            return self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["value"]
        else:
            return 0

    @property
    def icon(self):
        return ["mdi:fan-off", "mdi:fan"][
            self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["state"]
            == ADVANTAGE_AIR_ZONE_OPEN
        ]

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return self.device

    async def async_open_cover(self, **kwargs):
        await self.async_set_data(
            {
                self.acx: {
                    "zones": {self.zx: {"state": ADVANTAGE_AIR_ZONE_OPEN, "value": 100}}
                }
            }
        )
        # await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs):
        await self.async_set_data(
            {self.acx: {"zones": {self.zx: {"state": ADVANTAGE_AIR_ZONE_CLOSE}}}}
        )
        # await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs):
        position = round(kwargs.get(ATTR_POSITION) / 5) * 5
        if position == 0:
            await self.async_set_data(
                {self.acx: {"zones": {self.zx: {"state": ADVANTAGE_AIR_ZONE_CLOSE}}}}
            )
        else:
            await self.async_set_data(
                {
                    self.acx: {
                        "zones": {
                            self.zx: {
                                "state": ADVANTAGE_AIR_ZONE_OPEN,
                                "value": position,
                            }
                        }
                    }
                }
            )

        # await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self.coordinator.async_request_refresh()
