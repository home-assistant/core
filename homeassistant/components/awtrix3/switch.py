"""Platform for switch integration."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AwtrixCoordinator
from .entity import AwtrixEntity

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: AwtrixCoordinator = entry.runtime_data.coordinator
    async_add_entities([
        AwtrixSwitch(
            hass=hass,
            coordinator=coordinator,
            key="atrans",
            name="Transition",
            icon="mdi:swap-horizontal"),
        AwtrixSwitch(
            hass=hass,
            coordinator=coordinator,
            key="abri",
            name="Brightness mode",
            icon="mdi:brightness-auto")
    ])

class AwtrixSwitch(SwitchEntity, AwtrixEntity):
    """Representation of a Awtrix switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        key: str,
        name: str | None = None,
        icon: str | None = None
    ) -> None:
        """Initialize the switch."""

        self.hass = hass
        self.key = key
        self._attr_name = name or key
        self._state = False
        self._available = True
        self._attr_icon = icon

        super().__init__(coordinator, key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self.key == "atrans":
            await self.coordinator.set_value("settings", {"ATRANS": True})
        if self.key == "abri":
            await self.coordinator.set_value("settings", {"ABRI": True})

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.key == "atrans":
            await self.coordinator.set_value("settings", {"ATRANS": False})
        if self.key == "abri":
            await self.coordinator.set_value("settings", {"ABRI": False})

        await self.coordinator.async_refresh()

    @property
    def state(self) -> str:
        """Return state."""
        value = getattr(self.coordinator.data, self.key, None)
        return "on" if value else "off"
