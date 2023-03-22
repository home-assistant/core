"""Support for Hydrawise cloud switches."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DATA_HYDRAWISE,
    DEFAULT_WATERING_TIME,
    HydrawiseEntity,
)

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        name="Automatic Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        name="Manual Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SWITCH_KEYS): vol.All(
            cv.ensure_list, [vol.In(SWITCH_KEYS)]
        ),
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME): vol.All(
            vol.In(ALLOWED_WATERING_TIME)
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    default_watering_timer = config[CONF_WATERING_TIME]

    entities = [
        HydrawiseSwitch(zone, description, default_watering_timer)
        for zone in hydrawise.relays
        for description in SWITCH_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self, data, description: SwitchEntityDescription, default_watering_timer
    ) -> None:
        """Initialize a switch for Hydrawise device."""
        super().__init__(data, description)
        self._default_watering_timer = default_watering_timer

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(
                self._default_watering_timer, relay_data
            )
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(0, relay_data)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(0, relay_data)
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(365, relay_data)

    def update(self) -> None:
        """Update device state."""
        relay_data = self.data["relay"] - 1
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise switch: %s", self.name)
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = mydata.relays[relay_data]["timestr"] == "Now"
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = (mydata.relays[relay_data]["timestr"] != "") and (
                mydata.relays[relay_data]["timestr"] != "Now"
            )
