"""Services for the Homematic integration."""

import logging

import probatio

from homeassistant.const import ATTR_MODE, ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util.async_ import run_callback_threadsafe

from .const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE,
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    ATTR_RX_MODE,
    DATA_HOMEMATIC,
    DOMAIN,
    SERVICE_PUT_PARAMSET,
    SERVICE_RECONNECT,
    SERVICE_SET_INSTALL_MODE,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_SERVICE_RECONNECT = probatio.Schema({})

SCHEMA_SERVICE_SET_INSTALL_MODE = probatio.Schema(
    {
        probatio.Required(ATTR_INTERFACE): cv.string,
        probatio.Optional(ATTR_TIME, default=60): cv.positive_int,
        probatio.Optional(ATTR_MODE, default=1): probatio.All(
            probatio.Coerce(int), probatio.In([1, 2])
        ),
        probatio.Optional(ATTR_ADDRESS): probatio.All(cv.string, probatio.Upper),
    }
)

SCHEMA_SERVICE_PUT_PARAMSET = probatio.Schema(
    {
        probatio.Required(ATTR_INTERFACE): cv.string,
        probatio.Required(ATTR_ADDRESS): probatio.All(cv.string, probatio.Upper),
        probatio.Required(ATTR_PARAMSET_KEY): probatio.All(cv.string, probatio.Upper),
        probatio.Required(ATTR_PARAMSET): dict,
        probatio.Optional(ATTR_RX_MODE): probatio.All(cv.string, probatio.Upper),
    }
)


def _service_handle_reconnect(service: ServiceCall) -> None:
    """Service to reconnect all HomeMatic hubs."""
    service.hass.data[DATA_HOMEMATIC].reconnect()


def _service_handle_install_mode(service: ServiceCall) -> None:
    """Service to set interface into install mode."""
    interface = service.data.get(ATTR_INTERFACE)
    mode = service.data.get(ATTR_MODE)
    time = service.data.get(ATTR_TIME)
    address = service.data.get(ATTR_ADDRESS)

    service.hass.data[DATA_HOMEMATIC].setInstallMode(
        interface, t=time, mode=mode, address=address
    )


def _service_put_paramset(service: ServiceCall) -> None:
    """Service to call the putParamset method on a HomeMatic connection."""
    interface = service.data[ATTR_INTERFACE]
    address = service.data[ATTR_ADDRESS]
    paramset_key = service.data[ATTR_PARAMSET_KEY]
    # When passing in the paramset from a YAML file we get an OrderedDict
    # here instead of a dict, so add this explicit cast.
    # The service schema makes sure that this cast works.
    paramset = dict(service.data[ATTR_PARAMSET])
    rx_mode = service.data.get(ATTR_RX_MODE)

    _LOGGER.debug(
        "Calling putParamset: %s, %s, %s, %s, %s",
        interface,
        address,
        paramset_key,
        paramset,
        rx_mode,
    )
    service.hass.data[DATA_HOMEMATIC].putParamset(
        interface, address, paramset_key, paramset, rx_mode
    )


def setup_services(hass: HomeAssistant) -> None:
    """Register the Homematic services."""
    hass.services.register(
        DOMAIN,
        SERVICE_RECONNECT,
        _service_handle_reconnect,
        schema=SCHEMA_SERVICE_RECONNECT,
    )

    run_callback_threadsafe(
        hass.loop,
        async_register_admin_service,
        hass,
        DOMAIN,
        SERVICE_SET_INSTALL_MODE,
        _service_handle_install_mode,
        SCHEMA_SERVICE_SET_INSTALL_MODE,
    ).result()

    hass.services.register(
        DOMAIN,
        SERVICE_PUT_PARAMSET,
        _service_put_paramset,
        schema=SCHEMA_SERVICE_PUT_PARAMSET,
    )
