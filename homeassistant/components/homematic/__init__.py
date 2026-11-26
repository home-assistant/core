"""Support for HomeMatic devices."""

from functools import partial
import logging
from typing import Any

import probatio
from pyhomematic import HMConnection

from homeassistant.const import (
    ATTR_NAME,
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ADDRESS,
    ATTR_CHANNEL,
    ATTR_DEVICE_TYPE,
    ATTR_DISCOVER_DEVICES,
    ATTR_DISCOVERY_TYPE,
    ATTR_ERRORCODE,
    ATTR_INTERFACE,
    ATTR_LOW_BAT,
    ATTR_LOWBAT,
    ATTR_MESSAGE,
    ATTR_PARAM,
    ATTR_UNIQUE_ID,
    CONF_CALLBACK_IP,
    CONF_CALLBACK_PORT,
    CONF_INTERFACES,
    CONF_JSONPORT,
    CONF_LOCAL_IP,
    CONF_LOCAL_PORT,
    CONF_RESOLVENAMES,
    CONF_RESOLVENAMES_OPTIONS,
    DATA_CONF,
    DATA_HOMEMATIC,
    DATA_HUBS,
    DATA_STORE,
    DISCOVER_BATTERY,
    DISCOVER_BINARY_SENSORS,
    DISCOVER_CLIMATE,
    DISCOVER_COVER,
    DISCOVER_LIGHTS,
    DISCOVER_LOCKS,
    DISCOVER_SENSORS,
    DISCOVER_SWITCHES,
    DOMAIN,
    EVENT_ERROR,
    EVENT_IMPULSE,
    EVENT_KEYPRESS,
    HM_DEVICE_TYPES,
    HM_IGNORE_DISCOVERY_NODE,
    HM_IGNORE_DISCOVERY_NODE_EXCEPTIONS,
    HM_IMPULSE_EVENTS,
    HM_PRESS_EVENTS,
)
from .entity import HMHub
from .services import setup_services

_LOGGER = logging.getLogger(__name__)

DEFAULT_LOCAL_IP = "0.0.0.0"
DEFAULT_LOCAL_PORT = 0
DEFAULT_RESOLVENAMES = False
DEFAULT_JSONPORT = 80
DEFAULT_PORT = 2001
DEFAULT_PATH = ""
DEFAULT_USERNAME = "Admin"
DEFAULT_PASSWORD = ""
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = False
DEFAULT_CHANNEL = 1


DEVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PLATFORM): "homematic",
        probatio.Required(ATTR_NAME): cv.string,
        probatio.Required(ATTR_ADDRESS): cv.string,
        probatio.Required(ATTR_INTERFACE): cv.string,
        probatio.Optional(ATTR_DEVICE_TYPE): cv.string,
        probatio.Optional(ATTR_CHANNEL, default=DEFAULT_CHANNEL): probatio.Coerce(int),
        probatio.Optional(ATTR_PARAM): cv.string,
        probatio.Optional(ATTR_UNIQUE_ID): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_INTERFACES, default={}): {
                    cv.match_all: {
                        probatio.Required(CONF_HOST): cv.string,
                        probatio.Optional(
                            CONF_PORT, default=DEFAULT_PORT
                        ): probatio.Port(),
                        probatio.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
                        probatio.Optional(
                            CONF_RESOLVENAMES, default=DEFAULT_RESOLVENAMES
                        ): probatio.In(CONF_RESOLVENAMES_OPTIONS),
                        probatio.Optional(
                            CONF_JSONPORT, default=DEFAULT_JSONPORT
                        ): probatio.Port(),
                        probatio.Optional(
                            CONF_USERNAME, default=DEFAULT_USERNAME
                        ): cv.string,
                        probatio.Optional(
                            probatio.Secret(CONF_PASSWORD), default=DEFAULT_PASSWORD
                        ): cv.string,
                        probatio.Optional(CONF_CALLBACK_IP): cv.string,
                        probatio.Optional(CONF_CALLBACK_PORT): probatio.Port(),
                        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                        probatio.Optional(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): cv.boolean,
                    }
                },
                probatio.Optional(CONF_HOSTS, default={}): {
                    cv.match_all: {
                        probatio.Required(CONF_HOST): cv.string,
                        probatio.Optional(
                            CONF_PORT, default=DEFAULT_PORT
                        ): probatio.Port(),
                        probatio.Optional(
                            CONF_USERNAME, default=DEFAULT_USERNAME
                        ): cv.string,
                        probatio.Optional(
                            probatio.Secret(CONF_PASSWORD), default=DEFAULT_PASSWORD
                        ): cv.string,
                    }
                },
                probatio.Optional(CONF_LOCAL_IP, default=DEFAULT_LOCAL_IP): cv.string,
                probatio.Optional(CONF_LOCAL_PORT): probatio.Port(),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Homematic component."""
    conf = config[DOMAIN]
    hass.data[DATA_CONF] = remotes = {}
    hass.data[DATA_STORE] = set()

    interfaces: dict[str, dict[str, Any]] = conf[CONF_INTERFACES]
    hosts: dict[str, dict[str, Any]] = conf[CONF_HOSTS]

    # Create hosts-dictionary for pyhomematic
    for rname, rconfig in interfaces.items():
        remotes[rname] = {
            "ip": rconfig.get(CONF_HOST),
            "port": rconfig.get(CONF_PORT),
            "path": rconfig.get(CONF_PATH),
            "resolvenames": rconfig.get(CONF_RESOLVENAMES),
            "jsonport": rconfig.get(CONF_JSONPORT),
            "username": rconfig.get(CONF_USERNAME),
            "password": rconfig.get(CONF_PASSWORD),
            "callbackip": rconfig.get(CONF_CALLBACK_IP),
            "callbackport": rconfig.get(CONF_CALLBACK_PORT),
            "ssl": rconfig[CONF_SSL],
            "verify_ssl": rconfig.get(CONF_VERIFY_SSL),
            "connect": True,
        }

    for sname, sconfig in hosts.items():
        remotes[sname] = {
            "ip": sconfig.get(CONF_HOST),
            "port": sconfig[CONF_PORT],
            "username": sconfig.get(CONF_USERNAME),
            "password": sconfig.get(CONF_PASSWORD),
            "connect": False,
        }

    # Create server thread
    bound_system_callback = partial(_system_callback_handler, hass, config)
    hass.data[DATA_HOMEMATIC] = homematic = HMConnection(
        local=config[DOMAIN].get(CONF_LOCAL_IP),
        localport=config[DOMAIN].get(CONF_LOCAL_PORT, DEFAULT_LOCAL_PORT),
        remotes=remotes,
        systemcallback=bound_system_callback,
        interface_id="homeassistant",
    )

    # Start server thread, connect to hosts, initialize to receive events
    homematic.start()

    # Stops server when Home Assistant is shutting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, hass.data[DATA_HOMEMATIC].stop)

    # Init homematic hubs
    hass.data[DATA_HUBS] = [HMHub(hass, homematic, hub_name) for hub_name in hosts]

    setup_services(hass)

    return True


def _system_callback_handler(hass, config, src, *args):
    """System callback handler."""
    # New devices available at hub
    if src == "newDevices":
        (interface_id, dev_descriptions) = args
        interface = interface_id.split("-")[-1]

        # Device support active?
        if not hass.data[DATA_CONF][interface]["connect"]:
            return

        addresses = []
        for dev in dev_descriptions:
            address = dev["ADDRESS"].split(":")[0]
            if address not in hass.data[DATA_STORE]:
                hass.data[DATA_STORE].add(address)
                addresses.append(address)

        # Register EVENTS
        # Search all devices with an EVENTNODE that includes data
        bound_event_callback = partial(_hm_event_handler, hass, interface)
        for dev in addresses:
            hmdevice = hass.data[DATA_HOMEMATIC].devices[interface].get(dev)

            if hmdevice.EVENTNODE:
                hmdevice.setEventCallback(callback=bound_event_callback, bequeath=True)

        # Create Home Assistant entities
        if addresses:
            for component_name, discovery_type in (
                ("switch", DISCOVER_SWITCHES),
                ("light", DISCOVER_LIGHTS),
                ("cover", DISCOVER_COVER),
                ("binary_sensor", DISCOVER_BINARY_SENSORS),
                ("sensor", DISCOVER_SENSORS),
                ("climate", DISCOVER_CLIMATE),
                ("lock", DISCOVER_LOCKS),
                ("binary_sensor", DISCOVER_BATTERY),
            ):
                # Get all devices of a specific type
                found_devices = _get_devices(hass, discovery_type, addresses, interface)

                # When devices of this type are found
                # they are setup in Home Assistant and a discovery event is fired
                if found_devices:
                    discovery.load_platform(
                        hass,
                        component_name,
                        DOMAIN,
                        {
                            ATTR_DISCOVER_DEVICES: found_devices,
                            ATTR_DISCOVERY_TYPE: discovery_type,
                        },
                        config,
                    )

    # Homegear error message
    elif src == "error":
        _LOGGER.error("Error: %s", args)
        (interface_id, errorcode, message) = args
        hass.bus.fire(EVENT_ERROR, {ATTR_ERRORCODE: errorcode, ATTR_MESSAGE: message})


def _get_devices(hass, discovery_type, keys, interface):
    """Get the HomeMatic devices for given discovery_type."""
    device_arr = []

    for key in keys:
        device = hass.data[DATA_HOMEMATIC].devices[interface][key]
        class_name = device.__class__.__name__
        metadata = {}

        # Class not supported by discovery type
        if (
            discovery_type != DISCOVER_BATTERY
            and class_name not in HM_DEVICE_TYPES[discovery_type]
        ):
            continue

        # Load metadata needed to generate a parameter list
        if discovery_type == DISCOVER_SENSORS:
            metadata.update(device.SENSORNODE)
        elif discovery_type == DISCOVER_BINARY_SENSORS:
            metadata.update(device.BINARYNODE)
        elif discovery_type == DISCOVER_BATTERY:
            if ATTR_LOWBAT in device.ATTRIBUTENODE:
                metadata.update({ATTR_LOWBAT: device.ATTRIBUTENODE[ATTR_LOWBAT]})
            elif ATTR_LOW_BAT in device.ATTRIBUTENODE:
                metadata.update({ATTR_LOW_BAT: device.ATTRIBUTENODE[ATTR_LOW_BAT]})
            else:
                continue
        else:
            metadata.update({None: device.ELEMENT})

        # Generate options for 1...n elements with 1...n parameters
        for param, channels in metadata.items():
            if (
                param in HM_IGNORE_DISCOVERY_NODE
                and class_name not in HM_IGNORE_DISCOVERY_NODE_EXCEPTIONS.get(param, [])
            ):
                continue
            if discovery_type == DISCOVER_SWITCHES and class_name == "IPKeySwitchLevel":
                channels.remove(8)
                channels.remove(12)
            if discovery_type == DISCOVER_LIGHTS and class_name == "IPKeySwitchLevel":
                channels.remove(4)

            # Add devices
            _LOGGER.debug(
                "%s: Handling %s: %s: %s", discovery_type, key, param, channels
            )
            for channel in channels:
                name = _create_ha_id(
                    name=device.NAME, channel=channel, param=param, count=len(channels)
                )
                unique_id = _create_ha_id(
                    name=key, channel=channel, param=param, count=len(channels)
                )
                device_dict = {
                    CONF_PLATFORM: "homematic",
                    ATTR_ADDRESS: key,
                    ATTR_INTERFACE: interface,
                    ATTR_NAME: name,
                    ATTR_DEVICE_TYPE: class_name,
                    ATTR_CHANNEL: channel,
                    ATTR_UNIQUE_ID: unique_id,
                }
                if param is not None:
                    device_dict[ATTR_PARAM] = param

                # Add new device
                try:
                    DEVICE_SCHEMA(device_dict)
                    device_arr.append(device_dict)
                except probatio.MultipleInvalid as err:
                    _LOGGER.error("Invalid device config: %s", str(err))
    return device_arr


def _create_ha_id(name, channel, param, count):
    """Generate a unique entity id."""
    # HMDevice is a simple device
    if count == 1 and param is None:
        return name

    # Has multiple elements/channels
    if count > 1 and param is None:
        return f"{name} {channel}"

    # With multiple parameters on first channel
    if count == 1 and param is not None:
        return f"{name} {param}"

    # Multiple parameters with multiple channels
    if count > 1 and param is not None:
        return f"{name} {channel} {param}"

    raise ValueError(f"Unable to create unique id for count:{count} and param:{param}")


def _hm_event_handler(hass, interface, device, caller, attribute, value):
    """Handle all pyhomematic device events."""
    try:
        channel = int(device.split(":")[1])
        address = device.split(":")[0]
        hmdevice = hass.data[DATA_HOMEMATIC].devices[interface].get(address)
    except TypeError, ValueError:
        _LOGGER.error("Event handling channel convert error!")
        return

    # Return if not an event supported by device
    if attribute not in hmdevice.EVENTNODE:
        return

    _LOGGER.debug("Event %s for %s channel %i", attribute, hmdevice.NAME, channel)

    # Keypress event
    if attribute in HM_PRESS_EVENTS:
        hass.bus.fire(
            EVENT_KEYPRESS,
            {ATTR_NAME: hmdevice.NAME, ATTR_PARAM: attribute, ATTR_CHANNEL: channel},
        )
        return

    # Impulse event
    if attribute in HM_IMPULSE_EVENTS:
        hass.bus.fire(EVENT_IMPULSE, {ATTR_NAME: hmdevice.NAME, ATTR_CHANNEL: channel})
        return

    _LOGGER.warning("Event is unknown and not forwarded")
