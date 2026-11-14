"""Support for INSTEON dimmers via PowerLinc Modem."""

from typing import Any, override

from pyinsteon import devices
from pyinsteon.managers.scene_manager import async_load_scene_states
from pyinsteon.managers.scene_state_manager import SCENE_ADDED, InsteonScene

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SIGNAL_ADD_ENTITIES
from .entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Insteon switches from a config entry."""

    @callback
    def async_add_insteon_switch_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.SWITCH,
            InsteonSwitchEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.SWITCH}"
    async_dispatcher_connect(hass, signal, async_add_insteon_switch_entities)
    async_add_insteon_devices(
        hass,
        Platform.SWITCH,
        InsteonSwitchEntity,
        async_add_entities,
    )

    scenes = await async_load_scene_states(hass.config.config_dir)
    async_add_entities(InsteonSceneEntity(scene) for scene in scenes)

    @callback
    def async_scene_list_changed(event: str, scene: InsteonScene) -> None:
        """Add an entity for a new scene, or remove a deleted scene's entity."""
        if event == SCENE_ADDED:
            async_add_entities([InsteonSceneEntity(scene)])
            return
        entity_registry = er.async_get(hass)
        if entity_id := entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, _scene_unique_id(scene)
        ):
            entity_registry.async_remove(entity_id)

    config_entry.async_on_unload(scenes.subscribe(async_scene_list_changed))


class InsteonSwitchEntity(InsteonEntity, SwitchEntity):
    """A Class for an Insteon switch entity."""

    @property
    @override
    def is_on(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self._insteon_device.async_on(group=self._insteon_device_group.group)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self._insteon_device.async_off(group=self._insteon_device_group.group)


def _scene_unique_id(scene: InsteonScene) -> str:
    """Return the unique ID of a scene's entity."""
    return f"{devices.modem.id}_scene_{scene.scene_num}"


class InsteonSceneEntity(RestoreEntity, SwitchEntity):
    """A switch that turns an Insteon scene on and off.

    Scenes are not part of a device, so each scene has only its own area.
    """

    _attr_should_poll = False

    def __init__(self, scene: InsteonScene) -> None:
        """Initialize the scene entity."""
        self._scene = scene
        self._attr_unique_id = _scene_unique_id(scene)

    @property
    @override
    def name(self) -> str:
        """Return the scene name."""
        return self._scene.name

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the scene is on."""
        return self._scene.is_on

    @property
    @override
    def assumed_state(self) -> bool:
        """Return true unless a scene controller reports the scene state."""
        return not self._scene.has_device_state

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last state and follow scene changes."""
        await super().async_added_to_hass()
        if (
            self._scene.is_on is None
            and (last_state := await self.async_get_last_state())
            and last_state.state in (STATE_ON, STATE_OFF)
        ):
            self._scene.restore_state(last_state.state == STATE_ON)
        self.async_on_remove(self._scene.subscribe(self.async_write_ha_state))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the scene on."""
        await self._scene.async_on()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the scene off."""
        await self._scene.async_off()
