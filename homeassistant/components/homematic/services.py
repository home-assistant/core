"""Services for the Homematic integration."""

from datetime import datetime
import logging
from typing import Any

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util.async_ import run_callback_threadsafe

from .const import (
    DATA_HOMEMATIC,
    DATA_HUBS,
    DOMAIN,
    HomematicService,
    HomematicServiceArgument,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_SERVICE_VIRTUALKEY = probatio.Schema(
    {
        probatio.Required(HomematicServiceArgument.ADDRESS): probatio.All(
            cv.string, probatio.Upper
        ),
        probatio.Required(HomematicServiceArgument.CHANNEL): probatio.Coerce(int),
        probatio.Required(HomematicServiceArgument.PARAM): cv.string,
        probatio.Optional(HomematicServiceArgument.INTERFACE): cv.string,
    }
)

SCHEMA_SERVICE_SET_VARIABLE_VALUE = probatio.Schema(
    {
        probatio.Required(HomematicServiceArgument.NAME): cv.string,
        probatio.Required(HomematicServiceArgument.VALUE): cv.match_all,
        probatio.Optional(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
    }
)

SCHEMA_SERVICE_SET_DEVICE_VALUE = probatio.Schema(
    {
        probatio.Required(HomematicServiceArgument.ADDRESS): probatio.All(
            cv.string, probatio.Upper
        ),
        probatio.Required(HomematicServiceArgument.CHANNEL): probatio.Coerce(int),
        probatio.Required(HomematicServiceArgument.PARAM): probatio.All(
            cv.string, probatio.Upper
        ),
        probatio.Required(HomematicServiceArgument.VALUE): cv.match_all,
        probatio.Optional(HomematicServiceArgument.VALUE_TYPE): probatio.In(
            ["boolean", "dateTime.iso8601", "double", "int", "string"]
        ),
        probatio.Optional(HomematicServiceArgument.INTERFACE): cv.string,
    }
)

SCHEMA_SERVICE_RECONNECT = probatio.Schema({})

SCHEMA_SERVICE_SET_INSTALL_MODE = probatio.Schema(
    {
        probatio.Required(HomematicServiceArgument.INTERFACE): cv.string,
        probatio.Optional(HomematicServiceArgument.TIME, default=60): cv.positive_int,
        probatio.Optional(HomematicServiceArgument.MODE, default=1): probatio.All(
            probatio.Coerce(int), probatio.In([1, 2])
        ),
        probatio.Optional(HomematicServiceArgument.ADDRESS): probatio.All(
            cv.string, probatio.Upper
        ),
    }
)

SCHEMA_SERVICE_PUT_PARAMSET = probatio.Schema(
    {
        probatio.Required(HomematicServiceArgument.INTERFACE): cv.string,
        probatio.Required(HomematicServiceArgument.ADDRESS): probatio.All(
            cv.string, probatio.Upper
        ),
        probatio.Required(HomematicServiceArgument.PARAMSET_KEY): probatio.All(
            cv.string, probatio.Upper
        ),
        probatio.Required(HomematicServiceArgument.PARAMSET): dict,
        probatio.Optional(HomematicServiceArgument.RX_MODE): probatio.All(
            cv.string, probatio.Upper
        ),
    }
)


def _device_from_servicecall(hass: HomeAssistant, service: ServiceCall) -> Any:
    """Extract HomeMatic device from service call."""
    address = service.data.get(HomematicServiceArgument.ADDRESS)
    interface = service.data.get(HomematicServiceArgument.INTERFACE)
    if address == "BIDCOS-RF":
        address = "BidCoS-RF"
    if address == "HMIP-RCV-1":
        address = "HmIP-RCV-1"

    if interface:
        return hass.data[DATA_HOMEMATIC].devices[interface].get(address)

    for devices in hass.data[DATA_HOMEMATIC].devices.values():
        if address in devices:
            return devices[address]
    return None


def _hm_service_virtualkey(service: ServiceCall) -> None:
    """Service to handle virtualkey servicecalls."""
    address = service.data.get(HomematicServiceArgument.ADDRESS)
    channel = service.data.get(HomematicServiceArgument.CHANNEL)
    param = service.data.get(HomematicServiceArgument.PARAM)

    # Device not found
    hmdevice = _device_from_servicecall(service.hass, service)
    if hmdevice is None:
        _LOGGER.error("%s not found for service virtualkey!", address)
        return

    # Parameter doesn't exist for device
    if param not in hmdevice.ACTIONNODE:
        _LOGGER.error("%s not datapoint in hm device %s", param, address)
        return

    # Channel doesn't exist for device
    if channel not in hmdevice.ACTIONNODE[param]:
        _LOGGER.error("%i is not a channel in hm device %s", channel, address)
        return

    # Call parameter
    hmdevice.actionNodeData(param, True, channel)


def _service_handle_value(service: ServiceCall) -> None:
    """Service to call setValue method for HomeMatic system variable."""
    entity_hubs = service.hass.data[DATA_HUBS]
    entity_ids: list[str] | None = service.data.get(CommonServiceArgument.ENTITY_ID)
    name = service.data[HomematicServiceArgument.NAME]
    value = service.data[HomematicServiceArgument.VALUE]

    if entity_ids:
        entities = [entity for entity in entity_hubs if entity.entity_id in entity_ids]
    else:
        entities = entity_hubs

    if not entities:
        _LOGGER.error("No HomeMatic hubs available")
        return

    for hub in entities:
        hub.hm_set_variable(name, value)


def _service_handle_device(service: ServiceCall) -> None:
    """Service to call setValue method for HomeMatic devices."""
    address = service.data[HomematicServiceArgument.ADDRESS]
    channel = service.data[HomematicServiceArgument.CHANNEL]
    param = service.data[HomematicServiceArgument.PARAM]
    value = service.data[HomematicServiceArgument.VALUE]
    value_type = service.data.get(HomematicServiceArgument.VALUE_TYPE)

    # Convert value into correct XML-RPC Type.
    # https://docs.python.org/3/library/xmlrpc.client.html#xmlrpc.client.ServerProxy
    if value_type:
        if value_type == "int":
            value = int(value)
        elif value_type == "double":
            value = float(value)
        elif value_type == "boolean":
            value = bool(value)
        elif value_type == "dateTime.iso8601":
            value = datetime.strptime(value, "%Y%m%dT%H:%M:%S")
        else:
            # Default is 'string'
            value = str(value)

    # Device not found
    hmdevice = _device_from_servicecall(service.hass, service)
    if hmdevice is None:
        _LOGGER.error("%s not found!", address)
        return

    hmdevice.setValue(param, value, channel)


def _service_handle_reconnect(service: ServiceCall) -> None:
    """Service to reconnect all HomeMatic hubs."""
    service.hass.data[DATA_HOMEMATIC].reconnect()


def _service_handle_install_mode(service: ServiceCall) -> None:
    """Service to set interface into install mode."""
    interface = service.data.get(HomematicServiceArgument.INTERFACE)
    mode = service.data.get(HomematicServiceArgument.MODE)
    time = service.data.get(HomematicServiceArgument.TIME)
    address = service.data.get(HomematicServiceArgument.ADDRESS)

    service.hass.data[DATA_HOMEMATIC].setInstallMode(
        interface, t=time, mode=mode, address=address
    )


def _service_put_paramset(service: ServiceCall) -> None:
    """Service to call the putParamset method on a HomeMatic connection."""
    interface = service.data[HomematicServiceArgument.INTERFACE]
    address = service.data[HomematicServiceArgument.ADDRESS]
    paramset_key = service.data[HomematicServiceArgument.PARAMSET_KEY]
    # When passing in the paramset from a YAML file we get an OrderedDict
    # here instead of a dict, so add this explicit cast.
    # The service schema makes sure that this cast works.
    paramset = dict(service.data[HomematicServiceArgument.PARAMSET])
    rx_mode = service.data.get(HomematicServiceArgument.RX_MODE)

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
        HomematicService.VIRTUALKEY,
        _hm_service_virtualkey,
        schema=SCHEMA_SERVICE_VIRTUALKEY,
    )

    hass.services.register(
        DOMAIN,
        HomematicService.SET_VARIABLE_VALUE,
        _service_handle_value,
        schema=SCHEMA_SERVICE_SET_VARIABLE_VALUE,
    )

    hass.services.register(
        DOMAIN,
        HomematicService.SET_DEVICE_VALUE,
        _service_handle_device,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE,
    )

    hass.services.register(
        DOMAIN,
        HomematicService.RECONNECT,
        _service_handle_reconnect,
        schema=SCHEMA_SERVICE_RECONNECT,
    )

    run_callback_threadsafe(
        hass.loop,
        async_register_admin_service,
        hass,
        DOMAIN,
        HomematicService.SET_INSTALL_MODE,
        _service_handle_install_mode,
        SCHEMA_SERVICE_SET_INSTALL_MODE,
    ).result()

    hass.services.register(
        DOMAIN,
        HomematicService.PUT_PARAMSET,
        _service_put_paramset,
        schema=SCHEMA_SERVICE_PUT_PARAMSET,
    )
