"""Common vera code."""
import logging
from typing import Callable, DefaultDict, List, NamedTuple, Optional, Set, Union

import pyvera as pv

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import CONF_CONTROLLER, CONTROLLER_DATAS, DOMAIN

_LOGGER = logging.getLogger(__name__)


ControllerData = NamedTuple(
    "ControllerData",
    (
        ("controller", pv.VeraController),
        ("devices", DefaultDict[str, List[pv.VeraDevice]]),
        ("scenes", List[pv.VeraScene]),
    ),
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


def get_configured_platforms(controller_data: ControllerData) -> Set[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices.keys():
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)
