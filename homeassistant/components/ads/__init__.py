"""Support for Automation Device Specification (ADS)."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ADS_TYPE,
    CONF_ADS_VALUE,
    CONF_ADS_VAR,
    DATA_ADS,
    DOMAIN,
    SERVICE_WRITE_DATA_BY_NAME,
    AdsType,
)
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)

ADS_TYPEMAP = {
    AdsType.BOOL: pyads.PLCTYPE_BOOL,
    AdsType.BYTE: pyads.PLCTYPE_BYTE,
    AdsType.INT: pyads.PLCTYPE_INT,
    AdsType.UINT: pyads.PLCTYPE_UINT,
    AdsType.SINT: pyads.PLCTYPE_SINT,
    AdsType.USINT: pyads.PLCTYPE_USINT,
    AdsType.DINT: pyads.PLCTYPE_DINT,
    AdsType.UDINT: pyads.PLCTYPE_UDINT,
    AdsType.WORD: pyads.PLCTYPE_WORD,
    AdsType.DWORD: pyads.PLCTYPE_DWORD,
    AdsType.REAL: pyads.PLCTYPE_REAL,
    AdsType.LREAL: pyads.PLCTYPE_LREAL,
    AdsType.STRING: pyads.PLCTYPE_STRING,
    AdsType.TIME: pyads.PLCTYPE_TIME,
    AdsType.DATE: pyads.PLCTYPE_DATE,
    AdsType.DATE_AND_TIME: pyads.PLCTYPE_DT,
    AdsType.TOD: pyads.PLCTYPE_TOD,
}


# YAML Configuration Schema (to allow setup from configuration.yaml)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Required(CONF_ADS_TYPE): vol.In(AdsType),
        vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component with optional YAML configuration."""

    # Check if configuration exists in YAML and set it up accordingly
    if DOMAIN not in config:
        return True  # Skip setup if no YAML configuration is present

    conf = config[DOMAIN]
    return await async_setup_ads_integration(hass, conf)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ADS from a config entry created via the ConfigFlow."""
    return await async_setup_ads_integration(hass, entry.data)


async def async_setup_ads_integration(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> bool:
    """Set up common components for both YAML and config entry setups."""
    net_id = config[CONF_DEVICE]
    ip_address = config.get(CONF_IP_ADDRESS)
    port = config[CONF_PORT]

    try:
        client = pyads.Connection(net_id, port, ip_address)
        ads = AdsHub(client)
    except pyads.ADSError:
        _LOGGER.error(
            "Could not connect to ADS host (netid=%s, ip=%s, port=%s)",
            net_id,
            ip_address,
            port,
        )
        return False

    hass.data[DATA_ADS] = ads
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    async def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: int = call.data[CONF_ADS_VALUE]

        _LOGGER.debug(
            "Writing data for ADS variable: %s, type: %s, value: %s",
            ads_var,
            ads_type,
            value,
        )

        # Get the AdsHub instance from hass.data
        ads_hub = hass.data.get(DATA_ADS)
        if not ads_hub:
            _LOGGER.error("No ADS Hub instance found in hass.data")
            return
        try:
            _LOGGER.debug(
                "Calling write_by_name with '%s': '%s' : '%s'", ads_var, value, ads_type
            )
            ads_hub.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error("Error writing to ADS variable '%s': %s", ads_var, err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )
    _LOGGER.debug("Registered service: %s", SERVICE_WRITE_DATA_BY_NAME)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the ADS entry."""
    _LOGGER.debug("Unloading ADS entry: %s", entry.entry_id)

    # Ensure DATA_ADS exists in hass.data, if not log and return False
    ads_data = hass.data.get(DATA_ADS)
    if ads_data is None:
        _LOGGER.warning(
            "No ADS data found in hass.data during unload for entry: %s", entry.entry_id
        )
        return False

    _LOGGER.debug("Found ADS data, proceeding to shutdown")

    # Check if ads_data has a shutdown method and call it if it does
    shutdown_method = getattr(ads_data, "shutdown", None)
    if callable(shutdown_method):
        try:
            if asyncio.iscoroutinefunction(shutdown_method):
                await shutdown_method()  # Await if shutdown is asynchronous
            else:
                shutdown_method()  # Otherwise, call directly if it's synchronous
            _LOGGER.debug("ADS connection shut down successfully")
        except pyads.ADSError as e:
            _LOGGER.error("Error during shutdown of ADS connection: %s", e)
            return False
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Unexpected error during shutdown: %s", e)
            return False
    else:
        _LOGGER.warning(
            "No shutdown method available on ADS data for entry: %s; proceeding with unload",
            entry.entry_id,
        )

    # Clean up the data by deleting it from hass.data
    del hass.data[DATA_ADS]
    return True  # Return True if the unload was successful
