"""Light platform for the Tewke integration."""

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DISPATCHER_ADD_SCENES
from .scene import TewkeSceneLight
from .target import TewkeTargetLight

if TYPE_CHECKING:
    from pytewke.data import Scene

    from homeassistant.core import HomeAssistant

    from .data import TewkeConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tewke light entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities = [
        TewkeSceneLight(
            coordinator=coordinator,
            scene=scene,
        )
        for scene_id, scene in coordinator.data["scenes"].items()
    ]
    entities += [
        # We want to expose the scene lights and physical lights
        TewkeTargetLight(coordinator=coordinator, target=target)  # type: ignore[misc]
        for target in coordinator.data["targets"].values()
    ]
    async_add_entities(entities)

    @callback
    def _async_add_new_scenes(scenes: list[Scene]) -> None:
        async_add_entities(
            [
                TewkeSceneLight(
                    coordinator=coordinator,
                    scene=scene,
                )
                for scene in scenes
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DISPATCHER_ADD_SCENES}_{entry.entry_id}",
            _async_add_new_scenes,
        )
    )
