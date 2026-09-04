"""Scene-based light entities for the Tewke integration.

Each Tewke scene is exposed as a dimmable light with brightness from 0-255.

Scene brightness is write-only on the Tewke API; the last commanded value is
held locally for optimistic rendering.
"""

# pylint: disable=home-assistant-missing-parallel-updates

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import callback

from .entity import TewkeEntity, tewke_error_handler
from .util import _ha_to_tewke_brightness, _tewke_to_ha_brightness

if TYPE_CHECKING:
    from pytewke.data import Scene

    from .coordinator import TewkeCoordinator


class TewkeSceneEntity(TewkeEntity):
    """A Tewke scene base entity."""

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        scene: Scene,
        *,
        enabled_default: bool = True,
    ) -> None:
        """Initialise the scene light."""
        super().__init__(coordinator)
        self._scene_id = scene.id
        self._attr_name = scene.name
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        self._attr_unique_id = f"{hardware_id}_{scene.id}"
        self._is_on = scene.is_active
        self._brightness: int | None = scene.brightness
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def _scene(self) -> Scene | None:
        return self.coordinator.data["scenes"].get(self._scene_id)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Sync scene name from coordinator data before writing state."""
        scene = self._scene
        if scene is not None:
            self._attr_name = scene.name
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return True if the scene is available, False otherwise."""
        if not super().available:
            return False

        return self._scene_id in self.coordinator.data.get("scenes", {})

    @property
    def is_on(self) -> bool | None:
        """Return True when the scene is active."""
        scene = self._scene
        if scene is not None:
            self._is_on = scene.is_active
            if scene.brightness is not None:
                self._brightness = scene.brightness
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the last commanded brightness (0-255), or None if unknown."""
        return (
            _tewke_to_ha_brightness(self._brightness)
            if self._brightness is not None
            else None
        )

    async def _async_set_scene(
        self, *, state: bool, brightness: int | None = None
    ) -> None:
        """Set the scene state and brightness."""
        action = "activating" if state else "deactivating"
        identifier = f"scene {self._scene_id}"
        with tewke_error_handler(action, identifier):
            await self.coordinator.config_entry.runtime_data.tap.set_scene(
                scene_id=self._scene_id, state=state, brightness=brightness
            )
            self._is_on = state
            if state and brightness is not None:
                self._brightness = brightness
            self.async_write_ha_state()
            if not self.coordinator.config_entry.runtime_data.observe_active:
                await self.coordinator.async_request_refresh()


# pylint: disable-next=home-assistant-enforce-class-module
class TewkeSceneLight(TewkeSceneEntity, LightEntity):
    """A Tewke scene exposed as a dimmable light.

    The Tewke API does not return scene brightness, so the last commanded
    brightness is held in "_brightness" for optimistic rendering.
    """

    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        scene: Scene,
        *,
        enabled_default: bool = True,
    ) -> None:
        """Initialise the scene light."""
        super().__init__(coordinator, scene, enabled_default=enabled_default)
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the scene, optionally at a specific brightness."""
        raw = kwargs.get(ATTR_BRIGHTNESS)
        ha_brightness = int(raw) if raw is not None else (self.brightness or 255)
        tewke_brightness = _ha_to_tewke_brightness(ha_brightness)
        await self._async_set_scene(state=True, brightness=tewke_brightness)

    @override
    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Deactivate the scene."""
        await self._async_set_scene(state=False)
