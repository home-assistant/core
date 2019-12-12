"""Common vera code."""
from collections import defaultdict
import logging
from typing import Callable, DefaultDict, List, NamedTuple, Optional, Union

import pyvera as pv

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, Scene
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    ATTR_LAST_TRIP_TIME,
    ATTR_TRIPPED,
    CONF_EXCLUDE,
    CONF_LIGHTS,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert, slugify
from homeassistant.util.dt import utc_from_timestamp

from .const import (
    ATTR_CURRENT_ENERGY_KWH,
    ATTR_CURRENT_POWER_W,
    CONF_CONTROLLER,
    CONTROLLER_DATAS,
    DOMAIN,
    VERA_ID_FORMAT,
)

_LOGGER = logging.getLogger(__name__)


ControllerData = NamedTuple(
    "ControllerData",
    (
        ("controller", pv.VeraController),
        ("devices", DefaultDict[str, List[pv.VeraDevice]]),
        ("scenes", List[pv.VeraScene]),
    ),
)


class VeraDevice(Entity):
    """Representation of a Vera device entity."""

    def __init__(self, vera_device: pv.VeraDevice, controller: pv.VeraController):
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.device_id
        )

        self.controller.register(vera_device, self._update_callback)

    def _update_callback(self, _device):
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from vera device."""
        return self.vera_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = "True" if armed else "False"

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = "True" if tripped else "False"

        power = self.vera_device.power
        if power:
            attr[ATTR_CURRENT_POWER_W] = convert(power, float, 0.0)

        energy = self.vera_device.energy
        if energy:
            attr[ATTR_CURRENT_ENERGY_KWH] = convert(energy, float, 0.0)

        attr["Vera Device Id"] = self.vera_device.vera_device_id

        return attr

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return str(self.vera_device.vera_device_id)


def initialize_controller(hass: HomeAssistant, config: dict) -> ControllerData:
    """Initialize a controller."""
    # Get Vera specific configuration.
    base_url = config.get(CONF_CONTROLLER)
    light_ids = config.get(CONF_LIGHTS)
    exclude_ids = config.get(CONF_EXCLUDE)

    # Initialize the Vera controller.
    controller = pv.VeraController(base_url)
    controller.start()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, lambda event: controller.stop()
    )

    controller.refresh_data()
    all_devices = controller.get_devices()
    all_scenes = controller.get_scenes()
    # Exclude devices unwanted by user.
    devices = [device for device in all_devices if device.device_id not in exclude_ids]

    vera_devices = defaultdict(list)
    for device in devices:
        device_type = map_vera_device(device, light_ids)
        if device_type is None:
            continue

        vera_devices[device_type].append(device)

    vera_scenes = []
    for scene in all_scenes:
        vera_scenes.append(scene)

    return ControllerData(
        controller=controller, devices=vera_devices, scenes=vera_scenes
    )


EntityDeviceGenerator = Callable[[pv.VeraDevice, pv.VeraController], Entity]
EntitySceneGenerator = Callable[[pv.VeraDevice, pv.VeraController], Scene]
EntityGenerator = Union[EntityDeviceGenerator, EntitySceneGenerator]
ItemCollector = Callable[
    [ControllerData, str], List[Union[pv.VeraDevice, pv.VeraScene]]
]


def setup_device_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
    platform: str,
    generator: EntityDeviceGenerator,
):
    """Create and add vera entities for devices in a platform."""

    _setup_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform=platform,
        generator=generator,
        item_collector=lambda controller_data, platform: controller_data.devices.get(
            platform
        ),
    )


def setup_scene_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
    platform: str,
    generator: EntitySceneGenerator,
):
    """Create and add vera scenes."""
    _setup_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform=platform,
        generator=generator,
        item_collector=lambda controller_data, platform: controller_data.scenes,
    )


def _setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
    platform: str,
    generator: EntityGenerator,
    item_collector: ItemCollector,
) -> None:
    """Create and add vera entities for a given platform."""
    controller_data = get_controller_data_by_config(hass=hass, entry=entry)

    entities = []
    items = item_collector(controller_data, platform)

    for item in items or []:
        entities.append(generator(item, controller_data.controller))

    async_add_entities(entities, True)


def map_vera_device(vera_device, remap):
    """Map vera classes to Home Assistant types."""

    if isinstance(vera_device, pv.VeraDimmer):
        return LIGHT_DOMAIN
    if isinstance(vera_device, pv.VeraBinarySensor):
        return BINARY_SENSOR_DOMAIN
    if isinstance(vera_device, pv.VeraSensor):
        return SENSOR_DOMAIN
    if isinstance(vera_device, pv.VeraArmableDevice):
        return SWITCH_DOMAIN
    if isinstance(vera_device, pv.VeraLock):
        return LOCK_DOMAIN
    if isinstance(vera_device, pv.VeraThermostat):
        return CLIMATE_DOMAIN
    if isinstance(vera_device, pv.VeraCurtain):
        return COVER_DOMAIN
    if isinstance(vera_device, pv.VeraSceneController):
        return SENSOR_DOMAIN
    if isinstance(vera_device, pv.VeraSwitch):
        if vera_device.device_id in remap:
            return LIGHT_DOMAIN
        return SWITCH_DOMAIN
    return None


def get_controller_data_by_config(
    hass: HomeAssistant, entry: ConfigEntry
) -> Optional[ControllerData]:
    """Get controller data from hass data."""
    base_url = entry.data.get(CONF_CONTROLLER)
    for controller_data in hass.data[DOMAIN][CONTROLLER_DATAS].values():
        if controller_data.controller.base_url == base_url:
            return controller_data

    return None


def set_controller_data(hass: HomeAssistant, controller_data: ControllerData) -> None:
    """Set controller data in hass data."""
    serial_number = controller_data.controller.serial_number
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN][CONTROLLER_DATAS] = hass.data[DOMAIN].get(CONTROLLER_DATAS, {})
    hass.data[DOMAIN][CONTROLLER_DATAS][serial_number] = controller_data


def get_configured_platforms(controller_data: ControllerData) -> List[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices.keys():
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)
