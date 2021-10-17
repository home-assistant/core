"""The lookin integration fan platform."""
from __future__ import annotations

from typing import Any, Final

from homeassistant.components.fan import SUPPORT_OSCILLATE, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiolookin import Remote
from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

FAN_SUPPORT_FLAGS: Final = SUPPORT_OSCILLATE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform for lookin from a config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    _type_class_map = {
        "04": LookinHumidifierFan,
        "05": LookinPurifierFan,
        "07": LookinFan,
    }
    for remote in lookin_data.devices:
        if not (cls := _type_class_map.get(remote["Type"])):
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_remote(uuid)
        entities.append(cls(uuid=uuid, device=device, lookin_data=lookin_data))

    async_add_entities(entities)


class LookinFanBase(LookinPowerEntity, FanEntity):
    """A base class for lookin fan entities."""

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        """Init the lookin fan base class."""
        super().__init__(uuid, device, lookin_data)
        self._attr_is_on = False

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self._async_send_command(self._power_on_command)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._async_send_command(self._power_off_command)
        self._attr_is_on = False
        self.async_write_ha_state()


class LookinFan(LookinFanBase):
    """A lookin fan."""

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        """IR controlled fan."""
        super().__init__(uuid, device, lookin_data)
        self._oscillating: bool = False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return FAN_SUPPORT_FLAGS

    @property
    def oscillating(self) -> bool:
        """Return whether or not the fan is currently oscillating."""
        return self._oscillating

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set fan oscillation."""
        await self._async_send_command("swing")
        self._oscillating = oscillating
        self.async_write_ha_state()


class LookinHumidifierFan(LookinFanBase):
    """A lookin humidifer fan."""

    @property
    def icon(self) -> str:
        """Icon for a lookin humidifer fan."""
        return "mdi:water-percent"


class LookinPurifierFan(LookinFanBase):
    """A lookin air purifier fan."""

    @property
    def icon(self) -> str:
        """Icon for a lookin purifier fan."""
        return "mdi:water"
