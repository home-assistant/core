"""Support for Modbus."""
import logging
import threading
import asyncio
import json

from homeassistant.const import (
    ATTR_STATE,
    CONF_COVERS,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)

from homeassistant.helpers.discovery import load_platform

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_UNIT,
    ATTR_VALUE,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CLIMATE,
    CONF_CLIMATES,
    CONF_COVER,
    CONF_PARITY,
    CONF_STOPBITS,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
    CONF_TYPE_TCPSERVER,
)

from .modbus_hub import ModbusClientHub
from .modbus_server import ModbusServerHub

_LOGGER = logging.getLogger(__name__)


def ser_set(obj):
    if isinstance(obj, set):
        return list(obj)
    return obj


def modbus_hub_factory(client_config, hass):
    if client_config[CONF_TYPE] == CONF_TYPE_TCPSERVER:
        return ModbusServerHub(client_config, hass)
    else:
        return ModbusClientHub(client_config)


def modbus_setup(
    hass, config, service_write_register_schema, service_write_coil_schema
):
    """Set up Modbus component."""
    hass.data[DOMAIN] = hub_collect = {}

    for conf_hub in config[DOMAIN]:
        hub_collect[conf_hub[CONF_NAME]] = modbus_hub_factory(conf_hub, hass)

        # modbus needs to be activated before components are loaded
        # to avoid a racing problem
        hub_collect[conf_hub[CONF_NAME]].setup()

        # load platforms
        for component, conf_key in (
            (CONF_CLIMATE, CONF_CLIMATES),
            (CONF_COVER, CONF_COVERS),
        ):
            if conf_key in conf_hub:
                load_platform(hass, component, DOMAIN, conf_hub, config)

    def stop_modbus(event):
        """Stop Modbus service."""
        for client in hub_collect.values():
            client.close()

    def write_register(service):
        """Write Modbus registers."""
        unit = int(float(service.data[ATTR_UNIT]))
        address = int(float(service.data[ATTR_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = service.data[ATTR_HUB]
        if isinstance(value, list):
            hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value]
            )
        else:
            hub_collect[client_name].write_register(unit, address, int(float(value)))

    def write_coil(service):
        """Write Modbus coil."""
        unit = service.data[ATTR_UNIT]
        address = service.data[ATTR_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = service.data[ATTR_HUB]
        hub_collect[client_name].write_coil(unit, address, state)

    # register function to gracefully stop modbus
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

    # Register services for modbus
    hass.services.register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        write_register,
        schema=service_write_register_schema,
    )
    hass.services.register(
        DOMAIN, SERVICE_WRITE_COIL, write_coil, schema=service_write_coil_schema
    )

    return True
