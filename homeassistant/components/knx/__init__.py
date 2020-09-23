"""Support KNX devices."""
import logging

import voluptuous as vol
from xknx import XKNX
from xknx.devices import DateTime, ExposeSensor
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.exceptions import XKNXException
from xknx.io import (
    DEFAULT_MCAST_GRP,
    DEFAULT_MCAST_PORT,
    ConnectionConfig,
    ConnectionType,
)
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

from .const import DOMAIN, SupportedPlatforms
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
    WeatherSchema,
)

_LOGGER = logging.getLogger(__name__)

CONF_KNX_CONFIG = "config_file"

CONF_KNX_ROUTING = "routing"
CONF_KNX_TUNNELING = "tunneling"
CONF_KNX_FIRE_EVENT = "fire_event"
CONF_KNX_FIRE_EVENT_FILTER = "fire_event_filter"
CONF_KNX_INDIVIDUAL_ADDRESS = "individual_address"
CONF_KNX_MCAST_GRP = "multicast_group"
CONF_KNX_MCAST_PORT = "multicast_port"
CONF_KNX_STATE_UPDATER = "state_updater"
CONF_KNX_RATE_LIMIT = "rate_limit"
CONF_KNX_EXPOSE = "expose"

SERVICE_KNX_SEND = "send"
SERVICE_KNX_ATTR_ADDRESS = "address"
SERVICE_KNX_ATTR_PAYLOAD = "payload"
SERVICE_KNX_ATTR_TYPE = "type"

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
                vol.Optional(
                    CONF_KNX_INDIVIDUAL_ADDRESS, default=XKNX.DEFAULT_ADDRESS
                ): cv.string,
                vol.Optional(CONF_KNX_MCAST_GRP, default=DEFAULT_MCAST_GRP): cv.string,
                vol.Optional(CONF_KNX_MCAST_PORT, default=DEFAULT_MCAST_PORT): cv.port,
                vol.Optional(CONF_KNX_STATE_UPDATER, default=True): cv.boolean,
                vol.Optional(CONF_KNX_RATE_LIMIT, default=20): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
                vol.Optional(CONF_KNX_EXPOSE): vol.All(
                    cv.ensure_list, [ExposeSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.cover.value): vol.All(
                    cv.ensure_list, [CoverSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.binary_sensor.value): vol.All(
                    cv.ensure_list, [BinarySensorSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.light.value): vol.All(
                    cv.ensure_list, [LightSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.climate.value): vol.All(
                    cv.ensure_list, [ClimateSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.notify.value): vol.All(
                    cv.ensure_list, [NotifySchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.switch.value): vol.All(
                    cv.ensure_list, [SwitchSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.sensor.value): vol.All(
                    cv.ensure_list, [SensorSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.scene.value): vol.All(
                    cv.ensure_list, [SceneSchema.SCHEMA]
                ),
                vol.Optional(SupportedPlatforms.weather.value): vol.All(
                    cv.ensure_list, [WeatherSchema.SCHEMA]
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


async def async_setup(hass, config):
    """Set up the KNX component."""
    try:
        hass.data[DOMAIN] = KNXModule(hass, config)
        hass.data[DOMAIN].async_create_exposures()
        await hass.data[DOMAIN].start()
    except XKNXException as ex:
        _LOGGER.warning("Could not connect to KNX interface: %s", ex)
        hass.components.persistent_notification.async_create(
            f"Could not connect to KNX interface: <br><b>{ex}</b>", title="KNX"
        )

    for platform in SupportedPlatforms:
        if platform.value in config[DOMAIN]:
            for device_config in config[DOMAIN][platform.value]:
                create_knx_device(platform, hass.data[DOMAIN].xknx, device_config)

    # We need to wait until all entities are loaded into the device list since they could also be created from other platforms
    for platform in SupportedPlatforms:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform.value, DOMAIN, {}, config)
        )

    if not hass.data[DOMAIN].xknx.devices:
        _LOGGER.warning(
            "No KNX devices are configured. Please read "
            "https://www.home-assistant.io/blog/2020/09/17/release-115/#breaking-changes"
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_KNX_SEND,
        hass.data[DOMAIN].service_send_to_knx_bus,
        schema=SERVICE_KNX_SEND_SCHEMA,
    )

    return True


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
            own_address=self.config[DOMAIN][CONF_KNX_INDIVIDUAL_ADDRESS],
            rate_limit=self.config[DOMAIN][CONF_KNX_RATE_LIMIT],
            multicast_group=self.config[DOMAIN][CONF_KNX_MCAST_GRP],
            multicast_port=self.config[DOMAIN][CONF_KNX_MCAST_PORT],
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
        gateway_port = self.config[DOMAIN][CONF_KNX_TUNNELING][CONF_PORT]
        local_ip = self.config[DOMAIN][CONF_KNX_TUNNELING].get(
            ConnectionSchema.CONF_KNX_LOCAL_IP
        )
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
            if expose_type.lower() in ["time", "date", "datetime"]:
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

        telegram = Telegram(group_address=address, payload=payload)
        await self.xknx.telegrams.put(telegram)


class KNXExposeTime:
    """Object to Expose Time/Date object to KNX bus."""

    def __init__(self, xknx: XKNX, expose_type: str, address: str):
        """Initialize of Expose class."""
        self.xknx = xknx
        self.expose_type = expose_type
        self.address = address
        self.device = None

    @callback
    def async_register(self):
        """Register listener."""
        self.device = DateTime(
            self.xknx,
            name=self.expose_type.capitalize(),
            broadcast_type=self.expose_type.upper(),
            localtime=True,
            group_address=self.address,
        )


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
