"""Light entity for Mertik Maxitrol fireplace.

Light on/off and brightness are tracked locally (fully optimistic).
The status packet is unreliable for light state.

On HA startup: always initialises to Off and sends light_off() to device.
Brightness level is restored from the previous session via RestoreEntity.

When the fire is extinguished, the device physically turns the light off.
The entity detects this via the coordinator's fire_just_turned_off flag
and resets _is_on accordingly, but retains the brightness level so the
light can be turned back on at the same level.
"""

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import MertikConfigEntry
from .coordinator import MertikDataCoordinator
from .entity import MertikEntity

PARALLEL_UPDATES = 1

DEFAULT_BRIGHTNESS = 128


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MertikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    dataservice = entry.runtime_data
    async_add_entities(
        [
            MertikLightEntity(dataservice, entry.entry_id, entry.data["name"]),
        ]
    )


class MertikLightEntity(MertikEntity, LightEntity, RestoreEntity):
    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_assumed_state = True

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-Light"
        self._is_on = False
        self._brightness = DEFAULT_BRIGHTNESS

    async def async_added_to_hass(self) -> None:
        """Restore brightness only; always start with light off."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if last_state.attributes.get(ATTR_BRIGHTNESS) is not None:
                self._brightness = last_state.attributes[ATTR_BRIGHTNESS]
        self._is_on = False
        await self.hass.async_add_executor_job(self._dataservice.light_off)

    async def _restore_light(self) -> None:
        """Re-send light on after the device auto-killed it when fire turned off."""
        await self.hass.async_add_executor_job(self._dataservice.light_on)
        await self.hass.async_add_executor_job(
            self._dataservice.set_light_brightness, self._brightness
        )
        # _is_on stays True; brightness unchanged
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Called on every coordinator poll.
        If the fire just turned off, the device also turned the light off.
        We immediately re-send the light on command at the saved brightness
        so the light stays on independently of the fire state.
        """
        if self._dataservice.fire_just_turned_off and self._is_on:
            self.hass.async_create_task(self._restore_light())
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            if not self._is_on:
                await self.hass.async_add_executor_job(self._dataservice.light_on)
            await self.hass.async_add_executor_job(
                self._dataservice.set_light_brightness, self._brightness
            )
        else:
            await self.hass.async_add_executor_job(self._dataservice.light_on)
        self._is_on = True
        self.async_write_ha_state()
        self._dataservice.async_set_updated_data(None)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        self.async_write_ha_state()
        await self.hass.async_add_executor_job(self._dataservice.light_off)
        self._dataservice.async_set_updated_data(None)
