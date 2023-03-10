"""Support for Lektrico charging station button."""

from __future__ import annotations

from dataclasses import dataclass

import lektricowifi

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoButtonEntityDescription(ButtonEntityDescription):
    """A class that describes the Lektrico button entities."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Device) -> bool | None:
        """Return None."""
        return None


@dataclass
class ChargeStartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Start button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Device) -> bool:
        """Command to start charging."""
        return bool(await device.send_charge_start())


@dataclass
class ChargeStopButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Stop button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Device) -> bool:
        """Command to stop charging."""
        return bool(await device.send_charge_stop())


@dataclass
class ChargerRestartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Restart button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Device) -> bool:
        """Command to restart the charger."""
        return bool(await device.send_reset())


BUTTONS_FOR_CHARGERS: tuple[LektricoButtonEntityDescription, ...] = (
    ChargeStartButtonEntityDescription(
        key="charge_start",
        name="Charge start",
    ),
    ChargeStopButtonEntityDescription(
        key="charge_stop",
        name="Charge stop",
    ),
    ChargerRestartButtonEntityDescription(
        key="reboot",
        name="Reboot",
    ),
)


BUTTONS_FOR_LB_DEVICES: tuple[LektricoButtonEntityDescription, ...] = (
    ChargerRestartButtonEntityDescription(
        key="reboot",
        name="Reboot",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    _sensors_to_be_used: tuple[LektricoButtonEntityDescription, ...]
    if coordinator.device_type in (
        lektricowifi.Device.TYPE_1P7K,
        lektricowifi.Device.TYPE_3P22K,
    ):
        _sensors_to_be_used = BUTTONS_FOR_CHARGERS
    elif coordinator.device_type in (
        lektricowifi.Device.TYPE_EM,
        lektricowifi.Device.TYPE_3EM,
    ):
        _sensors_to_be_used = BUTTONS_FOR_LB_DEVICES
    else:
        return

    async_add_entities(
        LektricoButton(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for description in _sensors_to_be_used
    )


class LektricoButton(CoordinatorEntity, ButtonEntity):
    """The entity class for Lektrico charging stations binary sensors."""

    entity_description: LektricoButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoButtonEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.serial_number))},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

    async def async_press(self) -> None:
        """Send the command corresponding to the pressed button."""
        await self.entity_description.get_async_press(self.coordinator.device)
