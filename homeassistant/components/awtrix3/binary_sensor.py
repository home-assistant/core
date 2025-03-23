"""Awtrix platform binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AwtrixCoordinator
from .entity import AwtrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: AwtrixCoordinator = entry.runtime_data.coordinator

    async_add_entities([
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_left",
            name="Button left",
            icon="mdi:chevron-left-box-outline"),
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_select",
            name="Button select",
            icon="mdi:circle-box-outline"),
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_right",
            name="Button right",
            icon="mdi:chevron-right-box-outline")
    ])

class AwtrixBinarySensor(BinarySensorEntity, AwtrixEntity):
    """representation of a Awtrix binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        key: str,
        name: str | None = None,
        icon: str | None = None
    ) -> None:
        """Initialize the binary sensor."""

        self.hass = hass
        self.key = key
        self._attr_name = name or key
        self._state = False
        self._available = True
        self._attr_icon = icon
        self._state = "off"

        super().__init__(coordinator, key)
        self.coordinator.on_press(self.key, self.button_click)

    def button_click(self, state):
        """Set actual state."""
        self._state = 'on' if state == "1" else "off"
        self.async_write_ha_state()

    @property
    def state(self) -> str:
        """Return state."""
        return self._state
