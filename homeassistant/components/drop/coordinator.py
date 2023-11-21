"""DROP device data update coordinator object."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .const import (
    CONF_COMMAND_TOPIC,
    CONF_DATA_TOPIC,
    CONF_DEVICE_DESC,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    CONF_UNIQUE_ID,
    DEV_HUB,
    DOMAIN as DROP_DOMAIN,
    KEY_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class DROP_DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """DROP device object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the device."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry
        self._drop_device_id: str = config_entry.data[CONF_UNIQUE_ID]
        self._model: str = f"{config_entry.data[CONF_DEVICE_DESC]} on hub {config_entry.data[CONF_HUB_ID]}"
        if config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
            self._model = f"Hub {config_entry.data[CONF_HUB_ID]}"
        self._manufacturer: str = "Chandler Systems, Inc."
        self._device_name: str = config_entry.data["name"]
        self._device_information: dict[str, Any] = {}
        super().__init__(hass, _LOGGER, name=f"{DROP_DOMAIN}-{self._drop_device_id}")

    async def DROP_MessageReceived(
        self, topic: str, payload: str, qos: int, retain: bool
    ) -> None:
        """Process a received MQTT message."""
        topicRoot = self.config_entry.data[CONF_DATA_TOPIC].removesuffix("/#")
        try:
            jsonData = json_loads(payload)
            if topic.startswith(topicRoot):
                structureKey = topic.removeprefix(topicRoot).removeprefix("/")
                _LOGGER.debug(
                    "New data for %s/%s [%s]: %s",
                    self.config_entry.data[CONF_HUB_ID],
                    self.config_entry.data[CONF_DEVICE_ID],
                    structureKey,
                    payload,
                )

                # Create empty dictionary for this structure key if it does not already exist.
                if structureKey not in self._device_information:
                    self._device_information[structureKey] = {}

                # Merge incoming data into the existing dictionary.
                self._device_information[structureKey].update(jsonData)
                self.async_set_updated_data(None)
        except JSON_DECODE_EXCEPTIONS:
            _LOGGER.error("Invalid JSON (%s): %s", topic, payload)

    # Device properties
    @property
    def id(self) -> str:
        """Return DROP device id."""
        return self._drop_device_id

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_name

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def model(self) -> str:
        """Return model for device."""
        return self._model

    # API endpoints
    @property
    def battery(self) -> int | None:
        """Return battery percentage."""
        return self.getIntVal(KEY_STATUS, "battery")

    @property
    def current_flow_rate(self) -> float | None:
        """Return current flow rate in gpm."""
        return self.getFloatVal(KEY_STATUS, "curFlow")

    @property
    def peak_flow_rate(self) -> float | None:
        """Return peak flow rate in gpm."""
        return self.getFloatVal(KEY_STATUS, "peakFlow")

    @property
    def water_used_today(self) -> float | None:
        """Return water used today in gallons."""
        return self.getFloatVal(KEY_STATUS, "usedToday")

    @property
    def average_water_used(self) -> float | None:
        """Return average water used in gallons."""
        return self.getFloatVal(KEY_STATUS, "avgUsed")

    @property
    def capacity_remaining(self) -> float | None:
        """Return softener capacity remaining in gallons."""
        return self.getFloatVal(KEY_STATUS, "capacity")

    @property
    def current_system_pressure(self) -> float | None:
        """Return current system pressure in PSI."""
        return self.getFloatVal(KEY_STATUS, "psi")

    @property
    def high_system_pressure(self) -> int | None:
        """Return high system pressure today in PSI."""
        return self.getIntVal(KEY_STATUS, "psiHigh")

    @property
    def low_system_pressure(self) -> int | None:
        """Return low system pressure in PSI."""
        return self.getIntVal(KEY_STATUS, "psiLow")

    @property
    def leak(self) -> int | None:
        """Return leak sensor status."""
        return self.getIntVal(KEY_STATUS, "leak")

    @property
    def pending_notification(self) -> int | None:
        """Return pending notification sensor status."""
        return self.getIntVal(KEY_STATUS, "notif")

    @property
    def reserve_in_use(self) -> int | None:
        """Return reserve in use sensor status."""
        return self.getIntVal(KEY_STATUS, "resInUse")

    @property
    def salt(self) -> int | None:
        """Return salt sensor status."""
        return self.getIntVal(KEY_STATUS, "salt")

    @property
    def pump(self) -> int | None:
        """Return pump status."""
        return self.getIntVal(KEY_STATUS, "pump")

    @property
    def protect_mode(self) -> str | None:
        """Return Protect Mode status."""
        return self.getStrVal(KEY_STATUS, "pMode")

    @property
    def temperature_c(self) -> float | None:
        """Return temperature in Celsius."""
        return self.getFloatVal(KEY_STATUS, "temp")

    @property
    def temperature_f(self) -> float | None:
        """Return temperature in Fahrenheit."""
        tempC = self.getFloatVal(KEY_STATUS, "temp")
        if tempC is not None:
            return tempC * (float(9) / 5) + 32
        return None

    @property
    def inlet_tds(self) -> int | None:
        """Return inlet TDS in PPM."""
        return self.getIntVal(KEY_STATUS, "tdsIn")

    @property
    def outlet_tds(self) -> int | None:
        """Return outlet TDS in PPM."""
        return self.getIntVal(KEY_STATUS, "tdsOut")

    @property
    def cart1(self) -> int | None:
        """Return cartridge 1 life remaining."""
        return self.getIntVal(KEY_STATUS, "cart1")

    @property
    def cart2(self) -> int | None:
        """Return cartridge 2 life remaining."""
        return self.getIntVal(KEY_STATUS, "cart2")

    @property
    def cart3(self) -> int | None:
        """Return cartridge 3 life remaining."""
        return self.getIntVal(KEY_STATUS, "cart3")

    @property
    def last_known_water_state(self) -> str | None:
        """Return the last known water state for the system."""
        return self.getStrVal(KEY_STATUS, "water")

    @property
    def last_known_bypass_state(self) -> str | None:
        """Return the last known bypass state for a filter or softener."""
        return self.getStrVal(KEY_STATUS, "bypass")

    # Helper functions for above API endpoints
    def getStrVal(self, structure: str, key: str) -> str | None:
        """Return the specified API value as a string or None if it is unknown."""
        if (
            structure in self._device_information
            and key in self._device_information[structure]
        ):
            return self._device_information[structure][key]
        return None

    def getIntVal(self, structure: str, key: str) -> int | None:
        """Return return the specified API value as an int or None if it is unknown."""
        if (
            structure in self._device_information
            and key in self._device_information[structure]
        ):
            return int(self._device_information[structure][key])
        return None

    def getFloatVal(self, structure: str, key: str) -> float | None:
        """Return the specified API value as a float or None if it is unknown."""
        if (
            structure in self._device_information
            and key in self._device_information[structure]
        ):
            return float(self._device_information[structure][key])
        return None

    # Functions to change Controls
    async def set_water_on(self):
        """Set water supply ON."""
        await mqtt.async_publish(
            self.hass,
            self.config_entry.data[CONF_COMMAND_TOPIC],
            '{"water":1}',
            qos=0,
            retain=False,
        )

    async def set_water_off(self):
        """Set water supply OFF."""
        await mqtt.async_publish(
            self.hass,
            self.config_entry.data[CONF_COMMAND_TOPIC],
            '{"water":0}',
            qos=0,
            retain=False,
        )

    async def set_bypass_on(self):
        """Set bypass ON."""
        await mqtt.async_publish(
            self.hass,
            self.config_entry.data[CONF_COMMAND_TOPIC],
            '{"bypass":1}',
            qos=0,
            retain=False,
        )

    async def set_bypass_off(self):
        """Set bypass OFF."""
        await mqtt.async_publish(
            self.hass,
            self.config_entry.data[CONF_COMMAND_TOPIC],
            '{"bypass":0}',
            qos=0,
            retain=False,
        )

    async def set_protect_mode(self, pMode: str):
        """Set Protect Mode value."""
        await mqtt.async_publish(
            self.hass,
            self.config_entry.data[CONF_COMMAND_TOPIC],
            f'{{"pMode":"{pMode}"}}',
            qos=0,
            retain=False,
        )
