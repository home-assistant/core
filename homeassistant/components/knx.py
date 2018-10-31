"""
Connects to KNX platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/knx/
"""

import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_ENTITY_ID, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

REQUIREMENTS = ['xknx==0.9.1']

DOMAIN = "knx"
DATA_KNX = "data_knx"
CONF_KNX_CONFIG = "config_file"

CONF_KNX_ROUTING = "routing"
CONF_KNX_TUNNELING = "tunneling"
CONF_KNX_LOCAL_IP = "local_ip"
CONF_KNX_FIRE_EVENT = "fire_event"
CONF_KNX_FIRE_EVENT_FILTER = "fire_event_filter"
CONF_KNX_STATE_UPDATER = "state_updater"
CONF_KNX_EXPOSE = "expose"
CONF_KNX_EXPOSE_TYPE = "type"
CONF_KNX_EXPOSE_ADDRESS = "address"

SERVICE_KNX_SEND = "send"
SERVICE_KNX_ATTR_ADDRESS = "address"
SERVICE_KNX_ATTR_PAYLOAD = "payload"

ATTR_DISCOVER_DEVICES = 'devices'

_LOGGER = logging.getLogger(__name__)

TUNNELING_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_KNX_LOCAL_IP): cv.string,
    vol.Optional(CONF_PORT): cv.port,
})

ROUTING_SCHEMA = vol.Schema({
    vol.Required(CONF_KNX_LOCAL_IP): cv.string,
})

EXPOSE_SCHEMA = vol.Schema({
    vol.Required(CONF_KNX_EXPOSE_TYPE): cv.string,
    vol.Optional(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_KNX_EXPOSE_ADDRESS): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_KNX_CONFIG): cv.string,
        vol.Exclusive(CONF_KNX_ROUTING, 'connection_type'): ROUTING_SCHEMA,
        vol.Exclusive(CONF_KNX_TUNNELING, 'connection_type'):
            TUNNELING_SCHEMA,
        vol.Inclusive(CONF_KNX_FIRE_EVENT, 'fire_ev'):
            cv.boolean,
        vol.Inclusive(CONF_KNX_FIRE_EVENT_FILTER, 'fire_ev'):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_KNX_STATE_UPDATER, default=True): cv.boolean,
        vol.Optional(CONF_KNX_EXPOSE):
            vol.All(
                cv.ensure_list,
                [EXPOSE_SCHEMA]),
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_KNX_SEND_SCHEMA = vol.Schema({
    vol.Required(SERVICE_KNX_ATTR_ADDRESS): cv.string,
    vol.Required(SERVICE_KNX_ATTR_PAYLOAD): vol.Any(
        cv.positive_int, [cv.positive_int]),
})


async def async_setup(hass, config):
    """Set up the KNX component."""
    from xknx.exceptions import XKNXException
    try:
        hass.data[DATA_KNX] = KNXModule(hass, config)
        hass.data[DATA_KNX].async_create_exposures()
        await hass.data[DATA_KNX].start()

    except XKNXException as ex:
        _LOGGER.warning("Can't connect to KNX interface: %s", ex)
        hass.components.persistent_notification.async_create(
            "Can't connect to KNX interface: <br>"
            "<b>{0}</b>".format(ex),
            title="KNX")

    for component, discovery_type in (
            ('switch', 'Switch'),
            ('climate', 'Climate'),
            ('cover', 'Cover'),
            ('light', 'Light'),
            ('sensor', 'Sensor'),
            ('binary_sensor', 'BinarySensor'),
            ('scene', 'Scene'),
            ('notify', 'Notification')):
        found_devices = _get_devices(hass, discovery_type)
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {
                ATTR_DISCOVER_DEVICES: found_devices
            }, config))

    hass.services.async_register(
        DOMAIN, SERVICE_KNX_SEND,
        hass.data[DATA_KNX].service_send_to_knx_bus,
        schema=SERVICE_KNX_SEND_SCHEMA)

    return True


def _get_devices(hass, discovery_type):
    """Get the KNX devices."""
    return list(
        map(lambda device: device.name,
            filter(
                lambda device: type(device).__name__ == discovery_type,
                hass.data[DATA_KNX].xknx.devices)))


class KNXModule:
    """Representation of KNX Object."""

    def __init__(self, hass, config):
        """Initialize of KNX module."""
        self.hass = hass
        self.config = config
        self.connected = False
        self.init_xknx()
        self.register_callbacks()
        self.exposures = []

    def init_xknx(self):
        """Initialize of KNX object."""
        from xknx import XKNX
        self.xknx = XKNX(config=self.config_file(), loop=self.hass.loop)

    async def start(self):
        """Start KNX object. Connect to tunneling or Routing device."""
        connection_config = self.connection_config()
        await self.xknx.start(
            state_updater=self.config[DOMAIN][CONF_KNX_STATE_UPDATER],
            connection_config=connection_config)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.connected = True

    async def stop(self, event):
        """Stop KNX object. Disconnect from tunneling or Routing device."""
        await self.xknx.stop()

    def config_file(self):
        """Resolve and return the full path of xknx.yaml if configured."""
        config_file = self.config[DOMAIN].get(CONF_KNX_CONFIG)
        if not config_file:
            return None
        if not config_file.startswith("/"):
            return self.hass.config.path(config_file)
        return config_file

    def connection_config(self):
        """Return the connection_config."""
        if CONF_KNX_TUNNELING in self.config[DOMAIN]:
            return self.connection_config_tunneling()
        if CONF_KNX_ROUTING in self.config[DOMAIN]:
            return self.connection_config_routing()
        return self.connection_config_auto()

    def connection_config_routing(self):
        """Return the connection_config if routing is configured."""
        from xknx.io import ConnectionConfig, ConnectionType
        local_ip = \
            self.config[DOMAIN][CONF_KNX_ROUTING].get(CONF_KNX_LOCAL_IP)
        return ConnectionConfig(
            connection_type=ConnectionType.ROUTING,
            local_ip=local_ip)

    def connection_config_tunneling(self):
        """Return the connection_config if tunneling is configured."""
        from xknx.io import ConnectionConfig, ConnectionType, \
            DEFAULT_MCAST_PORT
        gateway_ip = \
            self.config[DOMAIN][CONF_KNX_TUNNELING].get(CONF_HOST)
        gateway_port = \
            self.config[DOMAIN][CONF_KNX_TUNNELING].get(CONF_PORT)
        local_ip = \
            self.config[DOMAIN][CONF_KNX_TUNNELING].get(CONF_KNX_LOCAL_IP)
        if gateway_port is None:
            gateway_port = DEFAULT_MCAST_PORT
        return ConnectionConfig(
            connection_type=ConnectionType.TUNNELING, gateway_ip=gateway_ip,
            gateway_port=gateway_port, local_ip=local_ip)

    def connection_config_auto(self):
        """Return the connection_config if auto is configured."""
        # pylint: disable=no-self-use
        from xknx.io import ConnectionConfig
        return ConnectionConfig()

    def register_callbacks(self):
        """Register callbacks within XKNX object."""
        if CONF_KNX_FIRE_EVENT in self.config[DOMAIN] and \
                self.config[DOMAIN][CONF_KNX_FIRE_EVENT]:
            from xknx.knx import AddressFilter
            address_filters = list(map(
                AddressFilter,
                self.config[DOMAIN][CONF_KNX_FIRE_EVENT_FILTER]))
            self.xknx.telegram_queue.register_telegram_received_cb(
                self.telegram_received_cb, address_filters)

    @callback
    def async_create_exposures(self):
        """Create exposures."""
        if CONF_KNX_EXPOSE not in self.config[DOMAIN]:
            return
        for to_expose in self.config[DOMAIN][CONF_KNX_EXPOSE]:
            expose_type = to_expose.get(CONF_KNX_EXPOSE_TYPE)
            entity_id = to_expose.get(CONF_ENTITY_ID)
            address = to_expose.get(CONF_KNX_EXPOSE_ADDRESS)
            if expose_type in ['time', 'date', 'datetime']:
                exposure = KNXExposeTime(
                    self.xknx, expose_type, address)
                exposure.async_register()
                self.exposures.append(exposure)
            else:
                exposure = KNXExposeSensor(
                    self.hass, self.xknx, expose_type, entity_id, address)
                exposure.async_register()
                self.exposures.append(exposure)

    async def telegram_received_cb(self, telegram):
        """Call invoked after a KNX telegram was received."""
        self.hass.bus.async_fire('knx_event', {
            'address': str(telegram.group_address),
            'data': telegram.payload.value
        })
        # False signals XKNX to proceed with processing telegrams.
        return False

    async def service_send_to_knx_bus(self, call):
        """Service for sending an arbitrary KNX message to the KNX bus."""
        from xknx.knx import Telegram, GroupAddress, DPTBinary, DPTArray
        attr_payload = call.data.get(SERVICE_KNX_ATTR_PAYLOAD)
        attr_address = call.data.get(SERVICE_KNX_ATTR_ADDRESS)

        def calculate_payload(attr_payload):
            """Calculate payload depending on type of attribute."""
            if isinstance(attr_payload, int):
                return DPTBinary(attr_payload)
            return DPTArray(attr_payload)
        payload = calculate_payload(attr_payload)
        address = GroupAddress(attr_address)

        telegram = Telegram()
        telegram.payload = payload
        telegram.group_address = address
        await self.xknx.telegrams.put(telegram)


class KNXAutomation():
    """Wrapper around xknx.devices.ActionCallback object.."""

    def __init__(self, hass, device, hook, action, counter=1):
        """Initialize Automation class."""
        self.hass = hass
        self.device = device
        script_name = "{} turn ON script".format(device.get_name())
        self.script = Script(hass, action, script_name)

        import xknx
        self.action = xknx.devices.ActionCallback(
            hass.data[DATA_KNX].xknx, self.script.async_run,
            hook=hook, counter=counter)
        device.actions.append(self.action)


class KNXExposeTime:
    """Object to Expose Time/Date object to KNX bus."""

    def __init__(self, xknx, expose_type, address):
        """Initialize of Expose class."""
        self.xknx = xknx
        self.type = expose_type
        self.address = address
        self.device = None

    @callback
    def async_register(self):
        """Register listener."""
        from xknx.devices import DateTime, DateTimeBroadcastType
        broadcast_type_string = self.type.upper()
        broadcast_type = DateTimeBroadcastType[broadcast_type_string]
        self.device = DateTime(
            self.xknx,
            'Time',
            broadcast_type=broadcast_type,
            group_address=self.address)
        self.xknx.devices.add(self.device)


class KNXExposeSensor:
    """Object to Expose HASS entity to KNX bus."""

    def __init__(self, hass, xknx, expose_type, entity_id, address):
        """Initialize of Expose class."""
        self.hass = hass
        self.xknx = xknx
        self.type = expose_type
        self.entity_id = entity_id
        self.address = address
        self.device = None

    @callback
    def async_register(self):
        """Register listener."""
        from xknx.devices import ExposeSensor
        self.device = ExposeSensor(
            self.xknx,
            name=self.entity_id,
            group_address=self.address,
            value_type=self.type)
        self.xknx.devices.add(self.device)
        async_track_state_change(
            self.hass, self.entity_id, self._async_entity_changed)

    async def _async_entity_changed(self, entity_id, old_state, new_state):
        """Handle entity change."""
        if new_state is None:
            return
        await self.device.set(float(new_state.state))
