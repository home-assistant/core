"""Extend the basic Accessory and Bridge functions."""
from __future__ import annotations

import logging
from typing import Any, cast
from uuid import UUID

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_OTHER
from pyhap.iid_manager import IIDManager
from pyhap.service import Service
from pyhap.util import callback as pyhap_callback

from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.remote import RemoteEntityFeature
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SERVICE,
    ATTR_SUPPORTED_FEATURES,
    ATTR_SW_VERSION,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_TYPE,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_ON,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    __version__,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    HomeAssistant,
    State,
    callback as ha_callback,
    split_entity_id,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.decorator import Registry

from .const import (
    ATTR_DISPLAY_NAME,
    ATTR_INTEGRATION,
    ATTR_VALUE,
    BRIDGE_MODEL,
    BRIDGE_SERIAL_NUMBER,
    CHAR_BATTERY_LEVEL,
    CHAR_CHARGING_STATE,
    CHAR_HARDWARE_REVISION,
    CHAR_STATUS_LOW_BATTERY,
    CONF_FEATURE_LIST,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    DEFAULT_LOW_BATTERY_THRESHOLD,
    DOMAIN,
    EVENT_HOMEKIT_CHANGED,
    HK_CHARGING,
    HK_NOT_CHARGABLE,
    HK_NOT_CHARGING,
    MANUFACTURER,
    MAX_MANUFACTURER_LENGTH,
    MAX_MODEL_LENGTH,
    MAX_SERIAL_LENGTH,
    MAX_VERSION_LENGTH,
    SERV_ACCESSORY_INFO,
    SERV_BATTERY_SERVICE,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    TYPE_FAUCET,
    TYPE_OUTLET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_SWITCH,
    TYPE_VALVE,
)
from .iidmanager import AccessoryIIDStorage
from .util import (
    accessory_friendly_name,
    async_dismiss_setup_message,
    async_show_setup_message,
    cleanup_name_for_homekit,
    convert_to_float,
    format_version,
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
TYPES: Registry[str, type[HomeAccessory]] = Registry()


def get_accessory(  # noqa: C901
    hass: HomeAssistant, driver: HomeDriver, state: State, aid: int | None, config: dict
) -> HomeAccessory | None:
    """Take state and return an accessory object if supported."""
    if not aid:
        _LOGGER.warning(
            'The entity "%s" is not supported, since it '
            "generates an invalid aid, please change it",
            state.entity_id,
        )
        return None

    a_type = None
    name = config.get(CONF_NAME, state.name)
    features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

    if state.domain == "alarm_control_panel":
        a_type = "SecuritySystem"

    elif state.domain in ("binary_sensor", "device_tracker", "person"):
        a_type = "BinarySensor"

    elif state.domain == "climate":
        a_type = "Thermostat"

    elif state.domain == "cover":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        if device_class in (
            CoverDeviceClass.GARAGE,
            CoverDeviceClass.GATE,
        ) and features & (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE):
            a_type = "GarageDoorOpener"
        elif (
            device_class == CoverDeviceClass.WINDOW
            and features & CoverEntityFeature.SET_POSITION
        ):
            a_type = "Window"
        elif features & CoverEntityFeature.SET_POSITION:
            a_type = "WindowCovering"
        elif features & (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE):
            a_type = "WindowCoveringBasic"
        elif features & CoverEntityFeature.SET_TILT_POSITION:
            # WindowCovering and WindowCoveringBasic both support tilt
            # only WindowCovering can handle the covers that are missing
            # CoverEntityFeature.SET_POSITION, CoverEntityFeature.OPEN,
            # and CoverEntityFeature.CLOSE
            a_type = "WindowCovering"

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

        if device_class == MediaPlayerDeviceClass.TV:
            a_type = "TelevisionMediaPlayer"
        elif validate_media_player_features(state, feature_list):
            a_type = "MediaPlayer"

    elif state.domain == "sensor":
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class == SensorDeviceClass.TEMPERATURE or unit in (
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
        ):
            a_type = "TemperatureSensor"
        elif device_class == SensorDeviceClass.HUMIDITY and unit == PERCENTAGE:
            a_type = "HumiditySensor"
        elif (
            device_class == SensorDeviceClass.PM10
            or SensorDeviceClass.PM10 in state.entity_id
        ):
            a_type = "PM10Sensor"
        elif (
            device_class == SensorDeviceClass.PM25
            or SensorDeviceClass.PM25 in state.entity_id
        ):
            a_type = "PM25Sensor"
        elif (
            device_class == SensorDeviceClass.GAS
            or SensorDeviceClass.GAS in state.entity_id
        ):
            a_type = "AirQualitySensor"
        elif device_class == SensorDeviceClass.CO:
            a_type = "CarbonMonoxideSensor"
        elif device_class == SensorDeviceClass.CO2 or "co2" in state.entity_id:
            a_type = "CarbonDioxideSensor"
        elif device_class == SensorDeviceClass.ILLUMINANCE or unit in ("lm", LIGHT_LUX):
            a_type = "LightSensor"

    elif state.domain == "switch":
        switch_type = config.get(CONF_TYPE, TYPE_SWITCH)
        a_type = SWITCH_TYPES[switch_type]

    elif state.domain == "vacuum":
        a_type = "Vacuum"

    elif state.domain == "remote" and features & RemoteEntityFeature.ACTIVITY:
        a_type = "ActivityRemote"

    elif state.domain in (
        "automation",
        "button",
        "input_boolean",
        "input_button",
        "remote",
        "scene",
        "script",
    ):
        a_type = "Switch"

    elif state.domain in ("input_select", "select"):
        a_type = "SelectSwitch"

    elif state.domain == "water_heater":
        a_type = "WaterHeater"

    elif state.domain == "camera":
        a_type = "Camera"

    if a_type is None:
        return None

    _LOGGER.debug('Add "%s" as "%s"', state.entity_id, a_type)
    return TYPES[a_type](hass, driver, name, state.entity_id, aid, config)


class HomeAccessory(Accessory):  # type: ignore[misc]
    """Adapter class for Accessory."""

    def __init__(
        self,
        hass: HomeAssistant,
        driver: HomeDriver,
        name: str,
        entity_id: str,
        aid: int,
        config: dict,
        *args: Any,
        category: str = CATEGORY_OTHER,
        device_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Accessory object."""
        super().__init__(
            driver=driver,
            display_name=cleanup_name_for_homekit(name),
            aid=aid,
            iid_manager=HomeIIDManager(driver.iid_storage),
            *args,
            **kwargs,
        )
        self.config = config or {}
        if device_id:
            self.device_id: str | None = device_id
            serial_number = device_id
            domain = None
        else:
            self.device_id = None
            serial_number = entity_id
            domain = split_entity_id(entity_id)[0].replace("_", " ")

        if self.config.get(ATTR_MANUFACTURER) is not None:
            manufacturer = str(self.config[ATTR_MANUFACTURER])
        elif self.config.get(ATTR_INTEGRATION) is not None:
            manufacturer = self.config[ATTR_INTEGRATION].replace("_", " ").title()
        elif domain:
            manufacturer = f"{MANUFACTURER} {domain}".title()
        else:
            manufacturer = MANUFACTURER
        if self.config.get(ATTR_MODEL) is not None:
            model = str(self.config[ATTR_MODEL])
        elif domain:
            model = domain.title()
        else:
            model = MANUFACTURER
        sw_version = None
        if self.config.get(ATTR_SW_VERSION) is not None:
            sw_version = format_version(self.config[ATTR_SW_VERSION])
        if sw_version is None:
            sw_version = format_version(__version__)
            assert sw_version is not None
        hw_version = None
        if self.config.get(ATTR_HW_VERSION) is not None:
            hw_version = format_version(self.config[ATTR_HW_VERSION])

        self.set_info_service(
            manufacturer=manufacturer[:MAX_MANUFACTURER_LENGTH],
            model=model[:MAX_MODEL_LENGTH],
            serial_number=serial_number[:MAX_SERIAL_LENGTH],
            firmware_revision=sw_version[:MAX_VERSION_LENGTH],
        )
        if hw_version:
            serv_info = self.get_service(SERV_ACCESSORY_INFO)
            char = self.driver.loader.get_char(CHAR_HARDWARE_REVISION)
            serv_info.add_characteristic(char)
            serv_info.configure_char(
                CHAR_HARDWARE_REVISION, value=hw_version[:MAX_VERSION_LENGTH]
            )
            char.broker = self
            self.iid_manager.assign(char)

        self.category = category
        self.entity_id = entity_id
        self.hass = hass
        self._subscriptions: list[CALLBACK_TYPE] = []

        if device_id:
            return

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
        state = self.hass.states.get(self.entity_id)
        assert state is not None
        entity_attributes = state.attributes
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
    def available(self) -> bool:
        """Return if accessory is available."""
        state = self.hass.states.get(self.entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    async def run(self) -> None:
        """Handle accessory driver started event."""
        if state := self.hass.states.get(self.entity_id):
            self.async_update_state_callback(state)
        self._subscriptions.append(
            async_track_state_change_event(
                self.hass, [self.entity_id], self.async_update_event_state_callback
            )
        )

        battery_charging_state = None
        battery_state = None
        if self.linked_battery_sensor and (
            linked_battery_sensor_state := self.hass.states.get(
                self.linked_battery_sensor
            )
        ):
            battery_state = linked_battery_sensor_state.state
            battery_charging_state = linked_battery_sensor_state.attributes.get(
                ATTR_BATTERY_CHARGING
            )
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_battery_sensor],
                    self.async_update_linked_battery_callback,
                )
            )
        elif state is not None:
            battery_state = state.attributes.get(ATTR_BATTERY_LEVEL)
        if self.linked_battery_charging_sensor:
            state = self.hass.states.get(self.linked_battery_charging_sensor)
            battery_charging_state = state and state.state == STATE_ON
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_battery_charging_sensor],
                    self.async_update_linked_battery_charging_callback,
                )
            )
        elif battery_charging_state is None and state is not None:
            battery_charging_state = state.attributes.get(ATTR_BATTERY_CHARGING)

        if battery_state is not None or battery_charging_state is not None:
            self.async_update_battery(battery_state, battery_charging_state)

    @ha_callback
    def async_update_event_state_callback(self, event: Event) -> None:
        """Handle state change event listener callback."""
        self.async_update_state_callback(event.data.get("new_state"))

    @ha_callback
    def async_update_state_callback(self, new_state: State | None) -> None:
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
    def async_update_linked_battery_callback(self, event: Event) -> None:
        """Handle linked battery sensor state change listener callback."""
        if (new_state := event.data.get("new_state")) is None:
            return
        if self.linked_battery_charging_sensor:
            battery_charging_state = None
        else:
            battery_charging_state = new_state.attributes.get(ATTR_BATTERY_CHARGING)
        self.async_update_battery(new_state.state, battery_charging_state)

    @ha_callback
    def async_update_linked_battery_charging_callback(self, event: Event) -> None:
        """Handle linked battery charging sensor state change listener callback."""
        if (new_state := event.data.get("new_state")) is None:
            return
        self.async_update_battery(None, new_state.state == STATE_ON)

    @ha_callback
    def async_update_battery(self, battery_level: Any, battery_charging: Any) -> None:
        """Update battery service if available.

        Only call this function if self._support_battery_level is True.
        """
        if not self._char_battery or not self._char_low_battery:
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
    def async_update_state(self, new_state: State) -> None:
        """Handle state change to update HomeKit value.

        Overridden by accessory types.
        """
        raise NotImplementedError()

    @ha_callback
    def async_call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None,
        value: Any | None = None,
    ) -> None:
        """Fire event and call service for changes from HomeKit."""
        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_DISPLAY_NAME: self.display_name,
            ATTR_SERVICE: service,
            ATTR_VALUE: value,
        }
        context = Context()

        self.hass.bus.async_fire(EVENT_HOMEKIT_CHANGED, event_data, context=context)
        self.hass.async_create_task(
            self.hass.services.async_call(
                domain, service, service_data, context=context
            )
        )

    @ha_callback
    def async_reset(self) -> None:
        """Reset and recreate an accessory."""
        self.hass.async_create_task(
            self.hass.services.async_call(
                DOMAIN,
                SERVICE_HOMEKIT_RESET_ACCESSORY,
                {ATTR_ENTITY_ID: self.entity_id},
            )
        )

    async def stop(self) -> None:
        """Cancel any subscriptions when the bridge is stopped."""
        while self._subscriptions:
            self._subscriptions.pop(0)()


class HomeBridge(Bridge):  # type: ignore[misc]
    """Adapter class for Bridge."""

    def __init__(self, hass: HomeAssistant, driver: HomeDriver, name: str) -> None:
        """Initialize a Bridge object."""
        super().__init__(driver, name, iid_manager=HomeIIDManager(driver.iid_storage))
        self.set_info_service(
            firmware_revision=format_version(__version__),
            manufacturer=MANUFACTURER,
            model=BRIDGE_MODEL,
            serial_number=BRIDGE_SERIAL_NUMBER,
        )
        self.hass = hass

    def setup_message(self) -> None:
        """Prevent print of pyhap setup message to terminal."""

    async def async_get_snapshot(self, info: dict) -> bytes:
        """Get snapshot from accessory if supported."""
        if (acc := self.accessories.get(info["aid"])) is None:
            raise ValueError("Requested snapshot for missing accessory")
        if not hasattr(acc, "async_get_snapshot"):
            raise ValueError(
                "Got a request for snapshot, but the Accessory "
                'does not define a "async_get_snapshot" method'
            )
        return cast(bytes, await acc.async_get_snapshot(info))


class HomeDriver(AccessoryDriver):  # type: ignore[misc]
    """Adapter class for AccessoryDriver."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        bridge_name: str,
        entry_title: str,
        iid_storage: AccessoryIIDStorage,
        **kwargs: Any,
    ) -> None:
        """Initialize a AccessoryDriver object."""
        super().__init__(**kwargs)
        self.hass = hass
        self._entry_id = entry_id
        self._bridge_name = bridge_name
        self._entry_title = entry_title
        self.iid_storage = iid_storage

    @pyhap_callback  # type: ignore[misc]
    def pair(
        self, client_uuid: UUID, client_public: str, client_permissions: int
    ) -> bool:
        """Override super function to dismiss setup message if paired."""
        success = super().pair(client_uuid, client_public, client_permissions)
        if success:
            async_dismiss_setup_message(self.hass, self._entry_id)
        return cast(bool, success)

    @pyhap_callback  # type: ignore[misc]
    def unpair(self, client_uuid: UUID) -> None:
        """Override super function to show setup message if unpaired."""
        super().unpair(client_uuid)

        if self.state.paired:
            return

        async_show_setup_message(
            self.hass,
            self._entry_id,
            accessory_friendly_name(self._entry_title, self.accessory),
            self.state.pincode,
            self.accessory.xhm_uri(),
        )


class HomeIIDManager(IIDManager):  # type: ignore[misc]
    """IID Manager that remembers IIDs between restarts."""

    def __init__(self, iid_storage: AccessoryIIDStorage) -> None:
        """Initialize a IIDManager object."""
        super().__init__()
        self._iid_storage = iid_storage

    def get_iid_for_obj(self, obj: Characteristic | Service) -> int:
        """Get IID for object."""
        aid = obj.broker.aid
        if isinstance(obj, Characteristic):
            service = obj.service
            iid = self._iid_storage.get_or_allocate_iid(
                aid, service.type_id, service.unique_id, obj.type_id, obj.unique_id
            )
        else:
            iid = self._iid_storage.get_or_allocate_iid(
                aid, obj.type_id, obj.unique_id, None, None
            )
        if iid in self.objs:
            raise RuntimeError(
                f"Cannot assign IID {iid} to {obj} as it is already in use by: {self.objs[iid]}"
            )
        return iid
