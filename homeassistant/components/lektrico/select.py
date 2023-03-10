"""Support for Lektrico charging station select."""

from __future__ import annotations

from dataclasses import dataclass

import lektricowifi

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoSelectEntityDescription(SelectEntityDescription):
    """A class that describes the Lektrico select entities."""

    @classmethod
    async def async_select_option(
        cls, device: lektricowifi.Device, value: int
    ) -> bool | None:
        """Return None."""
        return None


@dataclass
class DeviceLBModeSelectEntityDescription(LektricoSelectEntityDescription):
    """A class that describes the Lektrico LB_Device LB_MODE select entity."""

    @classmethod
    async def async_select_option(cls, device: lektricowifi.Device, value: int) -> bool:
        """Command the LB_DEVICE to change the LB_MODE."""
        return bool(await device.set_load_balancing_mode(value))


_MODE_TO_OPTION: dict[lektricowifi.LBMode, str] = {
    lektricowifi.LBMode.OFF: "Disabled",
    lektricowifi.LBMode.POWER: "Power",
    lektricowifi.LBMode.HYBRID: "Hybrid",
    lektricowifi.LBMode.GREEN: "Green",
}

_OPTION_TO_MODE: dict[str, lektricowifi.LBMode] = {
    value: key for key, value in _MODE_TO_OPTION.items()
}


SELECTS_FOR_LB_DEVICES: tuple[LektricoSelectEntityDescription, ...] = (
    DeviceLBModeSelectEntityDescription(
        key="lb_mode",
        name="LB Mode",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LektricoSelect(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
            list(_MODE_TO_OPTION.values()),
        )
        for description in SELECTS_FOR_LB_DEVICES
    )


class LektricoSelect(CoordinatorEntity, SelectEntity):
    """The entity class for Lektrico charging stations selects."""

    entity_description: LektricoSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoSelectEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
        supported_options: list[str],
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_options = supported_options

        self._attr_current_option = _MODE_TO_OPTION[coordinator.data.lb_mode]
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.serial_number))},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.async_select_option(
            self.coordinator.device, _OPTION_TO_MODE[option].value
        )
        self._attr_current_option = option
        self.async_write_ha_state()
