"""The ViCare integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device
import voluptuous as vol

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_CIRCUIT,
    CONF_HEATING_TYPE,
    DEFAULT_HEATING_TYPE,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    PLATFORMS,
    VICARE_API,
    VICARE_CIRCUITS,
    VICARE_DEVICE_CONFIG,
    VICARE_NAME,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass()
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[Device], bool]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_CIRCUIT),
            vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=60): vol.All(
                        cv.time_period, lambda value: value.total_seconds()
                    ),
                    vol.Optional(
                        CONF_CIRCUIT
                    ): int,  # Ignored: All circuits are now supported. Will be removed when switching to Setup via UI.
                    vol.Optional(CONF_NAME, default="ViCare"): cv.string,
                    vol.Optional(
                        CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE
                    ): cv.enum(HeatingType),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Create the ViCare component."""
    conf = config[DOMAIN]
    params = {"token_file": hass.config.path(STORAGE_DIR, "vicare_token.save")}

    params["cacheDuration"] = conf.get(CONF_SCAN_INTERVAL)
    params["client_id"] = conf.get(CONF_CLIENT_ID)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VICARE_NAME] = conf[CONF_NAME]
    setup_vicare_api(hass, conf, hass.data[DOMAIN])

    hass.data[DOMAIN][CONF_HEATING_TYPE] = conf[CONF_HEATING_TYPE]

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


def setup_vicare_api(hass, conf, entity_data):
    """Set up PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(conf[CONF_SCAN_INTERVAL])
    vicare_api.initWithCredentials(
        conf[CONF_USERNAME],
        conf[CONF_PASSWORD],
        conf[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, "vicare_token.save"),
    )

    device = vicare_api.devices[0]
    for device in vicare_api.devices:
        _LOGGER.info(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )
    entity_data[VICARE_DEVICE_CONFIG] = device
    entity_data[VICARE_API] = getattr(
        device, HEATING_TYPE_TO_CREATOR_METHOD[conf[CONF_HEATING_TYPE]]
    )()
    entity_data[VICARE_CIRCUITS] = entity_data[VICARE_API].circuits
