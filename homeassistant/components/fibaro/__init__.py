"""Support for the Fibaro devices."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
import logging
from typing import Any

from pyfibaro.fibaro_client import (
    FibaroAuthenticationFailed,
    FibaroClient,
    FibaroConnectFailed,
)
from pyfibaro.fibaro_device import DeviceModel
from pyfibaro.fibaro_info import InfoModel
from pyfibaro.fibaro_scene import SceneModel
from pyfibaro.fibaro_state_resolver import FibaroEvent, FibaroStateResolver

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.util import slugify

from .const import CONF_IMPORT_PLUGINS, DOMAIN

type FibaroConfigEntry = ConfigEntry[FibaroController]

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
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


class FibaroController:
    """Initiate Fibaro Controller Class."""

    def __init__(
        self, fibaro_client: FibaroClient, info: InfoModel, import_plugins: bool
    ) -> None:
        """Initialize the Fibaro controller."""
        self._client = fibaro_client
        self._fibaro_info = info

        # Whether to import devices from plugins
        self._import_plugins = import_plugins
        # Mapping roomId to room object
        self._room_map = {room.fibaro_id: room for room in self._client.read_rooms()}
        self._device_map: dict[int, DeviceModel]  # Mapping deviceId to device object
        self.fibaro_devices: dict[Platform, list[DeviceModel]] = defaultdict(
            list
        )  # List of devices by entity platform
        # All scenes
        self._scenes = self._client.read_scenes()
        self._callbacks: dict[int, list[Any]] = {}  # Update value callbacks by deviceId
        # Event callbacks by device id
        self._event_callbacks: dict[int, list[Callable[[FibaroEvent], None]]] = {}
        # Unique serial number of the hub
        self.hub_serial = info.serial_number
        # Device infos by fibaro device id
        self._device_infos: dict[int, DeviceInfo] = {}
        self._read_devices()

    def enable_state_handler(self) -> None:
        """Start StateHandler thread for monitoring updates."""
        self._client.register_update_handler(self._on_state_change)

    def disable_state_handler(self) -> None:
        """Stop StateHandler thread used for monitoring updates."""
        self._client.unregister_update_handler()

    def _on_state_change(self, state: Any) -> None:
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

        resolver = FibaroStateResolver(state)
        for event in resolver.get_events():
            # event does not always have a fibaro id, therefore it is
            # essential that we first check for relevant event type
            if (
                event.event_type.lower() == "centralsceneevent"
                and event.fibaro_id in self._event_callbacks
            ):
                for callback in self._event_callbacks[event.fibaro_id]:
                    callback(event)

    def register(self, device_id: int, callback: Any) -> None:
        """Register device with a callback for updates."""
        device_callbacks = self._callbacks.setdefault(device_id, [])
        device_callbacks.append(callback)

    def register_event(
        self, device_id: int, callback: Callable[[FibaroEvent], None]
    ) -> None:
        """Register device with a callback for central scene events.

        The callback receives one parameter with the event.
        """
        device_callbacks = self._event_callbacks.setdefault(device_id, [])
        device_callbacks.append(callback)

    def get_children(self, device_id: int) -> list[DeviceModel]:
        """Get a list of child devices."""
        return [
            device
            for device in self._device_map.values()
            if device.parent_fibaro_id == device_id
        ]

    def get_children2(self, device_id: int, endpoint_id: int) -> list[DeviceModel]:
        """Get a list of child devices for the same endpoint."""
        return [
            device
            for device in self._device_map.values()
            if device.parent_fibaro_id == device_id
            and (not device.has_endpoint_id or device.endpoint_id == endpoint_id)
        ]

    def get_siblings(self, device: DeviceModel) -> list[DeviceModel]:
        """Get the siblings of a device."""
        if device.has_endpoint_id:
            return self.get_children2(device.parent_fibaro_id, device.endpoint_id)
        return self.get_children(device.parent_fibaro_id)

    @staticmethod
    def _map_device_to_platform(device: DeviceModel) -> Platform | None:
        """Map device to HA device type."""
        # Use our lookup table to identify device type
        platform: Platform | None = None
        if device.type:
            platform = FIBARO_TYPEMAP.get(device.type)
        if platform is None and device.base_type:
            platform = FIBARO_TYPEMAP.get(device.base_type)

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
            elif device.has_central_scene_event:
                platform = Platform.EVENT
            elif device.value.has_value and device.value.is_bool_value:
                platform = Platform.BINARY_SENSOR
            elif (
                device.value.has_value
                or "power" in device.properties
                or "energy" in device.properties
            ):
                platform = Platform.SENSOR

        # Switches that control lights should show up as lights
        if platform == Platform.SWITCH and device.properties.get("isLight", False):
            platform = Platform.LIGHT
        return platform

    def _create_device_info(
        self, device: DeviceModel, devices: list[DeviceModel]
    ) -> None:
        """Create the device info. Unrooted entities are directly shown below the home center."""

        # The home center is always id 1 (z-wave primary controller)
        if device.parent_fibaro_id <= 1:
            return

        master_entity: DeviceModel | None = None
        if device.parent_fibaro_id == 1:
            master_entity = device
        else:
            for parent in devices:
                if parent.fibaro_id == device.parent_fibaro_id:
                    master_entity = parent
        if master_entity is None:
            _LOGGER.error("Parent with id %s not found", device.parent_fibaro_id)
            return

        if "zwaveCompany" in master_entity.properties:
            manufacturer = master_entity.properties.get("zwaveCompany")
        else:
            manufacturer = None

        self._device_infos[master_entity.fibaro_id] = DeviceInfo(
            identifiers={(DOMAIN, master_entity.fibaro_id)},
            manufacturer=manufacturer,
            name=master_entity.name,
            via_device=(DOMAIN, self.hub_serial),
        )

    def get_device_info(self, device: DeviceModel) -> DeviceInfo:
        """Get the device info by fibaro device id."""
        if device.fibaro_id in self._device_infos:
            return self._device_infos[device.fibaro_id]
        if device.parent_fibaro_id in self._device_infos:
            return self._device_infos[device.parent_fibaro_id]
        return DeviceInfo(identifiers={(DOMAIN, self.hub_serial)})

    def get_all_device_identifiers(self) -> list[set[tuple[str, str]]]:
        """Get all identifiers of fibaro integration."""
        return [device["identifiers"] for device in self._device_infos.values()]

    def get_room_name(self, room_id: int) -> str | None:
        """Get the room name by room id."""
        assert self._room_map
        room = self._room_map.get(room_id)
        return room.name if room else None

    def read_scenes(self) -> list[SceneModel]:
        """Return list of scenes."""
        return self._scenes

    def read_fibaro_info(self) -> InfoModel:
        """Return the general info about the hub."""
        return self._fibaro_info

    def get_frontend_url(self) -> str:
        """Return the url to the Fibaro hub web UI."""
        return self._client.frontend_url()

    def _read_devices(self) -> None:
        """Read and process the device list."""
        devices = self._client.read_devices()
        self._device_map = {}
        last_climate_parent = None
        last_endpoint = None
        for device in devices:
            try:
                device.fibaro_controller = self
                if device.room_id == 0:
                    room_name = "Unknown"
                else:
                    room_name = self._room_map[device.room_id].name
                device.room_name = room_name
                device.friendly_name = f"{room_name} {device.name}"
                device.ha_id = (
                    f"{slugify(room_name)}_{slugify(device.name)}_{device.fibaro_id}"
                )
                if device.enabled and (not device.is_plugin or self._import_plugins):
                    device.mapped_platform = self._map_device_to_platform(device)
                else:
                    device.mapped_platform = None
                if (platform := device.mapped_platform) is None:
                    continue
                device.unique_id_str = f"{slugify(self.hub_serial)}.{device.fibaro_id}"
                self._create_device_info(device, devices)
                self._device_map[device.fibaro_id] = device
                _LOGGER.debug(
                    "%s (%s, %s) -> %s %s",
                    device.ha_id,
                    device.type,
                    device.base_type,
                    platform,
                    str(device),
                )
                if platform != Platform.CLIMATE:
                    self.fibaro_devices[platform].append(device)
                    continue
                # We group climate devices into groups with the same
                # endPointID belonging to the same parent device.
                if device.has_endpoint_id:
                    _LOGGER.debug(
                        "climate device: %s, endPointId: %s",
                        device.ha_id,
                        device.endpoint_id,
                    )
                else:
                    _LOGGER.debug("climate device: %s, no endPointId", device.ha_id)
                # If a sibling of this device has been added, skip this one
                # otherwise add the first visible device in the group
                # which is a hack, but solves a problem with FGT having
                # hidden compatibility devices before the real device
                if last_climate_parent != device.parent_fibaro_id or (
                    device.has_endpoint_id and last_endpoint != device.endpoint_id
                ):
                    _LOGGER.debug("Handle separately")
                    self.fibaro_devices[platform].append(device)
                    last_climate_parent = device.parent_fibaro_id
                    last_endpoint = device.endpoint_id
                else:
                    _LOGGER.debug("not handling separately")
            except (KeyError, ValueError):
                pass


def connect_fibaro_client(data: Mapping[str, Any]) -> tuple[InfoModel, FibaroClient]:
    """Connect to the fibaro hub and read some basic data."""
    client = FibaroClient(data[CONF_URL])
    info = client.connect_with_credentials(data[CONF_USERNAME], data[CONF_PASSWORD])
    return (info, client)


def init_controller(data: Mapping[str, Any]) -> FibaroController:
    """Connect to the fibaro hub and init the controller."""
    info, client = connect_fibaro_client(data)
    return FibaroController(client, info, data[CONF_IMPORT_PLUGINS])


async def async_setup_entry(hass: HomeAssistant, entry: FibaroConfigEntry) -> bool:
    """Set up the Fibaro Component.

    The unique id of the config entry is the serial number of the home center.
    """
    try:
        controller = await hass.async_add_executor_job(init_controller, entry.data)
    except FibaroConnectFailed as connect_ex:
        raise ConfigEntryNotReady(
            f"Could not connect to controller at {entry.data[CONF_URL]}"
        ) from connect_ex
    except FibaroAuthenticationFailed as auth_ex:
        raise ConfigEntryAuthFailed from auth_ex

    entry.runtime_data = controller

    # register the hub device info separately as the hub has sometimes no entities
    fibaro_info = controller.read_fibaro_info()
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.hub_serial)},
        serial_number=controller.hub_serial,
        manufacturer=fibaro_info.manufacturer_name,
        name=fibaro_info.hc_name,
        model=fibaro_info.model_name,
        sw_version=fibaro_info.current_version,
        configuration_url=controller.get_frontend_url(),
        connections={(dr.CONNECTION_NETWORK_MAC, fibaro_info.mac_address)},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    controller.enable_state_handler()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FibaroConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Shutting down Fibaro connection")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    entry.runtime_data.disable_state_handler()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: FibaroConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a device entry from fibaro integration.

    Only removing devices which are not present anymore are eligible to be removed.
    """
    controller = config_entry.runtime_data
    for identifiers in controller.get_all_device_identifiers():
        if device_entry.identifiers == identifiers:
            # Fibaro device is still served by the controller,
            # do not allow to remove the device entry
            return False

    return True
