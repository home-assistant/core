"""Light platform for Deako."""

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DeakoConfigEntry, DeakoRuntimeData
from .const import DOMAIN

# Model names
MODEL_SMART = "smart"
MODEL_DIMMER = "dimmer"


async def async_setup_entry(
    hass: HomeAssistant,
    config: DeakoConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Configure the platform."""
    runtime_data = config.runtime_data
    client = runtime_data.connection

    add_entities([
        DeakoLightEntity(runtime_data, uuid, config.entry_id)
        for uuid in client.get_devices()
    ])


class DeakoLightEntity(LightEntity):
    """Deako LightEntity class."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = False
    _attr_available = True

    runtime_data: DeakoRuntimeData

    def __init__(
        self, runtime_data: DeakoRuntimeData, uuid: str, entry_id: str
    ) -> None:
        """Save connection reference."""
        self.runtime_data = runtime_data
        self._attr_unique_id = uuid

        client = runtime_data.connection
        dimmable = client.is_dimmable(uuid)

        model = MODEL_SMART
        self._attr_color_mode = ColorMode.ONOFF
        if dimmable:
            model = MODEL_DIMMER
            self._attr_color_mode = ColorMode.BRIGHTNESS

        self._attr_supported_color_modes = {self._attr_color_mode}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uuid)},
            name=client.get_name(uuid),
            manufacturer="Deako",
            model=model,
            via_device=(DOMAIN, entry_id),
        )

        client.set_state_callback(uuid, self.on_update)
        self.update()  # set initial state

    def on_update(self) -> None:
        """State update callback."""
        self.update()
        self.schedule_update_ha_state()

    async def control_device(self, power: bool, dim: int | None = None) -> None:
        """Control entity state via throttled client."""
        assert self._attr_unique_id is not None
        await self.runtime_data.throttled_control(self._attr_unique_id, power, dim)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        dim = None
        if ATTR_BRIGHTNESS in kwargs:
            dim = round(kwargs[ATTR_BRIGHTNESS] / 2.55, 0)
        await self.control_device(True, dim)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.control_device(False)

    def update(self) -> None:
        """Call to update state."""
        assert self._attr_unique_id is not None
        state = self.runtime_data.connection.get_state(self._attr_unique_id) or {}
        self._attr_is_on = bool(state.get("power", False))
        if (
            self._attr_supported_color_modes is not None
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            self._attr_brightness = int(round(state.get("dim", 0) * 2.55))
