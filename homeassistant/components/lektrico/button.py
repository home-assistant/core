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
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool | None:
        """Return None."""
        return None


@dataclass
class ChargeStartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Start button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to start charging."""
        return bool(await device.send_command("charge.start"))


@dataclass
class ChargeStopButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Stop button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to stop charging."""
        return bool(await device.send_command("charge.stop"))


@dataclass
class ChargerRestartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Restart button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to restart the charger."""
        return bool(await device.send_command("device.reset"))


@dataclass
class ChargerPauseButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Pause button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to pause the charger."""
        return bool(await device.send_command("charge.pause"))


@dataclass
class ChargerResumeButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Resume button entity."""

    @classmethod
    async def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to resume the charger."""
        return bool(await device.send_command("charge.resume"))


SENSORS: tuple[LektricoButtonEntityDescription, ...] = (
    ChargeStartButtonEntityDescription(
        key="charge_start",
        name="Charger Start",
    ),
    ChargeStopButtonEntityDescription(
        key="charge_stop",
        name="Charge Stop",
    ),
    ChargerRestartButtonEntityDescription(
        key="charger_restart",
        name="Charger Restart",
    ),
    ChargerPauseButtonEntityDescription(
        key="charge_pause",
        name="Charge Pause",
    ),
    ChargerResumeButtonEntityDescription(
        key="charge_resume",
        name="Charge Resume",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        LektricoButton(
            sensor_desc,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, False)


class LektricoButton(CoordinatorEntity, ButtonEntity):
    """The entity class for Lektrico charging stations binary sensors."""

    entity_description: LektricoButtonEntityDescription

    def __init__(
        self,
        description: LektricoButtonEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.friendly_name = friendly_name
        self.serial_number = coordinator.serial_number
        self.board_revision = coordinator.board_revision
        self.entity_description = description

        self._attr_name = f"{self.friendly_name} {description.name}"
        self._attr_unique_id = f"{self.serial_number}_{description.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            model=f"1P7K {self.serial_number} rev.{self.board_revision}",
            name=self.friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

    async def async_press(self) -> None:
        """Send the command corresponding to the pressed button."""
        await self.entity_description.get_async_press(self.coordinator.device)
