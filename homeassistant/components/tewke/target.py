"""Target-based entity classes for the Tewke integration.

Each Tewke physical output (target) is exposed as a "LightEntity". Targets
are disabled by default because most users will prefer to control their device
via scenes; targets are an advanced option for direct output control.

Dimmable targets expose "ColorMode.BRIGHTNESS"; non-dimmable ones expose
"ColorMode.ONOFF". Brightness values are converted between the Tewke scale
(0-100) and the HA scale (0-255).
"""

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import callback

from .entity import TewkeEntity, tewke_error_handler
from .util import _ha_to_tewke_brightness, _tewke_to_ha_brightness

if TYPE_CHECKING:
    from pytewke.data import Target

    from .coordinator import TewkeCoordinator


# pylint: disable-next=home-assistant-enforce-class-module
class TewkeTargetLight(TewkeEntity, LightEntity):
    """A Tewke physical output (target) exposed as a light.

    Disabled by default — targets are an advanced interface for direct output
    control. Most users should use scenes instead.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TewkeCoordinator, target: Target) -> None:
        """Initialise the target light."""
        super().__init__(coordinator)
        self._target_index = target.index
        self._attr_name = target.name
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        self._attr_unique_id = f"{hardware_id}_target_{target.index}"
        if target.is_dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._is_on = target.is_on
        self._brightness = target.brightness

    @property
    def _target(self) -> Target | None:
        return self.coordinator.data["targets"].get(self._target_index)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Sync target name from coordinator data before writing state."""
        target = self._target
        if target is not None:
            self._attr_name = target.name
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return True if the target is available, False otherwise."""
        if not super().available:
            return False

        return self._target_index in self.coordinator.data.get("targets", {})

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the output is on."""
        target = self._target
        if target is not None:
            self._is_on = target.is_on
            self._brightness = target.brightness
        return self._is_on

    @property
    @override
    def brightness(self) -> int | None:
        """Return the current brightness (0-255)."""
        target = self._target
        if target is None or not target.is_dimmable:
            return None
        return _tewke_to_ha_brightness(self._brightness)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the output, optionally at a specific brightness."""
        target = self._target
        if target is None:
            return
        if ATTR_BRIGHTNESS in kwargs:
            tewke_brightness = _ha_to_tewke_brightness(int(kwargs[ATTR_BRIGHTNESS]))
        elif target.is_dimmable:
            tewke_brightness = self._brightness if self._brightness > 0 else 100
        else:
            tewke_brightness = 100

        with tewke_error_handler("activating", f"target {self._target_index}"):
            await self.coordinator.config_entry.runtime_data.tap.set_target(
                target=self._target_index, brightness=tewke_brightness
            )
            self._is_on = tewke_brightness != 0
            self._brightness = tewke_brightness
            self.async_write_ha_state()
            if not self.coordinator.config_entry.runtime_data.observe_active:
                await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **_kwargs: object) -> None:
        """Turn off the output."""
        with tewke_error_handler("turning off", f"target {self._target_index}"):
            await self.coordinator.config_entry.runtime_data.tap.set_target(
                target=self._target_index, brightness=0
            )
            self._is_on = False
            self._brightness = 0
            self.async_write_ha_state()
            if not self.coordinator.config_entry.runtime_data.observe_active:
                await self.coordinator.async_request_refresh()
