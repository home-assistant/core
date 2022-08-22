"""Support for Lektrico charging station button."""

from __future__ import annotations

from dataclasses import dataclass

import lektricowifi

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_FRIENDLY_NAME,
)
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
    def get_async_press(cls, device: lektricowifi.Charger) -> bool | None:
        """Return None."""
        return None


@dataclass
class ChargeStartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Start button entity."""

    @classmethod
    def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to start charging."""
        return bool(device.send_command("charge.start"))


@dataclass
class ChargeStopButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charge Stop button entity."""

    @classmethod
    def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to stop charging."""
        return bool(device.send_command("charge.stop"))


@dataclass
class ChargerRestartButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Restart button entity."""

    @classmethod
    def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to restart the charger."""
        return bool(device.send_command("device.reset"))


@dataclass
class ChargerPauseButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Pause button entity."""

    @classmethod
    def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to pause the charger."""
        return bool(device.send_command("charge.pause"))


@dataclass
class ChargerResumeButtonEntityDescription(LektricoButtonEntityDescription):
    """A class that describes the Lektrico Charger Resume button entity."""

    @classmethod
    def get_async_press(cls, device: lektricowifi.Charger) -> bool:
        """Command to resume the charger."""
        return bool(device.send_command("charge.resume"))


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
    _lektrico_device: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    sensors = [
        LektricoButton(
            sensor_desc,
            _lektrico_device,
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
        _lektrico_device: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(_lektrico_device)
        self.friendly_name = friendly_name
        self.serial_number = _lektrico_device.serial_number
        self.board_revision = _lektrico_device.board_revision
        self.entity_description = description

        self._attr_name = f"{self.friendly_name} {description.name}"
        self._attr_unique_id = f"{self.serial_number}_{description.name}"

        self._lektrico_device = _lektrico_device

    async def async_press(self) -> None:
        """Send the command corresponding to the pressed button."""
        self.entity_description.get_async_press(self._lektrico_device.device)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Lektrico charger."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.serial_number)},
            ATTR_NAME: self.friendly_name,
            ATTR_MANUFACTURER: "Lektrico",
            ATTR_MODEL: f"1P7K {self.serial_number} rev.{self.board_revision}",
            ATTR_SW_VERSION: self._lektrico_device.data.fw_version,
        }
