"""Support for using humidifier with ecobee thermostats."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.humidifier import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    MODE_AUTO,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcobeeConfigEntry
from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

SCAN_INTERVAL = timedelta(minutes=3)

MODE_MANUAL = "manual"
MODE_OFF = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcobeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat humidifier entity."""
    data = config_entry.runtime_data
    entities = []
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["hasHumidifier"]:
            entities.append(EcobeeHumidifier(data, index))

    async_add_entities(entities, True)


ECOBEE_HUMIDIFIER_ACTION_TO_HASS = {
    "humidifier": HumidifierAction.HUMIDIFYING,
    "dehumidifier": HumidifierAction.DRYING,
}


class EcobeeHumidifier(HumidifierEntity):
    """A humidifier class for an ecobee thermostat with humidifier attached."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = [MODE_OFF, MODE_AUTO, MODE_MANUAL]
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_min_humidity = DEFAULT_MIN_HUMIDITY
    _attr_max_humidity = DEFAULT_MAX_HUMIDITY
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, data, thermostat_index) -> None:
        """Initialize ecobee humidifier platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._attr_unique_id = self.thermostat["identifier"]
        self._last_humidifier_on_mode = MODE_MANUAL

        self.update_without_throttle = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the ecobee humidifier."""
        model: str | None
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[self.thermostat['modelNumber']]} Thermostat"
        except KeyError:
            # Ecobee model is not in our list
            model = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.thermostat["name"],
        )

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        if self.mode != MODE_OFF:
            self._last_humidifier_on_mode = self.mode

    @property
    def action(self) -> HumidifierAction:
        """Return the current action."""
        for status in self.thermostat["equipmentStatus"].split(","):
            if status in ECOBEE_HUMIDIFIER_ACTION_TO_HASS:
                return ECOBEE_HUMIDIFIER_ACTION_TO_HASS[status]
        return HumidifierAction.IDLE if self.is_on else HumidifierAction.OFF

    @property
    def is_on(self) -> bool:
        """Return True if the humidifier is on."""
        return self.mode != MODE_OFF

    @property
    def mode(self) -> str:
        """Return the current mode, e.g., off, auto, manual."""
        return self.thermostat["settings"]["humidifierMode"]

    @property
    def target_humidity(self) -> int:
        """Return the desired humidity set point."""
        return int(self.thermostat["runtime"]["desiredHumidity"])

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        try:
            return int(self.thermostat["runtime"]["actualHumidity"])
        except KeyError:
            return None

    def set_mode(self, mode: str) -> None:
        """Set humidifier mode (auto, off, manual)."""
        if self.available_modes is None:
            raise NotImplementedError("Humidifier does not support modes.")
        if mode.lower() not in self.available_modes:
            raise ValueError(
                f"Invalid mode value: {mode}  Valid values are"
                f" {', '.join(self.available_modes)}."
            )

        self.data.ecobee.set_humidifier_mode(self.thermostat_index, mode)
        self.update_without_throttle = True

    def set_humidity(self, humidity: int) -> None:
        """Set the humidity level."""
        self.data.ecobee.set_humidity(self.thermostat_index, humidity)
        self.update_without_throttle = True

    def turn_off(self, **kwargs: Any) -> None:
        """Set humidifier to off mode."""
        self.set_mode(MODE_OFF)

    def turn_on(self, **kwargs: Any) -> None:
        """Set humidifier to on mode."""
        self.set_mode(self._last_humidifier_on_mode)
