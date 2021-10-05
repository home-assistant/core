"""This integration provides support for Stookalert Binary Sensor."""
from __future__ import annotations

from datetime import timedelta

import stookalert
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SCAN_INTERVAL = timedelta(minutes=60)
CONF_PROVINCE = "province"
DEFAULT_NAME = "Stookalert"
ATTRIBUTION = "Data provided by rivm.nl"
PROVINCES = [
    "Drenthe",
    "Flevoland",
    "Friesland",
    "Gelderland",
    "Groningen",
    "Limburg",
    "Noord-Brabant",
    "Noord-Holland",
    "Overijssel",
    "Utrecht",
    "Zeeland",
    "Zuid-Holland",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PROVINCE): vol.In(PROVINCES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Stookalert binary sensor platform."""
    api_handler = stookalert.stookalert(config[CONF_PROVINCE])
    add_entities(
        [StookalertBinarySensor(config[CONF_NAME], api_handler)], update_before_add=True
    )


class StookalertBinarySensor(BinarySensorEntity):
    """An implementation of RIVM Stookalert."""

    _attr_device_class = DEVICE_CLASS_SAFETY

    def __init__(self, name: str, api_handler: stookalert.stookalert) -> None:
        """Initialize a Stookalert device."""
        self._api_handler = api_handler
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_name = name

    def update(self) -> None:
        """Update the data from the Stookalert handler."""
        self._api_handler.get_alerts()
        self._attr_is_on = self._api_handler.state == 1
        if self._api_handler.last_updated:
            self._attr_extra_state_attributes.update(
                last_updated=self._api_handler.last_updated.isoformat()
            )
