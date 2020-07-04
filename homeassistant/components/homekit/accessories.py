"""Extend the basic Accessory and Bridge functions."""
from datetime import timedelta
from functools import partial, wraps
from inspect import getmodule
import logging

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_OTHER

from homeassistant.components import cover, vacuum
from homeassistant.components.cover import DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE
from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_TYPE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    STATE_ON,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
    __version__,
)
from homeassistant.core import callback as ha_callback, split_entity_id
from homeassistant.helpers.event import (
    async_track_state_change,
    track_point_in_utc_time,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from .const import (
    ATTR_DISPLAY_NAME,
    ATTR_INTERGRATION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    ATTR_VALUE,
    BRIDGE_MODEL,
    BRIDGE_SERIAL_NUMBER,
    CHAR_BATTERY_LEVEL,
    CHAR_CHARGING_STATE,
    CHAR_STATUS_LOW_BATTERY,
    CONF_FEATURE_LIST,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    DEBOUNCE_TIMEOUT,
    DEFAULT_LOW_BATTERY_THRESHOLD,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_PM25,
    EVENT_HOMEKIT_CHANGED,
    HK_CHARGING,
    HK_NOT_CHARGABLE,
    HK_NOT_CHARGING,
    MANUFACTURER,
    SERV_BATTERY_SERVICE,
    TYPE_FAUCET,
    TYPE_OUTLET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_SWITCH,
    TYPE_VALVE,
)
from .util import (
    convert_to_float,
    dismiss_setup_message,
    format_sw_version,
    show_setup_message,
    validate_media_player_features,
)

_LOGGER = logging.getLogger(__name__)
SWITCH_TYPES = {
    TYPE_FAUCET: "Valve",
    TYPE_OUTLET: "Outlet",
    TYPE_SHOWER: "Valve",
    TYPE_SPRINKLER: "Valve",
    TYPE_SWITCH: "Switch",
    TYPE_VALVE: "Valve",
}
TYPES = Registry()


def debounce(func):
    """Decorate function to debounce callbacks from HomeKit."""

    @ha_callback
    def call_later_listener(self, *args):
        """Handle call_later callback."""
        debounce_params = self.debounce.pop(func.__name__, None)
        if debounce_params:
            self.hass.async_add_executor_job(func, self, *debounce_params[1:])

    @wraps(func)
    def wrapper(self, *args):
        """Start async timer."""
        debounce_params = self.debounce.pop(func.__name__, None)
        if debounce_params:
            debounce_params[0]()  # remove listener
        remove_listener = track_point_in_utc_time(
            self.hass,
            partial(call_later_listener, self),
            dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT),
        )
        self.debounce[func.__name__] = (remove_listener, *args)
        logger.debug(
            "%s: Start %s timeout", self.entity_id, func.__name__.replace("set_", "")
        )

    name = getmodule(func).__name__
    logger = logging.getLogger(name)
    return wrapper


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

    elif state.domain == "humidifier":
        a_type = "HumidifierDehumidifier"

    elif state.domain == "light":
        a_type = "Light"

    elif state.domain == "lock":
        a_type = "Lock"

    elif state.domain == "media_player":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        feature_list = config.get(CONF_FEATURE_LIST, [])

        if device_class == DEVICE_CLASS_TV:
            a_type = "TelevisionMediaPlayer"
        elif validate_media_player_features(state, feature_list):
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

    elif state.domain == "camera":
        a_type = "Camera"

    if a_type is None:
        return None

    _LOGGER.debug('Add "%s" as "%s"', state.entity_id, a_type)
    return TYPES[a_type](hass, driver, name, state.entity_id, aid, config)


class HomeAccessory(Accessory):
    """Adapter class for Accessory."""

    def __init__(
        self,
        hass,
        driver,
        name,
        entity_id,
        aid,
        config,
        *args,
        category=CATEGORY_OTHER,
        **kwargs,
    ):
        """Initialize a Accessory object."""
        super().__init__(driver=driver, display_name=name, aid=aid, *args, **kwargs)
        self.config = config or {}
        domain = split_entity_id(entity_id)[0].replace("_", " ")

        if ATTR_MANUFACTURER in self.config:
            manufacturer = self.config[ATTR_MANUFACTURER]
        elif ATTR_INTERGRATION in self.config:
            manufacturer = self.config[ATTR_INTERGRATION].replace("_", " ").title()
        else:
            manufacturer = f"{MANUFACTURER} {domain}".title()
        if ATTR_MODEL in self.config:
            model = self.config[ATTR_MODEL]
        else:
            model = domain.title()
        if ATTR_SOFTWARE_VERSION in self.config:
            sw_version = format_sw_version(self.config[ATTR_SOFTWARE_VERSION])
        else:
            sw_version = __version__

        self.set_info_service(
            manufacturer=manufacturer,
            model=model,
            serial_number=entity_id,
            firmware_revision=sw_version,
        )

        self.category = category
        self.entity_id = entity_id
        self.hass = hass
        self.debounce = {}
        self._subscriptions = []
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        self.linked_battery_sensor = self.config.get(CONF_LINKED_BATTERY_SENSOR)
        self.linked_battery_charging_sensor = self.config.get(
            CONF_LINKED_BATTERY_CHARGING_SENSOR
        )
        self.low_battery_threshold = self.config.get(
            CONF_LOW_BATTERY_THRESHOLD, DEFAULT_LOW_BATTERY_THRESHOLD
        )

        """Add battery service if available"""
        entity_attributes = self.hass.states.get(self.entity_id).attributes
        battery_found = entity_attributes.get(ATTR_BATTERY_LEVEL)

        if self.linked_battery_sensor:
            state = self.hass.states.get(self.linked_battery_sensor)
            if state is not None:
                battery_found = state.state
            else:
                self.linked_battery_sensor = None
                _LOGGER.warning(
                    "%s: Battery sensor state missing: %s",
                    self.entity_id,
                    self.linked_battery_sensor,
                )

        if not battery_found:
            return

        _LOGGER.debug("%s: Found battery level", self.entity_id)

        if self.linked_battery_charging_sensor:
            state = self.hass.states.get(self.linked_battery_charging_sensor)
            if state is None:
                self.linked_battery_charging_sensor = None
                _LOGGER.warning(
                    "%s: Battery charging binary_sensor state missing: %s",
                    self.entity_id,
                    self.linked_battery_charging_sensor,
                )
            else:
                _LOGGER.debug("%s: Found battery charging", self.entity_id)

        serv_battery = self.add_preload_service(SERV_BATTERY_SERVICE)
        self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=0)
        self._char_charging = serv_battery.configure_char(
            CHAR_CHARGING_STATE, value=HK_NOT_CHARGABLE
        )
        self._char_low_battery = serv_battery.configure_char(
            CHAR_STATUS_LOW_BATTERY, value=0
        )

    @property
    def available(self):
        """Return if accessory is available."""
        state = self.hass.states.get(self.entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    async def run(self):
        """Handle accessory driver started event.

        Run inside the HAP-python event loop.
        """
        self.hass.add_job(self.run_handler)

    async def run_handler(self):
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        state = self.hass.states.get(self.entity_id)
        self.async_update_state_callback(None, None, state)
        self._subscriptions.append(
            async_track_state_change(
                self.hass, self.entity_id, self.async_update_state_callback
            )
        )

        battery_charging_state = None
        battery_state = None
        if self.linked_battery_sensor:
            linked_battery_sensor_state = self.hass.states.get(
                self.linked_battery_sensor
            )
            battery_state = linked_battery_sensor_state.state
            battery_charging_state = linked_battery_sensor_state.attributes.get(
                ATTR_BATTERY_CHARGING
            )
            self._subscriptions.append(
                async_track_state_change(
                    self.hass,
                    self.linked_battery_sensor,
                    self.async_update_linked_battery_callback,
                )
            )
        else:
            battery_state = state.attributes.get(ATTR_BATTERY_LEVEL)
        if self.linked_battery_charging_sensor:
            battery_charging_state = (
                self.hass.states.get(self.linked_battery_charging_sensor).state
                == STATE_ON
            )
            self._subscriptions.append(
                async_track_state_change(
                    self.hass,
                    self.linked_battery_charging_sensor,
                    self.async_update_linked_battery_charging_callback,
                )
            )
        elif battery_charging_state is None:
            battery_charging_state = state.attributes.get(ATTR_BATTERY_CHARGING)

        if battery_state is not None or battery_charging_state is not None:
            self.async_update_battery(battery_state, battery_charging_state)

    @ha_callback
    def async_update_state_callback(
        self, entity_id=None, old_state=None, new_state=None
    ):
        """Handle state change listener callback."""
        _LOGGER.debug("New_state: %s", new_state)
        if new_state is None:
            return
        battery_state = None
        battery_charging_state = None
        if (
            not self.linked_battery_sensor
            and ATTR_BATTERY_LEVEL in new_state.attributes
        ):
            battery_state = new_state.attributes.get(ATTR_BATTERY_LEVEL)
        if (
            not self.linked_battery_charging_sensor
            and ATTR_BATTERY_CHARGING in new_state.attributes
        ):
            battery_charging_state = new_state.attributes.get(ATTR_BATTERY_CHARGING)
        if battery_state is not None or battery_charging_state is not None:
            self.async_update_battery(battery_state, battery_charging_state)
        self.async_update_state(new_state)

    @ha_callback
    def async_update_linked_battery_callback(
        self, entity_id=None, old_state=None, new_state=None
    ):
        """Handle linked battery sensor state change listener callback."""
        if self.linked_battery_charging_sensor:
            battery_charging_state = None
        else:
            battery_charging_state = new_state.attributes.get(ATTR_BATTERY_CHARGING)
        self.async_update_battery(new_state.state, battery_charging_state)

    @ha_callback
    def async_update_linked_battery_charging_callback(
        self, entity_id=None, old_state=None, new_state=None
    ):
        """Handle linked battery charging sensor state change listener callback."""
        self.async_update_battery(None, new_state.state == STATE_ON)

    @ha_callback
    def async_update_battery(self, battery_level, battery_charging):
        """Update battery service if available.

        Only call this function if self._support_battery_level is True.
        """
        if not self._char_battery:
            # Battery appeared after homekit was started
            return

        battery_level = convert_to_float(battery_level)
        if battery_level is not None:
            if self._char_battery.value != battery_level:
                self._char_battery.set_value(battery_level)
            is_low_battery = 1 if battery_level < self.low_battery_threshold else 0
            if self._char_low_battery.value != is_low_battery:
                self._char_low_battery.set_value(is_low_battery)
                _LOGGER.debug(
                    "%s: Updated battery level to %d", self.entity_id, battery_level
                )

        # Charging state can appear after homekit was started
        if battery_charging is None or not self._char_charging:
            return

        hk_charging = HK_CHARGING if battery_charging else HK_NOT_CHARGING
        if self._char_charging.value != hk_charging:
            self._char_charging.set_value(hk_charging)
            _LOGGER.debug(
                "%s: Updated battery charging to %d", self.entity_id, hk_charging
            )

    @ha_callback
    def async_update_state(self, new_state):
        """Handle state change to update HomeKit value.

        Overridden by accessory types.
        """
        raise NotImplementedError()

    def call_service(self, domain, service, service_data, value=None):
        """Fire event and call service for changes from HomeKit."""
        self.hass.add_job(self.async_call_service, domain, service, service_data, value)

    async def async_call_service(self, domain, service, service_data, value=None):
        """Fire event and call service for changes from HomeKit.

        This method must be run in the event loop.
        """
        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_DISPLAY_NAME: self.display_name,
            ATTR_SERVICE: service,
            ATTR_VALUE: value,
        }

        self.hass.bus.async_fire(EVENT_HOMEKIT_CHANGED, event_data)
        await self.hass.services.async_call(domain, service, service_data)

    @ha_callback
    def async_stop(self):
        """Cancel any subscriptions when the bridge is stopped."""
        while self._subscriptions:
            self._subscriptions.pop(0)()


class HomeBridge(Bridge):
    """Adapter class for Bridge."""

    def __init__(self, hass, driver, name):
        """Initialize a Bridge object."""
        super().__init__(driver, name)
        self.set_info_service(
            firmware_revision=__version__,
            manufacturer=MANUFACTURER,
            model=BRIDGE_MODEL,
            serial_number=BRIDGE_SERIAL_NUMBER,
        )
        self.hass = hass

    def setup_message(self):
        """Prevent print of pyhap setup message to terminal."""

    def get_snapshot(self, info):
        """Get snapshot from accessory if supported."""
        acc = self.accessories.get(info["aid"])
        if acc is None:
            raise ValueError("Requested snapshot for missing accessory")
        if not hasattr(acc, "get_snapshot"):
            raise ValueError(
                "Got a request for snapshot, but the Accessory "
                'does not define a "get_snapshot" method'
            )
        return acc.get_snapshot(info)


class HomeDriver(AccessoryDriver):
    """Adapter class for AccessoryDriver."""

    def __init__(self, hass, entry_id, bridge_name, **kwargs):
        """Initialize a AccessoryDriver object."""
        super().__init__(**kwargs)
        self.hass = hass
        self._entry_id = entry_id
        self._bridge_name = bridge_name

    def pair(self, client_uuid, client_public):
        """Override super function to dismiss setup message if paired."""
        success = super().pair(client_uuid, client_public)
        if success:
            dismiss_setup_message(self.hass, self._entry_id)
        return success

    def unpair(self, client_uuid):
        """Override super function to show setup message if unpaired."""
        super().unpair(client_uuid)
        show_setup_message(
            self.hass,
            self._entry_id,
            self._bridge_name,
            self.state.pincode,
            self.accessory.xhm_uri(),
        )
