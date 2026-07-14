"""Scene-based entity classes for the Tewke integration.

Each Tewke scene can be exposed as one of three HA platform types depending on
the control type chosen during config flow:

* "TewkeSceneSwitch" — "SwitchEntity", no brightness
* "TewkeSceneLight" — "LightEntity", brightness 0-255 (optimistic)
* "TewkeSceneFan" — "FanEntity", percentage 0-100 (optimistic)

Scene brightness is write-only on the Tewke API; the last commanded value is
held locally for optimistic rendering.
"""

from typing import TYPE_CHECKING

from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidRequestError,
    PyTewkeInvalidResponseError,
    PyTewkeInvalidWallDockError,
    PyTewkeUnknownError,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from .const import LOGGER
from .entity import TewkeEntity
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
        hardware_id = coordinator.data["config"].hardware_id
        self._attr_unique_id = f"{hardware_id}_{scene.id}"
        self._is_on = scene.is_active
        self._brightness: int | None = scene.brightness
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def _scene(self) -> Scene | None:
        return self.coordinator.data["scenes"].get(self._scene_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync scene name from coordinator data before writing state."""
        scene = self._scene
        if scene is not None:
            self._attr_name = scene.name
        super()._handle_coordinator_update()

    @property
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

    @property
    def percentage(self) -> int | None:
        """Return the last commanded fan speed (0-100), or None if unknown."""
        return self._brightness

    async def _async_set_scene(
        self, *, state: bool, brightness: int | None = None
    ) -> None:
        """Set the scene state and brightness."""
        try:
            await self.coordinator.config_entry.runtime_data.tap.set_scene(
                scene_id=self._scene_id, state=state, brightness=brightness
            )
            self._is_on = state
            if state and brightness is not None:
                self._brightness = brightness
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except PyTewkeInvalidWallDockError:
            LOGGER.error("Attempted to set Scene while not connected to Wall Dock")
        except PyTewkeInvalidRequestError, RuntimeError:
            action = "activating" if state else "deactivating"
            LOGGER.exception("Internal error %s Tewke scene %s", action, self._scene_id)
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ):
            action = "activating" if state else "deactivating"
            LOGGER.exception("Error %s Tewke scene %s", action, self._scene_id)


class TewkeSceneSwitch(TewkeSceneEntity, SwitchEntity):
    """A Tewke scene exposed as a switch."""

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        scene: Scene,
        *,
        enabled_default: bool = True,
    ) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, scene, enabled_default=enabled_default)

    async def async_turn_on(self, **_kwargs: object) -> None:
        """Activate the scene."""
        await self._async_set_scene(state=True)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Deactivate the scene."""
        await self._async_set_scene(state=False)


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

    async def async_turn_on(self, **kwargs: object) -> None:
        """Activate the scene, optionally at a specific brightness."""
        raw = kwargs.get(ATTR_BRIGHTNESS)
        ha_brightness = int(raw) if raw is not None else (self.brightness or 255)
        tewke_brightness = _ha_to_tewke_brightness(ha_brightness)
        await self._async_set_scene(state=True, brightness=tewke_brightness)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Deactivate the scene."""
        await self._async_set_scene(state=False)


class TewkeSceneFan(TewkeSceneEntity, FanEntity):
    """A Tewke scene exposed as a fan.

    Fan speed percentage (0-100) maps directly to Tewke brightness (0-100).
    The last commanded percentage is stored locally because the Tewke API does
    not return scene brightness.
    """

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    _MAX_SPEED = 100

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        scene: Scene,
        *,
        default_dimming: int = 50,
        enabled_default: bool = True,
    ) -> None:
        """Initialise the scene fan."""
        super().__init__(coordinator, scene, enabled_default=enabled_default)
        self._default_dimming = default_dimming

    async def _async_set_percentage(self, percentage: int | None) -> None:
        """Set fan speed. A percentage of 0 turns the fan off."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._async_set_scene(state=True, brightness=percentage)

    @property
    def is_on(self) -> bool | None:
        """Return True when the scene is active.

        If the device reports a brightness of _MAX_SPEED (100), substitute the
        configured default dimming value so the entity never reflects a raw
        reading of _MAX_SPEED.
        """
        scene = self._scene
        if scene is not None:
            self._is_on = scene.is_active
            if scene.brightness is not None:
                self._brightness = (
                    self._default_dimming
                    if scene.brightness == self._MAX_SPEED
                    else scene.brightness
                )
        return self._is_on

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed. A percentage of 0 turns the fan off."""
        return await self._async_set_percentage(percentage)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        _preset_mode: str | None = None,
        **_kwargs: object,
    ) -> None:
        """Turn on the fan at the requested speed.

        When no percentage is given, the current device speed is used unless it
        is at _MAX_SPEED (100), in which case the configured default speed is used.
        """
        if percentage is not None:
            target = percentage
        else:
            current = self.percentage
            target = (
                self._default_dimming
                if current is None or current == self._MAX_SPEED
                else current
            )
        await self._async_set_percentage(target)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Turn off the fan."""
        await self._async_set_scene(state=False)
