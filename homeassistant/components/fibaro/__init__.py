"""Support for the Fibaro devices."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import logging
from typing import Any

from fiblary3.client.v4.client import (
    Client as FibaroClientV4,
    StateHandler as StateHandlerV4,
)
from fiblary3.client.v5.client import StateHandler as StateHandlerV5
from fiblary3.common.exceptions import HTTPException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_ICON,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import CONF_IMPORT_PLUGINS, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_COLOR = "color"
CONF_DEVICE_CONFIG = "device_config"
CONF_DIMMING = "dimming"
CONF_GATEWAYS = "gateways"
CONF_PLUGINS = "plugins"
CONF_RESET_COLOR = "reset_color"
CONF_WHITE_VALUE = "white_value"
FIBARO_CONTROLLER = "fibaro_controller"
FIBARO_DEVICES = "fibaro_devices"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.LOCK,
    Platform.SWITCH,
]

FIBARO_TYPEMAP = {
    "com.fibaro.multilevelSensor": Platform.SENSOR,
    "com.fibaro.binarySwitch": Platform.SWITCH,
    "com.fibaro.multilevelSwitch": Platform.SWITCH,
    "com.fibaro.FGD212": Platform.LIGHT,
    "com.fibaro.FGR": Platform.COVER,
    "com.fibaro.doorSensor": Platform.BINARY_SENSOR,
    "com.fibaro.doorWindowSensor": Platform.BINARY_SENSOR,
    "com.fibaro.FGMS001": Platform.BINARY_SENSOR,
    "com.fibaro.heatDetector": Platform.BINARY_SENSOR,
    "com.fibaro.lifeDangerSensor": Platform.BINARY_SENSOR,
    "com.fibaro.smokeSensor": Platform.BINARY_SENSOR,
    "com.fibaro.remoteSwitch": Platform.SWITCH,
    "com.fibaro.sensor": Platform.SENSOR,
    "com.fibaro.colorController": Platform.LIGHT,
    "com.fibaro.securitySensor": Platform.BINARY_SENSOR,
    "com.fibaro.hvac": Platform.CLIMATE,
    "com.fibaro.hvacSystem": Platform.CLIMATE,
    "com.fibaro.setpoint": Platform.CLIMATE,
    "com.fibaro.FGT001": Platform.CLIMATE,
    "com.fibaro.thermostatDanfoss": Platform.CLIMATE,
    "com.fibaro.doorLock": Platform.LOCK,
    "com.fibaro.binarySensor": Platform.BINARY_SENSOR,
    "com.fibaro.accelerometer": Platform.BINARY_SENSOR,
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
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {vol.Required(CONF_GATEWAYS): vol.All(cv.ensure_list, [GATEWAY_CONFIG])}
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


class FibaroController:
    """Initiate Fibaro Controller Class."""

    def __init__(
        self, config: Mapping[str, Any], serial_number: str | None = None
    ) -> None:
        """Initialize the Fibaro controller.

        Version 4 is used for home center 2 (SN starts with HC2) and
        home center lite (SN starts with HCL).

        Version 5 is used for home center 3 (SN starts with HC3),
        home center 3 lite (SN starts with HC3L) and yubii home (SN starts with YH).

        Here the serial number is optional and we choose then the V4 client. You
        should do that only when you use the FibaroController for login test as only
        the login and info API's are equal throughout the different versions.
        """

        # Only use V4 API as it works better even for HC3, after the library is fixed, we should
        # add here support for the newer library version V5 again.
        self._client = FibaroClientV4(
            config[CONF_URL], config[CONF_USERNAME], config[CONF_PASSWORD]
        )

        self._scene_map = None
        # Whether to import devices from plugins
        self._import_plugins = config[CONF_IMPORT_PLUGINS]
        self._room_map = None  # Mapping roomId to room object
        self._device_map = None  # Mapping deviceId to device object
        self.fibaro_devices: dict[Platform, list] = defaultdict(
            list
        )  # List of devices by entity platform
        self._callbacks: dict[Any, Any] = {}  # Update value callbacks by deviceId
        self._state_handler = None  # Fiblary's StateHandler object
        self.hub_serial: str  # Unique serial number of the hub
        self.hub_name: str  # The friendly name of the hub
        self.hub_software_version: str
        self.hub_api_url: str = config[CONF_URL]
        # Device infos by fibaro device id
        self._device_infos: dict[int, DeviceInfo] = {}

    def connect(self):
        """Start the communication with the Fibaro controller."""
        try:
            login = self._client.login.get()
            info = self._client.info.get()
            self.hub_serial = info.serialNumber
            self.hub_name = info.hcName
            self.hub_software_version = info.softVersion
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

    def connect_with_error_handling(self) -> None:
        """Translate connect errors to easily differentiate auth and connect failures.

        When there is a better error handling in the used library this can be improved.
        """
        try:
            connected = self.connect()
            if not connected:
                raise FibaroConnectFailed("Connect status is false")
        except HTTPException as http_ex:
            if http_ex.details == "Forbidden":
                raise FibaroAuthFailed from http_ex

            raise FibaroConnectFailed from http_ex
        except Exception as ex:
            raise FibaroConnectFailed from ex

    def enable_state_handler(self):
        """Start StateHandler thread for monitoring updates."""
        if isinstance(self._client, FibaroClientV4):
            self._state_handler = StateHandlerV4(self._client, self._on_state_change)
        else:
            self._state_handler = StateHandlerV5(self._client, self._on_state_change)

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
            for callback in self._callbacks[item]:
                callback()

    def register(self, device_id, callback):
        """Register device with a callback for updates."""
        self._callbacks.setdefault(device_id, [])
        self._callbacks[device_id].append(callback)

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
    def _map_device_to_platform(device: Any) -> Platform | None:
        """Map device to HA device type."""
        # Use our lookup table to identify device type
        platform: Platform | None = None
        if "type" in device:
            platform = FIBARO_TYPEMAP.get(device.type)
        if platform is None and "baseType" in device:
            platform = FIBARO_TYPEMAP.get(device.baseType)

        # We can also identify device type by its capabilities
        if platform is None:
            if "setBrightness" in device.actions:
                platform = Platform.LIGHT
            elif "turnOn" in device.actions:
                platform = Platform.SWITCH
            elif "open" in device.actions:
                platform = Platform.COVER
            elif "secure" in device.actions:
                platform = Platform.LOCK
            elif "value" in device.properties:
                if device.properties.value in ("true", "false"):
                    platform = Platform.BINARY_SENSOR
                else:
                    platform = Platform.SENSOR

        # Switches that control lights should show up as lights
        if platform == Platform.SWITCH and device.properties.get("isLight", False):
            platform = Platform.LIGHT
        return platform

    def _create_device_info(self, device: Any, devices: list) -> None:
        """Create the device info. Unrooted entities are directly shown below the home center."""

        # The home center is always id 1 (z-wave primary controller)
        if "parentId" not in device or device.parentId <= 1:
            return

        master_entity: Any | None = None
        if device.parentId == 1:
            master_entity = device
        else:
            for parent in devices:
                if "id" in parent and parent.id == device.parentId:
                    master_entity = parent
        if master_entity is None:
            _LOGGER.error("Parent with id %s not found", device.parentId)
            return

        if "zwaveCompany" in master_entity.properties:
            manufacturer = master_entity.properties.zwaveCompany
        else:
            manufacturer = "Unknown"

        self._device_infos[master_entity.id] = DeviceInfo(
            identifiers={(DOMAIN, master_entity.id)},
            manufacturer=manufacturer,
            name=master_entity.name,
            via_device=(DOMAIN, self.hub_serial),
        )

    def get_device_info(self, device: Any) -> DeviceInfo:
        """Get the device info by fibaro device id."""
        if device.id in self._device_infos:
            return self._device_infos[device.id]
        if "parentId" in device and device.parentId in self._device_infos:
            return self._device_infos[device.parentId]
        return DeviceInfo(identifiers={(DOMAIN, self.hub_serial)})

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
            device.unique_id_str = f"{slugify(self.hub_serial)}.scene.{device.id}"
            self._scene_map[device.id] = device
            self.fibaro_devices[Platform.SCENE].append(device)
            _LOGGER.debug("%s scene -> %s", device.ha_id, device)

    def _read_devices(self):
        """Read and process the device list."""
        devices = list(self._client.devices.list())
        self._device_map = {}
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
                if device.enabled and (
                    "isPlugin" not in device
                    or (not device.isPlugin or self._import_plugins)
                ):
                    device.mapped_platform = self._map_device_to_platform(device)
                else:
                    device.mapped_platform = None
                if (platform := device.mapped_platform) is None:
                    continue
                device.unique_id_str = f"{slugify(self.hub_serial)}.{device.id}"
                self._create_device_info(device, devices)
                self._device_map[device.id] = device
                _LOGGER.debug(
                    "%s (%s, %s) -> %s %s",
                    device.ha_id,
                    device.type,
                    device.baseType,
                    platform,
                    str(device),
                )
                if platform != Platform.CLIMATE:
                    self.fibaro_devices[platform].append(device)
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
                    self.fibaro_devices[platform].append(device)
                    last_climate_parent = device.parentId
                    if "endPointId" in device.properties:
                        last_endpoint = device.properties.endPointId
                    else:
                        last_endpoint = 0
                else:
                    _LOGGER.debug("not handling separately")
            except (KeyError, ValueError):
                pass


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Migrate configuration from configuration.yaml."""
    if DOMAIN not in base_config:
        return True
    gateways = base_config[DOMAIN][CONF_GATEWAYS]
    if gateways is None:
        return True

    # check if already configured
    if hass.config_entries.async_entries(DOMAIN):
        return True

    for gateway in gateways:
        # prepare new config based on configuration.yaml
        conf = {
            CONF_URL: gateway[CONF_URL],
            CONF_USERNAME: gateway[CONF_USERNAME],
            CONF_PASSWORD: gateway[CONF_PASSWORD],
            CONF_IMPORT_PLUGINS: gateway[CONF_PLUGINS],
        }

        # import into config flow based configuration
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


def _init_controller(
    data: Mapping[str, Any], serial_number: str | None
) -> FibaroController:
    """Validate the user input allows us to connect to fibaro."""
    controller = FibaroController(data, serial_number)
    controller.connect_with_error_handling()
    return controller


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Fibaro Component.

    The unique id of the config entry is the serial number of the home center.
    """
    try:
        controller = await hass.async_add_executor_job(
            _init_controller, entry.data, entry.unique_id
        )
    except FibaroConnectFailed as connect_ex:
        raise ConfigEntryNotReady(
            f"Could not connect to controller at {entry.data[CONF_URL]}"
        ) from connect_ex
    except FibaroAuthFailed as auth_ex:
        raise ConfigEntryAuthFailed from auth_ex

    data: dict[str, Any] = {}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    data[FIBARO_CONTROLLER] = controller
    devices = data[FIBARO_DEVICES] = {}
    for platform in PLATFORMS:
        devices[platform] = [*controller.fibaro_devices[platform]]

    # register the hub device info separately as the hub has sometimes no entities
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.hub_serial)},
        manufacturer="Fibaro",
        name=controller.hub_name,
        model=controller.hub_serial,
        sw_version=controller.hub_software_version,
        configuration_url=controller.hub_api_url.removesuffix("/api/"),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    controller.enable_state_handler()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Shutting down Fibaro connection")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][FIBARO_CONTROLLER].disable_state_handler()
    hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FibaroDevice(Entity):
    """Representation of a Fibaro device entity."""

    _attr_should_poll = False

    def __init__(self, fibaro_device):
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = fibaro_device.fibaro_controller
        self.ha_id = fibaro_device.ha_id
        self._attr_name = fibaro_device.friendly_name
        self._attr_unique_id = fibaro_device.unique_id_str
        self._attr_device_info = self.controller.get_device_info(fibaro_device)
        # propagate hidden attribute set in fibaro home center to HA
        if "visible" in fibaro_device and fibaro_device.visible is False:
            self._attr_entity_registry_visible_default = False

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.controller.register(self.fibaro_device.id, self._update_callback)

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)

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
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {"fibaro_id": self.fibaro_device.id}

        try:
            if "battery" in self.fibaro_device.interfaces:
                attr[ATTR_BATTERY_LEVEL] = int(
                    self.fibaro_device.properties.batteryLevel
                )
            if "armed" in self.fibaro_device.properties:
                armed = self.fibaro_device.properties.armed
                if isinstance(armed, bool):
                    attr[ATTR_ARMED] = armed
                elif isinstance(armed, str) and armed.lower() in ("true", "false"):
                    attr[ATTR_ARMED] = armed.lower() == "true"
                else:
                    attr[ATTR_ARMED] = None
        except (ValueError, KeyError):
            pass

        return attr


class FibaroConnectFailed(HomeAssistantError):
    """Error to indicate we cannot connect to fibaro home center."""


class FibaroAuthFailed(HomeAssistantError):
    """Error to indicate that authentication failed on fibaro home center."""
