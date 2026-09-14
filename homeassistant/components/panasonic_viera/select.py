"""Picture mode selection support for Panasonic Viera TVs."""

from typing import Any, override

from homeassistant.components.select import SelectEntity
from homeassistant.const import ATTR_MANUFACTURER, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PanasonicVieraConfigEntry, Remote
from .const import (
    ATTR_DEVICE_INFO,
    ATTR_MODEL_NUMBER,
    ATTR_UDN,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NUMBER,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PanasonicVieraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PAC picture mode selector when supported by the TV."""
    remote = config_entry.runtime_data
    if remote.picture_modes is None:
        return
    config = config_entry.data
    async_add_entities(
        [
            PanasonicVieraPictureModeEntity(
                remote, config[CONF_NAME], config[ATTR_DEVICE_INFO]
            )
        ]
    )


class PanasonicVieraPictureModeEntity(SelectEntity):
    """Representation of a Panasonic PAC picture mode selector."""

    _attr_has_entity_name = True
    _attr_name = "Picture mode"

    def __init__(
        self, remote: Remote, name: str, device_info: dict[str, Any] | None
    ) -> None:
        """Initialize the picture mode selector."""
        self._remote = remote
        if device_info is not None:
            self._attr_unique_id = f"{device_info[ATTR_UDN]}_picture_mode"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_info[ATTR_UDN])},
                manufacturer=device_info.get(ATTR_MANUFACTURER, DEFAULT_MANUFACTURER),
                model=device_info.get(ATTR_MODEL_NUMBER, DEFAULT_MODEL_NUMBER),
                name=name,
            )
        else:
            self._attr_name = f"{name} Picture mode"

    @property
    @override
    def available(self) -> bool:
        """Return whether PAC picture modes remain available."""
        return self._remote.available and self._remote.picture_modes is not None

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current PAC picture mode."""
        return self._remote.picture_mode

    @property
    @override
    def options(self) -> list[str]:
        """Return the picture modes exposed by PAC."""
        return self._remote.picture_modes or []

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a PAC picture mode."""
        await self._remote.async_set_picture_mode(option)
        self.async_write_ha_state()
