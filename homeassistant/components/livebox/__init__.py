import ipaddress
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, 
    CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import (
    config_validation as cv, device_registry as dr)
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN, DEFAULT_USERNAME, DEFAULT_HOST, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
  {
    DOMAIN: vol.Schema(
      {
        # Validate as IP address and then convert back to a string.
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): 
            vol.All(ipaddress.ip_address, cv.string),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
      }
    )
  },
  extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):
    """Set up configured Livebox."""
    return True

async def async_setup_entry(hass, entry):
    """Set up Livebox as config entry."""
    from aiosysbus import Sysbus
    from aiosysbus.exceptions import HttpRequestError
    box = Sysbus()
    try:
        await box.open(
            host=entry.data['host'],
            port=entry.data['port'],
            username=entry.data['username'], 
            password=entry.data['password'])
    except HttpRequestError:
        _LOGGER.exception('Http Request error to Livebox')
    except CannotConnect:
        _LOGGER.exception('Failed to connect to Livebox')
    except AuthenticationRequired:
        _LOGGER.exception('User or password incorrect')

    hass.data[DOMAIN] = box
    config = (await box.system.get_deviceinfo())['status']

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, config['SerialNumber'])
        },
        manufacturer = config['Manufacturer'],
        name = config['ProductClass'],
        model = config['ModelName'],
        sw_version = config['SoftwareVersion'],
    )
        
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        async_load_platform(hass, "device_tracker", DOMAIN, {}, entry)
    )
        
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    box = hass.data[DOMAIN]
    await box.close()
    
    return True
