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

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Configure the platform."""
    client: Deako = hass.data[DOMAIN][config.entry_id]

    devices = client.get_devices()
    if len(devices) == 0:
        # If deako devices are advertising on mdns, we should be able to get at least one device
        _LOGGER.warning("No devices found from local integration")
        await client.disconnect()
        return
    lights = [DeakoLightSwitch(client, uuid) for uuid in devices]
    add_entities(lights)


class DeakoLightSwitch(LightEntity):
    """Deako LightEntity class."""

    client: Deako
    uuid: str

    def __init__(self, client: Deako, uuid: str) -> None:
        """Save connection reference."""
        self.client = client
        self.uuid = uuid
        self.client.set_state_callback(self.uuid, self.on_update)

    def on_update(self) -> None:
        """State update callback."""
        self.schedule_update_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Returns device info in HA digestable format."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.uuid)},
            name=self.name,
            manufacturer="Deako",
            model="dimmer"
            if ColorMode.BRIGHTNESS in self.supported_color_modes
            else "smart",
        )

    @property
    def unique_id(self) -> str:
        """Return the ID of this Deako light."""
        return self.uuid

    @property
    def name(self) -> str:
        """Return the name of the Deako light."""
        name = self.client.get_name(self.uuid)
        return name or f"Unknown device: {self.uuid}"

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        state = self.client.get_state(self.uuid)
        if state is not None:
            power = state.get("power", False)
            if isinstance(power, bool):
                return power
        return False

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        state = self.client.get_state(self.uuid)
        if state is not None:
            return int(round(state.get("dim", 0) * 2.55))
        return 0

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported features."""
        color_modes: set[ColorMode] = set()
        state = self.client.get_state(self.uuid)
        if state is not None and state.get("dim") is None:
            color_modes.add(ColorMode.ONOFF)
        else:
            color_modes.add(ColorMode.BRIGHTNESS)
        return color_modes

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        state = self.client.get_state(self.uuid)
        if state is not None and state.get("dim") is None:
            return ColorMode.ONOFF
        return ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        dim = None
        if ATTR_BRIGHTNESS in kwargs:
            dim = round(kwargs[ATTR_BRIGHTNESS] / 2.55, 0)
        await self.client.control_device(self.uuid, True, dim)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.client.control_device(self.uuid, False)
