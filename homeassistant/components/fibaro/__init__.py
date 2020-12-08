"""Support for the Fibaro devices."""
from collections import defaultdict
import logging
from typing import Optional

from fiblary3.client.v4.client import Client as FibaroClient, StateHandler
import voluptuous as vol

from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_ICON,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_WHITE_VALUE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert, slugify

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_ENERGY_KWH = "current_energy_kwh"
ATTR_CURRENT_POWER_W = "current_power_w"

CONF_COLOR = "color"
CONF_DEVICE_CONFIG = "device_config"
CONF_DIMMING = "dimming"
CONF_GATEWAYS = "gateways"
CONF_PLUGINS = "plugins"
CONF_RESET_COLOR = "reset_color"
DOMAIN = "fibaro"
FIBARO_CONTROLLERS = "fibaro_controllers"
FIBARO_DEVICES = "fibaro_devices"
FIBARO_COMPONENTS = [
    "binary_sensor",
    "climate",
    "cover",
    "light",
    "scene",
    "sensor",
    "lock",
    "switch",
]

FIBARO_TYPEMAP = {
    "com.fibaro.multilevelSensor": "sensor",
    "com.fibaro.binarySwitch": "switch",
    "com.fibaro.multilevelSwitch": "switch",
    "com.fibaro.FGD212": "light",
    "com.fibaro.FGR": "cover",
    "com.fibaro.doorSensor": "binary_sensor",
    "com.fibaro.doorWindowSensor": "binary_sensor",
    "com.fibaro.FGMS001": "binary_sensor",
    "com.fibaro.heatDetector": "binary_sensor",
    "com.fibaro.lifeDangerSensor": "binary_sensor",
    "com.fibaro.smokeSensor": "binary_sensor",
    "com.fibaro.remoteSwitch": "switch",
    "com.fibaro.sensor": "sensor",
    "com.fibaro.colorController": "light",
    "com.fibaro.securitySensor": "binary_sensor",
    "com.fibaro.hvac": "climate",
    "com.fibaro.setpoint": "climate",
    "com.fibaro.FGT001": "climate",
    "com.fibaro.thermostatDanfoss": "climate",
    "com.fibaro.doorLock": "lock",
}

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema(
    {
        vol.Optional(CONF_DIMMING): cv.boolean,
        vol.Optional(CONF_COLOR): cv.boolean,
        vol.Optional(CONF_WHITE_VALUE): cv.boolean,
        vol.Optional(CONF_RESET_COLOR): cv.boolean,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Optional(CONF_ICON): cv.string,
    }
)

FIBARO_ID_LIST_SCHEMA = vol.Schema([cv.string])

GATEWAY_CONFIG = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_URL): cv.url,
        vol.Optional(CONF_PLUGINS, default=False): cv.boolean,
        vol.Optional(CONF_EXCLUDE, default=[]): FIBARO_ID_LIST_SCHEMA,
        vol.Optional(CONF_DEVICE_CONFIG, default={}): vol.Schema(
            {cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_GATEWAYS): vol.All(cv.ensure_list, [GATEWAY_CONFIG])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class FibaroController:
    """Initiate Fibaro Controller Class."""

    def __init__(self, config):
        """Initialize the Fibaro controller."""

        self._client = FibaroClient(
            config[CONF_URL], config[CONF_USERNAME], config[CONF_PASSWORD]
        )
        self._scene_map = None
        # Whether to import devices from plugins
        self._import_plugins = config[CONF_PLUGINS]
        self._device_config = config[CONF_DEVICE_CONFIG]
        self._room_map = None  # Mapping roomId to room object
        self._device_map = None  # Mapping deviceId to device object
        self.fibaro_devices = None  # List of devices by type
        self._callbacks = {}  # Update value callbacks by deviceId
        self._state_handler = None  # Fiblary's StateHandler object
        self._excluded_devices = config[CONF_EXCLUDE]
        self.hub_serial = None  # Unique serial number of the hub

    def connect(self):
        """Start the communication with the Fibaro controller."""
        try:
            login = self._client.login.get()
            info = self._client.info.get()
            self.hub_serial = slugify(info.serialNumber)
        except AssertionError:
            _LOGGER.error("Can't connect to Fibaro HC. Please check URL")
            return False
        if login is None or login.status is False:
            _LOGGER.error(
                "Invalid login for Fibaro HC. Please check username and password"
            )
            return False

        self._room_map = {room.id: room for room in self._client.rooms.list()}
        self._read_devices()
        self._read_scenes()
        return True

    def enable_state_handler(self):
        """Start StateHandler thread for monitoring updates."""
        self._state_handler = StateHandler(self._client, self._on_state_change)

    def disable_state_handler(self):
        """Stop StateHandler thread used for monitoring updates."""
        self._state_handler.stop()
        self._state_handler = None

    def _on_state_change(self, state):
        """Handle change report received from the HomeCenter."""
        callback_set = set()
        for change in state.get("changes", []):
            try:
                dev_id = change.pop("id")
                if dev_id not in self._device_map:
                    continue
                device = self._device_map[dev_id]
                for property_name, value in change.items():
                    if property_name == "log":
                        if value and value != "transfer OK":
                            _LOGGER.debug("LOG %s: %s", device.friendly_name, value)
                        continue
                    if property_name == "logTemp":
                        continue
                    if property_name in device.properties:
                        device.properties[property_name] = value
                        _LOGGER.debug(
                            "<- %s.%s = %s", device.ha_id, property_name, str(value)
                        )
                    else:
                        _LOGGER.warning("%s.%s not found", device.ha_id, property_name)
                    if dev_id in self._callbacks:
                        callback_set.add(dev_id)
            except (ValueError, KeyError):
                pass
        for item in callback_set:
            self._callbacks[item]()

    def register(self, device_id, callback):
        """Register device with a callback for updates."""
        self._callbacks[device_id] = callback

    def get_children(self, device_id):
        """Get a list of child devices."""
        return [
            device
            for device in self._device_map.values()
            if device.parentId == device_id
        ]

    def get_children2(self, device_id, endpoint_id):
        """Get a list of child devices for the same endpoint."""
        return [
            device
            for device in self._device_map.values()
            if device.parentId == device_id
            and (
                "endPointId" not in device.properties
                or device.properties.endPointId == endpoint_id
            )
        ]

    def get_siblings(self, device):
        """Get the siblings of a device."""
        if "endPointId" in device.properties:
            return self.get_children2(
                self._device_map[device.id].parentId,
                self._device_map[device.id].properties.endPointId,
            )
        return self.get_children(self._device_map[device.id].parentId)

    @staticmethod
    def _map_device_to_type(device):
        """Map device to HA device type."""
        # Use our lookup table to identify device type
        device_type = None
        if "type" in device:
            device_type = FIBARO_TYPEMAP.get(device.type)
        if device_type is None and "baseType" in device:
            device_type = FIBARO_TYPEMAP.get(device.baseType)

        # We can also identify device type by its capabilities
        if device_type is None:
            if "setBrightness" in device.actions:
                device_type = "light"
            elif "turnOn" in device.actions:
                device_type = "switch"
            elif "open" in device.actions:
                device_type = "cover"
            elif "secure" in device.actions:
                device_type = "lock"
            elif "value" in device.properties:
                if device.properties.value in ("true", "false"):
                    device_type = "binary_sensor"
                else:
                    device_type = "sensor"

        # Switches that control lights should show up as lights
        if device_type == "switch" and device.properties.get("isLight", False):
            device_type = "light"
        return device_type

    def _read_scenes(self):
        scenes = self._client.scenes.list()
        self._scene_map = {}
        for device in scenes:
            if "name" not in device or "id" not in device:
                continue
            device.fibaro_controller = self
            if "roomID" not in device or device.roomID == 0:
                room_name = "Unknown"
            else:
                room_name = self._room_map[device.roomID].name
            device.room_name = room_name
            device.friendly_name = f"{room_name} {device.name}"
            device.ha_id = (
                f"scene_{slugify(room_name)}_{slugify(device.name)}_{device.id}"
            )
            device.unique_id_str = f"{self.hub_serial}.scene.{device.id}"
            self._scene_map[device.id] = device
            self.fibaro_devices["scene"].append(device)
            _LOGGER.debug("%s scene -> %s", device.ha_id, device)

    def _read_devices(self):
        """Read and process the device list."""
        devices = self._client.devices.list()
        self._device_map = {}
        self.fibaro_devices = defaultdict(list)
        last_climate_parent = None
        last_endpoint = None
        for device in devices:
            try:
                if "name" not in device or "id" not in device:
                    continue
                device.fibaro_controller = self
                if "roomID" not in device or device.roomID == 0:
                    room_name = "Unknown"
                else:
                    room_name = self._room_map[device.roomID].name
                device.room_name = room_name
                device.friendly_name = f"{room_name} {device.name}"
                device.ha_id = (
                    f"{slugify(room_name)}_{slugify(device.name)}_{device.id}"
                )
                if (
                    device.enabled
                    and (
                        "isPlugin" not in device
                        or (not device.isPlugin or self._import_plugins)
                    )
                    and device.ha_id not in self._excluded_devices
                ):
                    device.mapped_type = self._map_device_to_type(device)
                    device.device_config = self._device_config.get(device.ha_id, {})
                else:
                    device.mapped_type = None
                dtype = device.mapped_type
                if dtype is None:
                    continue
                device.unique_id_str = f"{self.hub_serial}.{device.id}"
                self._device_map[device.id] = device
                _LOGGER.debug(
                    "%s (%s, %s) -> %s %s",
                    device.ha_id,
                    device.type,
                    device.baseType,
                    dtype,
                    str(device),
                )
                if dtype != "climate":
                    self.fibaro_devices[dtype].append(device)
                    continue
                # We group climate devices into groups with the same
                # endPointID belonging to the same parent device.
                if "endPointId" in device.properties:
                    _LOGGER.debug(
                        "climate device: %s, endPointId: %s",
                        device.ha_id,
                        device.properties.endPointId,
                    )
                else:
                    _LOGGER.debug("climate device: %s, no endPointId", device.ha_id)
                # If a sibling of this device has been added, skip this one
                # otherwise add the first visible device in the group
                # which is a hack, but solves a problem with FGT having
                # hidden compatibility devices before the real device
                if last_climate_parent != device.parentId or (
                    "endPointId" in device.properties
                    and last_endpoint != device.properties.endPointId
                ):
                    _LOGGER.debug("Handle separately")
                    self.fibaro_devices[dtype].append(device)
                    last_climate_parent = device.parentId
                    if "endPointId" in device.properties:
                        last_endpoint = device.properties.endPointId
                    else:
                        last_endpoint = 0
                else:
                    _LOGGER.debug("not handling separately")
            except (KeyError, ValueError):
                pass


def setup(hass, base_config):
    """Set up the Fibaro Component."""
    if DOMAIN not in base_config:
        # AIS new config_flow way
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][CONF_GATEWAYS] = {}
        hass.data[FIBARO_CONTROLLERS] = {}
        return True

    # old configuration.yaml way
    gateways = base_config[DOMAIN][CONF_GATEWAYS]
    hass.data[FIBARO_CONTROLLERS] = {}

    def stop_fibaro(event):
        """Stop Fibaro Thread."""
        _LOGGER.info("Shutting down Fibaro connection")
        for controller in hass.data[FIBARO_CONTROLLERS].values():
            controller.disable_state_handler()

    hass.data[FIBARO_DEVICES] = {}
    for component in FIBARO_COMPONENTS:
        hass.data[FIBARO_DEVICES][component] = []

    for gateway in gateways:
        controller = FibaroController(gateway)
        if controller.connect():
            hass.data[FIBARO_CONTROLLERS][controller.hub_serial] = controller
            for component in FIBARO_COMPONENTS:
                hass.data[FIBARO_DEVICES][component].extend(
                    controller.fibaro_devices[component]
                )

    if hass.data[FIBARO_CONTROLLERS]:
        for component in FIBARO_COMPONENTS:
            discovery.load_platform(hass, component, DOMAIN, {}, base_config)
        for controller in hass.data[FIBARO_CONTROLLERS].values():
            controller.enable_state_handler()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_fibaro)
        return True

    return False


class FibaroDevice(Entity):
    """Representation of a Fibaro device entity."""

    def __init__(self, fibaro_device):
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = fibaro_device.fibaro_controller
        self._name = fibaro_device.friendly_name
        self.ha_id = fibaro_device.ha_id

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.controller.register(self.fibaro_device.id, self._update_callback)

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def device_info(self):
        sw_version = 1
        manufacturer = "Fibaro"
        if "properties" in self.fibaro_device:
            if "zwaveVersion" in self.fibaro_device.properties:
                sw_version = self.fibaro_device.properties.zwaveVersion
            if "zwaveCompany" in self.fibaro_device.properties:
                manufacturer = self.fibaro_device.properties.zwaveCompany

        return {
            "identifiers": {(DOMAIN, self.ha_id)},
            "name": self._name,
            "manufacturer": manufacturer,
            "model": self.fibaro_device.type,
            "sw_version": sw_version,
            "via_device": None,
        }

    @property
    def level(self):
        """Get the level of Fibaro device."""
        if "value" in self.fibaro_device.properties:
            return self.fibaro_device.properties.value
        return None

    @property
    def level2(self):
        """Get the tilt level of Fibaro device."""
        if "value2" in self.fibaro_device.properties:
            return self.fibaro_device.properties.value2
        return None

    def dont_know_message(self, action):
        """Make a warning in case we don't know how to perform an action."""
        _LOGGER.warning(
            "Not sure how to setValue: %s (available actions: %s)",
            str(self.ha_id),
            str(self.fibaro_device.actions),
        )

    def set_level(self, level):
        """Set the level of Fibaro device."""
        self.action("setValue", level)
        if "value" in self.fibaro_device.properties:
            self.fibaro_device.properties.value = level
        if "brightness" in self.fibaro_device.properties:
            self.fibaro_device.properties.brightness = level

    def set_level2(self, level):
        """Set the level2 of Fibaro device."""
        self.action("setValue2", level)
        if "value2" in self.fibaro_device.properties:
            self.fibaro_device.properties.value2 = level

    def call_turn_on(self):
        """Turn on the Fibaro device."""
        self.action("turnOn")

    def call_turn_off(self):
        """Turn off the Fibaro device."""
        self.action("turnOff")

    def call_set_color(self, red, green, blue, white):
        """Set the color of Fibaro device."""
        red = int(max(0, min(255, red)))
        green = int(max(0, min(255, green)))
        blue = int(max(0, min(255, blue)))
        white = int(max(0, min(255, white)))
        color_str = f"{red},{green},{blue},{white}"
        self.fibaro_device.properties.color = color_str
        self.action("setColor", str(red), str(green), str(blue), str(white))

    def action(self, cmd, *args):
        """Perform an action on the Fibaro HC."""
        if cmd in self.fibaro_device.actions:
            getattr(self.fibaro_device, cmd)(*args)
            _LOGGER.debug("-> %s.%s%s called", str(self.ha_id), str(cmd), str(args))
        else:
            self.dont_know_message(cmd)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if "power" in self.fibaro_device.properties:
            power = self.fibaro_device.properties.power
            if power:
                return convert(power, float, 0.0)
        else:
            return None

    @property
    def current_binary_state(self):
        """Return the current binary state."""
        if self.fibaro_device.properties.value == "false":
            return False
        if (
            self.fibaro_device.properties.value == "true"
            or int(self.fibaro_device.properties.value) > 0
        ):
            return True
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.fibaro_device.unique_id_str

    @property
    def name(self) -> Optional[str]:
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from fibaro device."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {"fibaro_id": self.fibaro_device.id}

        try:
            if "battery" in self.fibaro_device.interfaces:
                attr[ATTR_BATTERY_LEVEL] = int(
                    self.fibaro_device.properties.batteryLevel
                )
            if "fibaroAlarmArm" in self.fibaro_device.interfaces:
                attr[ATTR_ARMED] = bool(self.fibaro_device.properties.armed)
            if "power" in self.fibaro_device.interfaces:
                attr[ATTR_CURRENT_POWER_W] = convert(
                    self.fibaro_device.properties.power, float, 0.0
                )
            if "energy" in self.fibaro_device.interfaces:
                attr[ATTR_CURRENT_ENERGY_KWH] = convert(
                    self.fibaro_device.properties.energy, float, 0.0
                )
        except (ValueError, KeyError):
            pass

        return attr


# AIS
async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    import threading

    # discover_devices is a sync function.
    t = threading.Thread(target=discover_devices, args=(hass, config_entry))
    t.start()

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # TODO await hass.config_entries.async_forward_entry_unload(config_entry, "xxx")
    return True


def discover_devices(hass, config_entry):
    """
    Run periodically to discover new devices.

    Currently it's only run at startup.
    """
    # ------------
    gateway = {
        CONF_URL: config_entry.data[CONF_URL],
        CONF_USERNAME: config_entry.data[CONF_USERNAME],
        CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
        CONF_PLUGINS: False,
        CONF_DEVICE_CONFIG: {},
        CONF_EXCLUDE: [],
    }

    def stop_fibaro(event):
        """Stop Fibaro Thread."""
        _LOGGER.info("Shutting down Fibaro connection")
        for controller in hass.data[FIBARO_CONTROLLERS].values():
            controller.disable_state_handler()

    hass.data[FIBARO_DEVICES] = {}
    for component in FIBARO_COMPONENTS:
        hass.data[FIBARO_DEVICES][component] = []

    controller = FibaroController(gateway)
    if controller.connect():
        hass.data[FIBARO_CONTROLLERS][controller.hub_serial] = controller
        for component in FIBARO_COMPONENTS:
            hass.data[FIBARO_DEVICES][component].extend(
                controller.fibaro_devices[component]
            )

    if hass.data[FIBARO_CONTROLLERS]:
        for component in FIBARO_COMPONENTS:
            # discovery.load_platform(hass, component, DOMAIN, {}, config_entry)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )
        for controller in hass.data[FIBARO_CONTROLLERS].values():
            controller.enable_state_handler()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_fibaro)
        return True

    return False
