"""Coordinator module for the AirTouch 3 integration."""

from dataclasses import dataclass
import logging
from typing import Any

from pyairtouch3 import (
    DEFAULT_PORT,
    Aircon,
    AirTouchClient,
    AirTouchError,
    AirtouchZone,
)

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

VALUE_COMMANDS = {"set_mode", "set_fan_speed", "set_group_temperature"}


@dataclass(slots=True)
class AirTouch3Data:
    """Parsed AirTouch 3 coordinator data."""

    aircon: Aircon
    zones: dict[int, AirtouchZone]

    @classmethod
    def from_aircon(cls, aircon: Aircon) -> AirTouch3Data:
        """Create coordinator data with zones keyed by AirTouch zone id."""
        return cls(
            aircon=aircon,
            zones={zone.id: zone for zone in aircon.zones},
        )


async def async_fetch_airtouch_data(host: str, port: int = DEFAULT_PORT) -> Aircon:
    """Fetch and parse data from an AirTouch 3 controller."""
    try:
        aircon = await AirTouchClient(host, port, logger=_LOGGER).fetch_aircon()
    except AirTouchError as err:
        _LOGGER.debug("AirTouch 3 communication with %s:%s failed: %s", host, port, err)
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if getattr(aircon, "ac_id", None) is None:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": "response did not include an AC id"},
        )
    return aircon


class Airtouch3DataUpdateCoordinator(DataUpdateCoordinator[AirTouch3Data]):
    """Class to manage fetching Airtouch 3 data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize the Airtouch data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._entry = entry
        self.host = host
        self.port = port
        self._client = AirTouchClient(host, port, logger=_LOGGER)

    @property
    def system_id(self) -> str:
        """Return a stable controller identifier for entity unique IDs."""
        return self._entry.unique_id or self.host

    async def _async_update_data(self) -> AirTouch3Data:
        """Fetch data from AirTouch."""
        return AirTouch3Data.from_aircon(
            await async_fetch_airtouch_data(self.host, self.port)
        )

    async def send_command(
        self, command_type: str, target_id: int, value: Any = None
    ) -> None:
        """Send a command to the AirTouch unit."""
        command_key = command_type
        if hasattr(command_key, "value"):
            command_key = command_key.value
        if not isinstance(command_key, str):
            command_key = str(command_key)

        if command_key == "turn_on":
            if not self.data.aircon.status:
                _LOGGER.debug("AC is off, sending turn_on command")
                self.data.aircon.status = True
            else:
                _LOGGER.debug("AC is already on, skipping turn_on command")
                return
        elif command_key == "turn_off":
            if self.data.aircon.status:
                _LOGGER.debug("AC is on, sending turn_off command")
                self.data.aircon.status = False
            else:
                _LOGGER.debug("AC is already off, skipping turn_off command")
                return
        elif command_key != "toggle_zone" and command_key not in VALUE_COMMANDS:
            _LOGGER.error("Unknown command type: %s", command_key)
            return

        try:
            if command_key == "set_mode":
                await self._client.set_mode(target_id, self.data.aircon.brand_id, value)
            elif command_key == "set_fan_speed":
                await self._client.set_fan_speed(
                    target_id, self.data.aircon.brand_id, value
                )
            elif command_key == "set_group_temperature":
                await self._client.adjust_zone_temperature(target_id, value)
            elif command_key in {"turn_on", "turn_off"}:
                await self._client.toggle_ac_power(target_id)
            elif command_key == "toggle_zone":
                await self._client.toggle_zone(target_id)

            _LOGGER.debug(
                "Sent %s command to AirTouch target %s with value %s",
                command_key,
                target_id,
                value,
            )
        except AirTouchError as err:
            _LOGGER.error("Failed to send command to AirTouch: %s", err)

    async def adjust_temperature(self, zone_id: int, target_temp: int) -> None:
        """Adjust temperature by sending repeated set_fan commands based on current target."""
        if (zone := self.data.zones.get(zone_id)) is None:
            _LOGGER.error("Current target temperature for zone %s not found", zone_id)
            return

        current_target = zone.desired_temperature
        diff = target_temp - current_target
        inc_dec = 1 if diff > 0 else -1
        num_steps = abs(int(diff))

        _LOGGER.debug(
            "Adjusting temperature for zone %s from %s to %s with %s steps",
            zone_id,
            current_target,
            target_temp,
            num_steps,
        )

        for _ in range(num_steps):
            await self.send_command("set_group_temperature", zone_id, inc_dec)
            _LOGGER.debug("Adjusting temperature by %s for zone %s", inc_dec, zone_id)
