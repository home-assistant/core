"""Light platform for the Tewke integration."""

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_DISABLED_SCENES, DISPATCHER_ADD_SCENES
from .scene import TewkeSceneLight
from .target import TewkeTargetLight

if TYPE_CHECKING:
    from pytewke.data import Scene

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TewkeConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tewke light entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    scene_control_types = entry.runtime_data.scene_control_types
    disabled_scenes: list[str] = entry.data.get(CONF_DISABLED_SCENES, [])

    entities = [
        TewkeSceneLight(
            coordinator=coordinator,
            scene=scene,
            enabled_default=scene_id not in disabled_scenes,
        )
        for scene_id, scene in coordinator.data["scenes"].items()
        if scene_control_types.get(scene_id) == "light"
    ]
    entities += [
        TewkeTargetLight(coordinator=coordinator, target=target)
        for target in coordinator.data["targets"].values()
    ]
    async_add_entities(entities)

    @callback
    def _async_add_new_scenes(scenes: list[Scene]) -> None:
        async_add_entities(
            TewkeSceneLight(
                coordinator=coordinator,
                scene=scene,
                enabled_default=scene.id
                not in entry.data.get(CONF_DISABLED_SCENES, []),
            )
            for scene in scenes
            if scene_control_types.get(scene.id) == "light"
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCHER_ADD_SCENES, _async_add_new_scenes)
    )
