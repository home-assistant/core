"""Select entities for the ONVIF integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnvifDataUpdateCoordinator
from .device import ONVIFDevice
from .entity import ONVIFBaseEntity
from .models import Profile

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ONVIFSelectEntityDescription(SelectEntityDescription):
    """Describes ONVIF select entity."""

    select_fn: Callable[
        [ONVIFDevice], Callable[[Profile, Any], Coroutine[Any, Any, None]]
    ]
    supported_fn: Callable[[ONVIFDevice], bool]
    options_map: dict[str, Any]


SELECT_TYPE = (
    ONVIFSelectEntityDescription(
        key="ir_cutoff_filter",
        translation_key="ir_cutoff_filter",
        name="IR Lamp",
        icon="mdi:spotlight-beam",
        options_map={
            "OFF": {"IrCutFilter": "ON"},
            "ON": {"IrCutFilter": "OFF"},
            "AUTO": {"IrCutFilter": "AUTO"},
        },
        options=["ON", "OFF", "AUTO"],
        select_fn=lambda device: device.async_set_imaging_settings,
        supported_fn=lambda device: device.capabilities.imaging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ONVIF button based on a config entry."""
    device = hass.data[DOMAIN][config_entry.unique_id]
    coordinator = config_entry.runtime_data["coordinator"]
    async_add_entities(
        OnvifSelectEntity(device, coordinator, description)
        for description in SELECT_TYPE
        if description.supported_fn(device)
    )


class OnvifSelectEntity(
    CoordinatorEntity[OnvifDataUpdateCoordinator], ONVIFBaseEntity, SelectEntity
):
    """Defines ONVIF Select entities."""

    def __init__(
        self,
        device: ONVIFDevice,
        coordinator: OnvifDataUpdateCoordinator,
        description: ONVIFSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{self.device.name} {description.name}"
        self._attr_unique_id = f"{self.mac_or_serial}_{description.key}"
        self.entity_description = description
        self._attr_current_option = "AUTO"  # default value
        self.coordinator = coordinator

    @property
    def current_option(self) -> str | None:
        """Return the current IR Cut filter mode."""
        value = self.coordinator.data.get("IrCutFilter", "AUTO")
        for k, v in self.entity_description.options_map.items():
            if v["IrCutFilter"] == value:
                return k
        return "AUTO"

    async def async_select_option(self, option: str) -> None:
        """Send out setting Auto for IR Lamp."""
        profile = self.device.profiles[0]
        payload = self.entity_description.options_map.get(option)

        if payload is None:
            _LOGGER.debug("Option '%s' not supported", option)

        await self.entity_description.select_fn(self.device)(profile, payload)
        await self.coordinator.async_request_refresh()
        # self.async_write_ha_state()
