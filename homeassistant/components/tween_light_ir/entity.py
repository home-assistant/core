"""Common entity for Tween Light Infrared integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_NAMES, DOMAIN


class TweenLightIrEntity(Entity):
    """Tween Light Infrared base entity providing common device info."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str | None = None) -> None:
        """Initialize entity."""
        self._attr_unique_id = (
            f"{entry.entry_id}_{unique_id_suffix}"
            if unique_id_suffix is not None
            else entry.entry_id
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            model=DEVICE_TYPE_NAMES[entry.data[CONF_DEVICE_TYPE]],
            manufacturer="Tween Light",
        )
