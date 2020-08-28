"""Support KNX devices."""
import logging

import voluptuous as vol
from xknx import XKNX
from xknx.devices import DateTime, ExposeSensor
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.exceptions import XKNXException
from xknx.io import DEFAULT_MCAST_PORT, ConnectionConfig, ConnectionType
from xknx.telegram import AddressFilter, GroupAddress, Telegram

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import DATA_KNX, DOMAIN, DeviceTypes
from .factory import create_knx_device
from .schema import (
    BinarySensorSchema,
    ClimateSchema,
    ConnectionSchema,
    CoverSchema,
    ExposeSchema,
    LightSchema,
    NotifySchema,
    SceneSchema,
    SensorSchema,
    SwitchSchema,
)

_LOGGER = logging.getLogger(__name__)

CONF_KNX_CONFIG = "config_file"

CONF_KNX_ROUTING = "routing"
CONF_KNX_TUNNELING = "tunneling"
CONF_KNX_FIRE_EVENT = "fire_event"
CONF_KNX_FIRE_EVENT_FILTER = "fire_event_filter"
CONF_KNX_STATE_UPDATER = "state_updater"
CONF_KNX_RATE_LIMIT = "rate_limit"
CONF_KNX_EXPOSE = "expose"

CONF_KNX_LIGHT = "light"
CONF_KNX_COVER = "cover"
CONF_KNX_BINARY_SENSOR = "binary_sensor"
CONF_KNX_SCENE = "scene"
CONF_KNX_SENSOR = "sensor"
CONF_KNX_SWITCH = "switch"
CONF_KNX_NOTIFY = "notify"
CONF_KNX_CLIMATE = "climate"

SERVICE_KNX_SEND = "send"
SERVICE_KNX_ATTR_ADDRESS = "address"
SERVICE_KNX_ATTR_PAYLOAD = "payload"
SERVICE_KNX_ATTR_TYPE = "type"

ATTR_DISCOVER_DEVICES = "devices"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_KNX_CONFIG): cv.string,
                vol.Exclusive(
                    CONF_KNX_ROUTING, "connection_type"
                ): ConnectionSchema.ROUTING_SCHEMA,
                vol.Exclusive(
                    CONF_KNX_TUNNELING, "connection_type"
                ): ConnectionSchema.TUNNELING_SCHEMA,
                vol.Inclusive(CONF_KNX_FIRE_EVENT, "fire_ev"): cv.boolean,
                vol.Inclusive(CONF_KNX_FIRE_EVENT_FILTER, "fire_ev"): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_KNX_STATE_UPDATER, default=True): cv.boolean,
                vol.Optional(CONF_KNX_RATE_LIMIT, default=20): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
                vol.Optional(CONF_KNX_EXPOSE): vol.All(
                    cv.ensure_list, [ExposeSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_COVER): vol.All(
                    cv.ensure_list, [CoverSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_BINARY_SENSOR): vol.All(
                    cv.ensure_list, [BinarySensorSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_LIGHT): vol.All(
                    cv.ensure_list, [LightSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_CLIMATE): vol.All(
                    cv.ensure_list, [ClimateSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_NOTIFY): vol.All(
                    cv.ensure_list, [NotifySchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_SWITCH): vol.All(
                    cv.ensure_list, [SwitchSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_SENSOR): vol.All(
                    cv.ensure_list, [SensorSchema.SCHEMA]
                ),
                vol.Optional(CONF_KNX_SCENE): vol.All(
                    cv.ensure_list, [SceneSchema.SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_KNX_SEND_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_KNX_ATTR_ADDRESS): cv.string,
        vol.Required(SERVICE_KNX_ATTR_PAYLOAD): vol.Any(
            cv.positive_int, [cv.positive_int]
        ),
        vol.Optional(SERVICE_KNX_ATTR_TYPE): vol.Any(int, float, str),
    }
)

KNX_CONFIG_PLATFORM_MAPPING = {
    CONF_KNX_COVER: DeviceTypes.cover,
    CONF_KNX_SWITCH: DeviceTypes.switch,
    CONF_KNX_LIGHT: DeviceTypes.light,
    CONF_KNX_SENSOR: DeviceTypes.sensor,
    CONF_KNX_NOTIFY: DeviceTypes.notify,
    CONF_KNX_SCENE: DeviceTypes.scene,
    CONF_KNX_BINARY_SENSOR: DeviceTypes.binary_sensor,
    CONF_KNX_CLIMATE: DeviceTypes.climate,
}


async def async_setup(hass, config):
    """Set up the KNX component."""
    try:
        hass.data[DATA_KNX] = KNXModule(hass, config)
        hass.data[DATA_KNX].async_create_exposures()
        await hass.data[DATA_KNX].start()
    except XKNXException as ex:
        _LOGGER.warning("Can't connect to KNX interface: %s", ex)
        hass.components.persistent_notification.async_create(
            f"Can't connect to KNX interface: <br><b>{ex}</b>", title="KNX"
        )

    for platform_config, device_type in KNX_CONFIG_PLATFORM_MAPPING.items():
        if platform_config in config[DOMAIN]:
            for device_config in config[DOMAIN][platform_config]:
                hass.data[DATA_KNX].xknx.devices.add(
                    create_knx_device(
                        hass, device_type, hass.data[DATA_KNX].xknx, device_config
                    )
                )

    for component, discovery_type in (
        ("switch", "Switch"),
        ("climate", "Climate"),
        ("cover", "Cover"),
        ("light", "Light"),
        ("sensor", "Sensor"),
        ("binary_sensor", "BinarySensor"),
        ("scene", "Scene"),
        ("notify", "Notification"),
    ):
        found_devices = _get_devices(hass, discovery_type)
        hass.async_create_task(
            discovery.async_load_platform(
                hass, component, DOMAIN, {ATTR_DISCOVER_DEVICES: found_devices}, config
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_KNX_SEND,
        hass.data[DATA_KNX].service_send_to_knx_bus,
        schema=SERVICE_KNX_SEND_SCHEMA,
    )

    return True


def _get_devices(hass, discovery_type):
    """Get the KNX devices."""
    return list(
        map(
            lambda device: device.name,
            filter(
                lambda device: type(device).__name__ == discovery_type,
                hass.data[DATA_KNX].xknx.devices,
            ),
        )
    )


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
        self.xknx = XKNX(
            config=self.config_file(),
            loop=self.hass.loop,
            rate_limit=self.config[DOMAIN][CONF_KNX_RATE_LIMIT],
        )

    async def start(self):
        """Start KNX object. Connect to tunneling or Routing device."""
        connection_config = self.connection_config()
        await self.xknx.start(
            state_updater=self.config[DOMAIN][CONF_KNX_STATE_UPDATER],
            connection_config=connection_config,
        )
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
        # return None to let xknx use config from xknx.yaml connection block if given
        #   otherwise it will use default ConnectionConfig (Automatic)
        return None

    def connection_config_routing(self):
        """Return the connection_config if routing is configured."""
        local_ip = self.config[DOMAIN][CONF_KNX_ROUTING].get(
            ConnectionSchema.CONF_KNX_LOCAL_IP
        )
        return ConnectionConfig(
            connection_type=ConnectionType.ROUTING, local_ip=local_ip
        )

    def connection_config_tunneling(self):
        """Return the connection_config if tunneling is configured."""
        gateway_ip = self.config[DOMAIN][CONF_KNX_TUNNELING][CONF_HOST]
        gateway_port = self.config[DOMAIN][CONF_KNX_TUNNELING].get(CONF_PORT)
        local_ip = self.config[DOMAIN][CONF_KNX_TUNNELING].get(
            ConnectionSchema.CONF_KNX_LOCAL_IP
        )
        if gateway_port is None:
            gateway_port = DEFAULT_MCAST_PORT
        return ConnectionConfig(
            connection_type=ConnectionType.TUNNELING,
            gateway_ip=gateway_ip,
            gateway_port=gateway_port,
            local_ip=local_ip,
            auto_reconnect=True,
        )

    def register_callbacks(self):
        """Register callbacks within XKNX object."""
        if (
            CONF_KNX_FIRE_EVENT in self.config[DOMAIN]
            and self.config[DOMAIN][CONF_KNX_FIRE_EVENT]
        ):
            address_filters = list(
                map(AddressFilter, self.config[DOMAIN][CONF_KNX_FIRE_EVENT_FILTER])
            )
            self.xknx.telegram_queue.register_telegram_received_cb(
                self.telegram_received_cb, address_filters
            )

    @callback
    def async_create_exposures(self):
        """Create exposures."""
        if CONF_KNX_EXPOSE not in self.config[DOMAIN]:
            return
        for to_expose in self.config[DOMAIN][CONF_KNX_EXPOSE]:
            expose_type = to_expose.get(ExposeSchema.CONF_KNX_EXPOSE_TYPE)
            entity_id = to_expose.get(CONF_ENTITY_ID)
            attribute = to_expose.get(ExposeSchema.CONF_KNX_EXPOSE_ATTRIBUTE)
            default = to_expose.get(ExposeSchema.CONF_KNX_EXPOSE_DEFAULT)
            address = to_expose.get(ExposeSchema.CONF_KNX_EXPOSE_ADDRESS)
            if expose_type in ["time", "date", "datetime"]:
                exposure = KNXExposeTime(self.xknx, expose_type, address)
                exposure.async_register()
                self.exposures.append(exposure)
            else:
                exposure = KNXExposeSensor(
                    self.hass,
                    self.xknx,
                    expose_type,
                    entity_id,
                    attribute,
                    default,
                    address,
                )
                exposure.async_register()
                self.exposures.append(exposure)

    async def telegram_received_cb(self, telegram):
        """Call invoked after a KNX telegram was received."""
        self.hass.bus.async_fire(
            "knx_event",
            {"address": str(telegram.group_address), "data": telegram.payload.value},
        )
        # False signals XKNX to proceed with processing telegrams.
        return False

    async def service_send_to_knx_bus(self, call):
        """Service for sending an arbitrary KNX message to the KNX bus."""
        attr_payload = call.data.get(SERVICE_KNX_ATTR_PAYLOAD)
        attr_address = call.data.get(SERVICE_KNX_ATTR_ADDRESS)
        attr_type = call.data.get(SERVICE_KNX_ATTR_TYPE)

        def calculate_payload(attr_payload):
            """Calculate payload depending on type of attribute."""
            if attr_type is not None:
                transcoder = DPTBase.parse_transcoder(attr_type)
                if transcoder is None:
                    raise ValueError(f"Invalid type for knx.send service: {attr_type}")
                return DPTArray(transcoder.to_knx(attr_payload))
            if isinstance(attr_payload, int):
                return DPTBinary(attr_payload)
            return DPTArray(attr_payload)

        payload = calculate_payload(attr_payload)
        address = GroupAddress(attr_address)

        telegram = Telegram()
        telegram.payload = payload
        telegram.group_address = address
        await self.xknx.telegrams.put(telegram)


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
        broadcast_type_string = self.type.upper()
        broadcast_type = broadcast_type_string
        self.device = DateTime(
            self.xknx, "Time", broadcast_type=broadcast_type, group_address=self.address
        )
        self.xknx.devices.add(self.device)


class KNXExposeSensor:
    """Object to Expose Home Assistant entity to KNX bus."""

    def __init__(self, hass, xknx, expose_type, entity_id, attribute, default, address):
        """Initialize of Expose class."""
        self.hass = hass
        self.xknx = xknx
        self.type = expose_type
        self.entity_id = entity_id
        self.expose_attribute = attribute
        self.expose_default = default
        self.address = address
        self.device = None

    @callback
    def async_register(self):
        """Register listener."""
        if self.expose_attribute is not None:
            _name = self.entity_id + "__" + self.expose_attribute
        else:
            _name = self.entity_id
        self.device = ExposeSensor(
            self.xknx,
            name=_name,
            group_address=self.address,
            value_type=self.type,
        )
        self.xknx.devices.add(self.device)
        async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )

    async def _async_entity_changed(self, event):
        """Handle entity change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        if self.expose_attribute is not None:
            new_attribute = new_state.attributes.get(self.expose_attribute)
            old_state = event.data.get("old_state")

            if old_state is not None:
                old_attribute = old_state.attributes.get(self.expose_attribute)
                if old_attribute == new_attribute:
                    # don't send same value sequentially
                    return
            await self._async_set_knx_value(new_attribute)
        else:
            await self._async_set_knx_value(new_state.state)

    async def _async_set_knx_value(self, value):
        """Set new value on xknx ExposeSensor."""
        if value is None:
            if self.expose_default is None:
                return
            value = self.expose_default

        if self.type == "binary":
            if value == STATE_ON:
                value = True
            elif value == STATE_OFF:
                value = False

        await self.device.set(value)
