"""Support for TP-Link Omada Controller."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, ATTR_ENTITY_ID,
    CONF_HOST)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_WIFIACRULE,
    SERVICE_WIFIACRULE_ATTR_RULE,
)
from .common import OmadaData


LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the TP-Link Omada integration."""
    hass.data.setdefault(DOMAIN, {})

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up TP-Link Omada via a config entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]

    omada_controller = OmadaData(hass, entry)
    await omada_controller.async_update()
    hass.data[DOMAIN][name] = omada_controller

    try:
        omada_controller = OmadaData(hass, entry)
        await omada_controller.async_update()
        hass.data[DOMAIN][name] = omada_controller
    except Exception as exp:
        LOGGER.warning("Failed to connect: %s", exp)
        raise ConfigEntryNotReady

    LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, DT_DOMAIN)
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_WIFIACRULE,
        omada_controller.set_accesscontrolerrule_service_handler,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                vol.Optional(SERVICE_WIFIACRULE_ATTR_RULE): str
            }
        ),
    )

    return True
