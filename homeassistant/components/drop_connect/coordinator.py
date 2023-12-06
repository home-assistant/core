"""DROP device data update coordinator object."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .const import (
    CONF_DATA_TOPIC,
    CONF_DEVICE_DESC,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OWNER_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DEV_HUB,
    DOMAIN,
    KEY_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class DROPDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """DROP device object."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the device."""
        self._model: str = f"{config_entry.data[CONF_DEVICE_DESC]} on hub {config_entry.data[CONF_HUB_ID]}"
        if config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
            self._model = f"Hub {config_entry.data[CONF_HUB_ID]}"
        self._manufacturer: str = "Chandler Systems, Inc."
        self._device_name: str = config_entry.data[CONF_DEVICE_NAME]
        self._device_information: dict[str, Any] = {}
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}-{config_entry.unique_id}")

    async def drop_message_received(
        self, topic: str, payload: str, qos: int, retain: bool
    ) -> None:
        """Process a received MQTT message."""
        topic_root = self.config_entry.data[CONF_DATA_TOPIC].removesuffix("/#")
        try:
            json_data = json_loads(payload)
            if topic.startswith(topic_root):
                structure_key = topic.removeprefix(topic_root).removeprefix("/")
                _LOGGER.debug(
                    "New data for %s/%s [%s]: %s",
                    self.config_entry.data[CONF_HUB_ID],
                    self.config_entry.data[CONF_DEVICE_ID],
                    structure_key,
                    payload,
                )

                # Create empty dictionary for this structure key if it does not already exist.
                if structure_key not in self._device_information:
                    self._device_information[structure_key] = {}

                # Merge incoming data into the existing dictionary.
                self._device_information[structure_key].update(json_data)
                self.async_set_updated_data(None)
        except JSON_DECODE_EXCEPTIONS:
            _LOGGER.error("Invalid JSON (%s): %s", topic, payload)

    # Device properties

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description."""
        assert self.config_entry.unique_id is not None
        device_info = DeviceInfo(
            manufacturer=self._manufacturer,
            model=self._model,
            name=self._device_name,
            identifiers={(DOMAIN, self.config_entry.unique_id)},
        )
        if self.config_entry.data[CONF_DEVICE_TYPE] != DEV_HUB:
            device_info.update(
                {"via_device": (DOMAIN, self.config_entry.data[CONF_DEVICE_OWNER_ID])}
            )
        return device_info

    # API endpoints
    @property
    def battery(self) -> int | None:
        """Return battery percentage."""
        return self.get_int_val(KEY_STATUS, "battery")

    @property
    def current_flow_rate(self) -> float | None:
        """Return current flow rate in gpm."""
        return self.get_float_val(KEY_STATUS, "curFlow")

    @property
    def peak_flow_rate(self) -> float | None:
        """Return peak flow rate in gpm."""
        return self.get_float_val(KEY_STATUS, "peakFlow")

    @property
    def water_used_today(self) -> float | None:
        """Return water used today in gallons."""
        return self.get_float_val(KEY_STATUS, "usedToday")

    @property
    def average_water_used(self) -> float | None:
        """Return average water used in gallons."""
        return self.get_float_val(KEY_STATUS, "avgUsed")

    @property
    def capacity_remaining(self) -> float | None:
        """Return softener capacity remaining in gallons."""
        return self.get_float_val(KEY_STATUS, "capacity")

    @property
    def current_system_pressure(self) -> float | None:
        """Return current system pressure in PSI."""
        return self.get_float_val(KEY_STATUS, "psi")

    @property
    def high_system_pressure(self) -> int | None:
        """Return high system pressure today in PSI."""
        return self.get_int_val(KEY_STATUS, "psiHigh")

    @property
    def low_system_pressure(self) -> int | None:
        """Return low system pressure in PSI."""
        return self.get_int_val(KEY_STATUS, "psiLow")

    @property
    def temperature(self) -> float | None:
        """Return temperature."""
        return self.get_float_val(KEY_STATUS, "temp")

    @property
    def inlet_tds(self) -> int | None:
        """Return inlet TDS in PPM."""
        return self.get_int_val(KEY_STATUS, "tdsIn")

    @property
    def outlet_tds(self) -> int | None:
        """Return outlet TDS in PPM."""
        return self.get_int_val(KEY_STATUS, "tdsOut")

    @property
    def cart1(self) -> int | None:
        """Return cartridge 1 life remaining."""
        return self.get_int_val(KEY_STATUS, "cart1")

    @property
    def cart2(self) -> int | None:
        """Return cartridge 2 life remaining."""
        return self.get_int_val(KEY_STATUS, "cart2")

    @property
    def cart3(self) -> int | None:
        """Return cartridge 3 life remaining."""
        return self.get_int_val(KEY_STATUS, "cart3")

    # Helper functions for above API endpoints
    def get_int_val(self, structure: str, key: str) -> int | None:
        """Return the specified API value as an int or None if it is unknown."""
        if (
            structure in self._device_information
            and key in self._device_information[structure]
            and self._device_information[structure][key] is not None
        ):
            return int(self._device_information[structure][key])
        return None

    def get_float_val(self, structure: str, key: str) -> float | None:
        """Return the specified API value as a float or None if it is unknown."""
        if (
            structure in self._device_information
            and key in self._device_information[structure]
            and self._device_information[structure][key] is not None
        ):
            return float(self._device_information[structure][key])
        return None
