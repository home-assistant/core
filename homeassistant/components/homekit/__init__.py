"""Support for Apple HomeKit."""
import ipaddress
import logging

from aiohttp import web
import voluptuous as vol
from zeroconf import InterfaceChoice

from homeassistant.components import cover, vacuum
from homeassistant.components.binary_sensor import DEVICE_CLASS_BATTERY_CHARGING
from homeassistant.components.cover import DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)
from homeassistant.core import callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry

from .aidmanager import AccessoryAidStorage
from .const import (
    AID_STORAGE,
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    BRIDGE_NAME,
    CONF_ADVERTISE_IP,
    CONF_AUTO_START,
    CONF_ENTITY_CONFIG,
    CONF_FEATURE_LIST,
    CONF_FILTER,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_SAFE_MODE,
    CONF_ZEROCONF_DEFAULT_INTERFACE,
    DEFAULT_AUTO_START,
    DEFAULT_PORT,
    DEFAULT_SAFE_MODE,
    DEFAULT_ZEROCONF_DEFAULT_INTERFACE,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_PM25,
    DOMAIN,
    EVENT_HOMEKIT_CHANGED,
    HOMEKIT_FILE,
    HOMEKIT_PAIRING_QR,
    HOMEKIT_PAIRING_QR_SECRET,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_START,
    TYPE_FAUCET,
    TYPE_OUTLET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_SWITCH,
    TYPE_VALVE,
)
from .util import (
    show_setup_message,
    validate_entity_config,
    validate_media_player_features,
)

_LOGGER = logging.getLogger(__name__)

MAX_DEVICES = 150
TYPES = Registry()

# #### Driver Status ####
STATUS_READY = 0
STATUS_RUNNING = 1
STATUS_STOPPED = 2
STATUS_WAIT = 3

SWITCH_TYPES = {
    TYPE_FAUCET: "Valve",
    TYPE_OUTLET: "Outlet",
    TYPE_SHOWER: "Valve",
    TYPE_SPRINKLER: "Valve",
    TYPE_SWITCH: "Switch",
    TYPE_VALVE: "Valve",
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Optional(CONF_NAME, default=BRIDGE_NAME): vol.All(
                    cv.string, vol.Length(min=3, max=25)
                ),
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): vol.All(ipaddress.ip_address, cv.string),
                vol.Optional(CONF_ADVERTISE_IP): vol.All(
                    ipaddress.ip_address, cv.string
                ),
                vol.Optional(CONF_AUTO_START, default=DEFAULT_AUTO_START): cv.boolean,
                vol.Optional(CONF_SAFE_MODE, default=DEFAULT_SAFE_MODE): cv.boolean,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config,
                vol.Optional(
                    CONF_ZEROCONF_DEFAULT_INTERFACE,
                    default=DEFAULT_ZEROCONF_DEFAULT_INTERFACE,
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RESET_ACCESSORY_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_ids}
)


async def async_setup(hass, config):
    """Set up the HomeKit component."""
    _LOGGER.debug("Begin setup HomeKit")

    aid_storage = hass.data[AID_STORAGE] = AccessoryAidStorage(hass)
    await aid_storage.async_initialize()

    hass.http.register_view(HomeKitPairingQRView)

    conf = config[DOMAIN]
    name = conf[CONF_NAME]
    port = conf[CONF_PORT]
    ip_address = conf.get(CONF_IP_ADDRESS)
    advertise_ip = conf.get(CONF_ADVERTISE_IP)
    auto_start = conf[CONF_AUTO_START]
    safe_mode = conf[CONF_SAFE_MODE]
    entity_filter = conf[CONF_FILTER]
    entity_config = conf[CONF_ENTITY_CONFIG]
    interface_choice = (
        InterfaceChoice.Default if conf.get(CONF_ZEROCONF_DEFAULT_INTERFACE) else None
    )

    homekit = HomeKit(
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        entity_config,
        safe_mode,
        advertise_ip,
        interface_choice,
    )
    await hass.async_add_executor_job(homekit.setup)

    def handle_homekit_reset_accessory(service):
        """Handle start HomeKit service call."""
        if homekit.status != STATUS_RUNNING:
            _LOGGER.warning(
                "HomeKit is not running. Either it is waiting to be "
                "started or has been stopped."
            )
            return

        entity_ids = service.data.get("entity_id")
        homekit.reset_accessories(entity_ids)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_RESET_ACCESSORY,
        handle_homekit_reset_accessory,
        schema=RESET_ACCESSORY_SERVICE_SCHEMA,
    )

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        data = event.data
        entity_id = data.get(ATTR_ENTITY_ID)
        value = data.get(ATTR_VALUE)

        value_msg = f" to {value}" if value else ""
        message = f"send command {data[ATTR_SERVICE]}{value_msg} for {data[ATTR_DISPLAY_NAME]}"

        return {
            "name": "HomeKit",
            "message": message,
            "entity_id": entity_id,
        }

    hass.components.logbook.async_describe_event(
        DOMAIN, EVENT_HOMEKIT_CHANGED, async_describe_logbook_event
    )

    if auto_start:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, homekit.async_start)
        return True

    async def async_handle_homekit_service_start(service):
        """Handle start HomeKit service call."""
        if homekit.status != STATUS_READY:
            _LOGGER.warning(
                "HomeKit is not ready. Either it is already running or has "
                "been stopped."
            )
            return
        await homekit.async_start()

    hass.services.async_register(
        DOMAIN, SERVICE_HOMEKIT_START, async_handle_homekit_service_start
    )

    return True


def get_accessory(hass, driver, state, aid, config):
    """Take state and return an accessory object if supported."""
    if not aid:
        _LOGGER.warning(
            'The entity "%s" is not supported, since it '
            "generates an invalid aid, please change it.",
            state.entity_id,
        )
        return None

    a_type = None
    name = config.get(CONF_NAME, state.name)

    if state.domain == "alarm_control_panel":
        a_type = "SecuritySystem"

    elif state.domain in ("binary_sensor", "device_tracker", "person"):
        a_type = "BinarySensor"

    elif state.domain == "climate":
        a_type = "Thermostat"

    elif state.domain == "cover":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if device_class in (DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE) and features & (
            cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE
        ):
            a_type = "GarageDoorOpener"
        elif features & cover.SUPPORT_SET_POSITION:
            a_type = "WindowCovering"
        elif features & (cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE):
            a_type = "WindowCoveringBasic"

    elif state.domain == "fan":
        a_type = "Fan"

    elif state.domain == "light":
        a_type = "Light"

    elif state.domain == "lock":
        a_type = "Lock"

    elif state.domain == "media_player":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        feature_list = config.get(CONF_FEATURE_LIST)

        if device_class == DEVICE_CLASS_TV:
            a_type = "TelevisionMediaPlayer"
        else:
            if feature_list and validate_media_player_features(state, feature_list):
                a_type = "MediaPlayer"

    elif state.domain == "sensor":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class == DEVICE_CLASS_TEMPERATURE or unit in (
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
        ):
            a_type = "TemperatureSensor"
        elif device_class == DEVICE_CLASS_HUMIDITY and unit == UNIT_PERCENTAGE:
            a_type = "HumiditySensor"
        elif device_class == DEVICE_CLASS_PM25 or DEVICE_CLASS_PM25 in state.entity_id:
            a_type = "AirQualitySensor"
        elif device_class == DEVICE_CLASS_CO:
            a_type = "CarbonMonoxideSensor"
        elif device_class == DEVICE_CLASS_CO2 or DEVICE_CLASS_CO2 in state.entity_id:
            a_type = "CarbonDioxideSensor"
        elif device_class == DEVICE_CLASS_ILLUMINANCE or unit in ("lm", "lx"):
            a_type = "LightSensor"

    elif state.domain == "switch":
        switch_type = config.get(CONF_TYPE, TYPE_SWITCH)
        a_type = SWITCH_TYPES[switch_type]

    elif state.domain == "vacuum":
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if features & (vacuum.SUPPORT_START | vacuum.SUPPORT_RETURN_HOME):
            a_type = "DockVacuum"
        else:
            a_type = "Switch"

    elif state.domain in ("automation", "input_boolean", "remote", "scene", "script"):
        a_type = "Switch"

    elif state.domain == "water_heater":
        a_type = "WaterHeater"

    if a_type is None:
        return None

    _LOGGER.debug('Add "%s" as "%s"', state.entity_id, a_type)
    return TYPES[a_type](hass, driver, name, state.entity_id, aid, config)


class HomeKit:
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(
        self,
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        entity_config,
        safe_mode,
        advertise_ip=None,
        interface_choice=None,
    ):
        """Initialize a HomeKit object."""
        self.hass = hass
        self._name = name
        self._port = port
        self._ip_address = ip_address
        self._filter = entity_filter
        self._config = entity_config
        self._safe_mode = safe_mode
        self._advertise_ip = advertise_ip
        self._interface_choice = interface_choice
        self.status = STATUS_READY

        self.bridge = None
        self.driver = None

    def setup(self):
        """Set up bridge and accessory driver."""
        # pylint: disable=import-outside-toplevel
        from .accessories import HomeBridge, HomeDriver

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)

        ip_addr = self._ip_address or get_local_ip()
        path = self.hass.config.path(HOMEKIT_FILE)
        self.driver = HomeDriver(
            self.hass,
            address=ip_addr,
            port=self._port,
            persist_file=path,
            advertised_address=self._advertise_ip,
            interface_choice=self._interface_choice,
        )
        self.bridge = HomeBridge(self.hass, self.driver, self._name)
        if self._safe_mode:
            _LOGGER.debug("Safe_mode selected")
            self.driver.safe_mode = True

    def reset_accessories(self, entity_ids):
        """Reset the accessory to load the latest configuration."""
        aid_storage = self.hass.data[AID_STORAGE]
        removed = []
        for entity_id in entity_ids:
            aid = aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
            if aid not in self.bridge.accessories:
                _LOGGER.warning(
                    "Could not reset accessory. entity_id not found %s", entity_id
                )
                continue
            acc = self.remove_bridge_accessory(aid)
            removed.append(acc)
        self.driver.config_changed()

        for acc in removed:
            self.bridge.add_accessory(acc)
        self.driver.config_changed()

    def add_bridge_accessory(self, state):
        """Try adding accessory to bridge if configured beforehand."""
        if not self._filter(state.entity_id):
            return

        # The bridge itself counts as an accessory
        if len(self.bridge.accessories) + 1 >= MAX_DEVICES:
            _LOGGER.warning(
                "Cannot add %s as this would exceeded the %d device limit. Consider using the filter option.",
                state.entity_id,
                MAX_DEVICES,
            )
            return

        aid = self.hass.data[AID_STORAGE].get_or_allocate_aid_for_entity_id(
            state.entity_id
        )
        conf = self._config.pop(state.entity_id, {})
        # If an accessory cannot be created or added due to an exception
        # of any kind (usually in pyhap) it should not prevent
        # the rest of the accessories from being created
        try:
            acc = get_accessory(self.hass, self.driver, state, aid, conf)
            if acc is not None:
                self.bridge.add_accessory(acc)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to create a HomeKit accessory for %s", state.entity_id
            )

    def remove_bridge_accessory(self, aid):
        """Try adding accessory to bridge if configured beforehand."""
        acc = None
        if aid in self.bridge.accessories:
            acc = self.bridge.accessories.pop(aid)
        return acc

    async def async_start(self, *args):
        """Start the accessory driver."""
        if self.status != STATUS_READY:
            return
        self.status = STATUS_WAIT

        ent_reg = await entity_registry.async_get_registry(self.hass)

        device_lookup = ent_reg.async_get_device_class_lookup(
            {
                ("binary_sensor", DEVICE_CLASS_BATTERY_CHARGING),
                ("sensor", DEVICE_CLASS_BATTERY),
            }
        )

        bridged_states = []
        for state in self.hass.states.async_all():
            if not self._filter(state.entity_id):
                continue

            self._async_configure_linked_battery_sensors(ent_reg, device_lookup, state)
            bridged_states.append(state)

        await self.hass.async_add_executor_job(self._start, bridged_states)

    def _start(self, bridged_states):
        from . import (  # noqa: F401 pylint: disable=unused-import, import-outside-toplevel
            type_covers,
            type_fans,
            type_lights,
            type_locks,
            type_media_players,
            type_security_systems,
            type_sensors,
            type_switches,
            type_thermostats,
        )

        for state in bridged_states:
            self.add_bridge_accessory(state)

        self.driver.add_accessory(self.bridge)

        if not self.driver.state.paired:
            show_setup_message(
                self.hass, self.driver.state.pincode, self.bridge.xhm_uri()
            )

        _LOGGER.debug("Driver start")
        self.hass.async_add_executor_job(self.driver.start)
        self.status = STATUS_RUNNING

    async def async_stop(self, *args):
        """Stop the accessory driver."""
        if self.status != STATUS_RUNNING:
            return
        self.status = STATUS_STOPPED

        _LOGGER.debug("Driver stop")
        self.hass.async_add_executor_job(self.driver.stop)

    @callback
    def _async_configure_linked_battery_sensors(self, ent_reg, device_lookup, state):
        entry = ent_reg.async_get(state.entity_id)

        if (
            entry is None
            or entry.device_id is None
            or entry.device_id not in device_lookup
            or entry.device_class
            in (DEVICE_CLASS_BATTERY_CHARGING, DEVICE_CLASS_BATTERY)
        ):
            return

        if ATTR_BATTERY_CHARGING not in state.attributes:
            battery_charging_binary_sensor_entity_id = device_lookup[
                entry.device_id
            ].get(("binary_sensor", DEVICE_CLASS_BATTERY_CHARGING))
            if battery_charging_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_CHARGING_SENSOR,
                    battery_charging_binary_sensor_entity_id,
                )

        if ATTR_BATTERY_LEVEL not in state.attributes:
            battery_sensor_entity_id = device_lookup[entry.device_id].get(
                ("sensor", DEVICE_CLASS_BATTERY)
            )
            if battery_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_SENSOR, battery_sensor_entity_id
                )


class HomeKitPairingQRView(HomeAssistantView):
    """Display the homekit pairing code at a protected url."""

    url = "/api/homekit/pairingqr"
    name = "api:homekit:pairingqr"
    requires_auth = False

    # pylint: disable=no-self-use
    async def get(self, request):
        """Retrieve the pairing QRCode image."""
        if request.query_string != request.app["hass"].data[HOMEKIT_PAIRING_QR_SECRET]:
            raise Unauthorized()
        return web.Response(
            body=request.app["hass"].data[HOMEKIT_PAIRING_QR],
            content_type="image/svg+xml",
        )
