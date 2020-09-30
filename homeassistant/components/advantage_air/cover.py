"""Cover platform for Advantage Air integration."""

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DAMPER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import STATE_OPEN
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_CLOSE


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup isn't required."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir cover platform."""

    instance = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for _, ac_key in enumerate(instance["coordinator"].data["aircons"]):
        for _, zone_key in enumerate(
            instance["coordinator"].data["aircons"][ac_key]["zones"]
        ):
            # Only add zone vent controls when zone in vent control mode.
            if (
                instance["coordinator"].data["aircons"][ac_key]["zones"][zone_key][
                    "type"
                ]
                == 0
            ):
                entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
    async_add_entities(entities)
    return True


class AdvantageAirZoneVent(CoordinatorEntity, CoverEntity):
    """Advantage Air Climate Class."""

    def __init__(self, instance, ac_key, zone_key):
        """Initialize the Advantage Air Zone Vent cover entity."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_key = ac_key
        self.zone_key = zone_key

    @property
    def name(self):
        """Return the name."""
        return f'{self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]["name"]} Vent'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}'

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_DAMPER

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """Return if vent is fully closed."""
        return (
            self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
                "state"
            ]
            == STATE_CLOSE
        )

    @property
    def is_opening(self):
        """Platform is unaware of opening state."""
        return False

    @property
    def is_closing(self):
        """Platform is unaware of closing state."""
        return False

    @property
    def current_cover_position(self):
        """Return vents current position as a percentage."""
        if (
            self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
                "state"
            ]
            == STATE_OPEN
        ):
            return self.coordinator.data["aircons"][self.ac_key]["zones"][
                self.zone_key
            ]["value"]
        return 0

    @property
    def icon(self):
        """Return vent icon."""
        return ["mdi:fan-off", "mdi:fan"][
            self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
                "state"
            ]
            == STATE_OPEN
        ]

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def async_open_cover(self, **kwargs):
        """Fully open zone vent."""
        await self.async_change(
            {
                self.ac_key: {
                    "zones": {self.zone_key: {"state": STATE_OPEN, "value": 100}}
                }
            }
        )

    async def async_close_cover(self, **kwargs):
        """Fully close zone vent."""
        await self.async_change(
            {self.ac_key: {"zones": {self.zone_key: {"state": STATE_CLOSE}}}}
        )

    async def async_set_cover_position(self, **kwargs):
        """Change vent position."""
        position = round(kwargs.get(ATTR_POSITION) / 5) * 5
        if position == 0:
            await self.async_change(
                {self.ac_key: {"zones": {self.zone_key: {"state": STATE_CLOSE}}}}
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {
                            self.zone_key: {
                                "state": STATE_OPEN,
                                "value": position,
                            }
                        }
                    }
                }
            )
