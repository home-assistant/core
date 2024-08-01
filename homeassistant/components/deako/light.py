"""Binary sensor platform for integration_blueprint."""

import logging
from typing import Any

from pydeako.deako import Deako

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

# Model names
MODEL_SMART = "smart"
MODEL_DIMMER = "dimmer"

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Configure the platform."""
    client: Deako = config.runtime_data

    devices = client.get_devices()
    add_entities([DeakoLightEntity(client, uuid) for uuid in devices])


class DeakoLightEntity(LightEntity):
    """Deako LightEntity class."""

    _attr_supported_color_modes: set[ColorMode]

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = False
    _attr_available = True

    def __init__(self, client: Deako, uuid: str) -> None:
        """Save connection reference."""
        self.client = client
        self._attr_unique_id = uuid

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
        )

        client.set_state_callback(uuid, self.on_update)
        self.update()  # set initial state

    def on_update(self) -> None:
        """State update callback."""
        self.update()
        self.schedule_update_ha_state()

    def get_state(self) -> dict[str, bool | int]:
        """Return state of entity from client."""
        assert self._attr_unique_id is not None
        return self.client.get_state(self._attr_unique_id) or {}

    async def control_device(self, power: bool, dim: int | None = None) -> None:
        """Control entity state via client."""
        assert self._attr_unique_id is not None
        await self.client.control_device(self._attr_unique_id, power, dim)

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
        state = self.get_state()
        self._attr_is_on = bool(state.get("power", False))
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
            self._attr_brightness = int(round(state.get("dim", 0) * 2.55))
