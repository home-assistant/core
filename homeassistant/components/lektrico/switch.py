"""Support for Lektrico charging station switches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import lektricowifi

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
class LektricoSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes the Lektrico switch entities."""

    @classmethod
    def get_is_on(cls, data: Any) -> int | None:
        """Return None."""
        return None

    @classmethod
    def turn_on(cls, device: lektricowifi.Charger, data: Any) -> bool | None:
        """Return None."""
        return None

    @classmethod
    def turn_off(cls, device: lektricowifi.Charger, data: Any) -> bool | None:
        """Return None."""
        return None


@dataclass
class RequireAuthSwitchEntityDescription(LektricoSwitchEntityDescription):
    """A class that describes the Lektrico RequireAuth Switch entity."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool:
        """Get the RequireAuth."""
        return bool(data.require_auth)

    @classmethod
    def turn_on(cls, device: lektricowifi.Charger, data: Any) -> bool:
        """Turn on the RequireAuth switch."""
        return bool(
            device.send_command(
                'app_config.set?config_key="headless"&config_value="false"'
            )
        )

    @classmethod
    def turn_off(cls, device: lektricowifi.Charger, data: Any) -> bool:
        """Turn off the RequireAuth switch."""
        return bool(
            device.send_command(
                'app_config.set?config_key="headless"&config_value="true"'
            )
        )


@dataclass
class LockSwitchEntityDescription(LektricoSwitchEntityDescription):
    """A class that describes the Lektrico Lock / Unlock Switch entity."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool:
        """Check if the reported state is LOCKED."""
        return str(data.charger_state) == "LOCKED"

    @classmethod
    def turn_on(cls, device: lektricowifi.Charger, data: Any) -> bool:
        """Lock the charger."""
        return bool(
            device.send_command(
                'app_config.set?config_key="charger_locked"&config_value="true"'
            )
        )

    @classmethod
    def turn_off(cls, device: lektricowifi.Charger, data: Any) -> bool:
        """Unlock the charger."""
        return bool(
            device.send_command(
                'app_config.set?config_key="charger_locked"&config_value="false"'
            )
        )


SENSORS: tuple[LektricoSwitchEntityDescription, ...] = (
    RequireAuthSwitchEntityDescription(
        key="require_auth",
        name="Require Auth",
    ),
    LockSwitchEntityDescription(
        key="locked",
        name="Lock",
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
        LektricoSwitch(
            sensor_desc,
            _lektrico_device,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, False)


class LektricoSwitch(CoordinatorEntity, SwitchEntity):
    """The entity class for Lektrico charging stations switches."""

    entity_description: LektricoSwitchEntityDescription

    def __init__(
        self,
        description: LektricoSwitchEntityDescription,
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
        # ex: 500006_No Authorisation

        self._lektrico_device = _lektrico_device

    @property
    def is_on(self) -> bool:
        """If the switch is currently on or off."""
        return bool(self.entity_description.get_is_on(self._lektrico_device.data))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.entity_description.turn_on(
            self._lektrico_device.device, self._lektrico_device.data
        )
        # Refresh the coordinator because a switch changed a value.
        await self._lektrico_device.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.entity_description.turn_off(
            self._lektrico_device.device, self._lektrico_device.data
        )
        # Refresh the coordinator because a switch changed a value.
        await self._lektrico_device.async_refresh()

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
