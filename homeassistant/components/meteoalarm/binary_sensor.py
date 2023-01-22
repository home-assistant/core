"""Binary Sensor for MeteoAlarm.eu."""
from __future__ import annotations

from datetime import timedelta
import logging

from meteoalertapi import Meteoalert
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Information provided by MeteoAlarm"

CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"
CONF_PROVINCE = "province"

DEFAULT_NAME = "meteoalarm"

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COUNTRY): cv.string,
        vol.Required(CONF_PROVINCE): cv.string,
        vol.Optional(CONF_LANGUAGE, default="en"): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MeteoAlarm binary sensor platform."""

    country = config[CONF_COUNTRY]
    province = config[CONF_PROVINCE]
    language = config[CONF_LANGUAGE]
    name = config[CONF_NAME]

    try:
        api = Meteoalert(country, province, language)
    except KeyError:
        _LOGGER.error("Wrong country digits or province name")
        return

    add_entities([MeteoAlertBinarySensor(api, name)], True)


class MeteoAlertBinarySensor(BinarySensorEntity):
    """Representation of a MeteoAlert binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, api, name):
        """Initialize the MeteoAlert binary sensor."""
        self._attr_name = name
        self._api = api

    def update(self) -> None:
        """Update device state."""
        self._attr_extra_state_attributes = {}
        self._attr_is_on = False

        if alert := self._api.get_alert():
            expiration_date = dt_util.parse_datetime(alert["expires"])

            if expiration_date is not None and expiration_date > dt_util.utcnow():
                self._attr_extra_state_attributes = alert
                self._attr_is_on = True
