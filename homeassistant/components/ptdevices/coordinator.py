"""Coordinator for PTDevices integration."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Final

import aioptdevices
from aioptdevices.interface import Interface, PTDevicesResponseData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REFRESH_COOLDOWN: Final = 30
UPDATE_INTERVAL = timedelta(seconds=60)

type PTDevicesConfigEntry = ConfigEntry[PTDevicesCoordinator]


class PTDevicesCoordinator(DataUpdateCoordinator[PTDevicesResponseData]):
    """Class for interacting with PTDevices get_data."""

    config_entry: PTDevicesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PTDevicesConfigEntry,
        ptdevices_interface: Interface,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
                cooldown=REFRESH_COOLDOWN,
            ),
        )

        self.interface = ptdevices_interface

        # Holds device_id and sensor.key in the tuple
        self.known_sensors: set[tuple[str, str]] = set()

        self.new_sensor_callbacks: list[Callable[[list[tuple[str, str]]], None]] = []

    async def _async_update_data(self) -> PTDevicesResponseData:
        try:
            data = await self.interface.get_data()
        except aioptdevices.PTDevicesRequestError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesUnauthorizedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_access_token",
                translation_placeholders={"error": repr(err)},
            ) from err

        self._async_add_remove_entities(data["body"])
        return data["body"]

    def _async_add_remove_entities(
        self,
        new_data: PTDevicesResponseData,
    ) -> None:
        # Purge stale devices
        device_reg = dr.async_get(self.hass)
        identifiers = {
            (DOMAIN, f"{device_data['user_id']}_{device_id}")
            for device_id, device_data in new_data.items()
        }
        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            if not set(device.identifiers) & identifiers:
                _LOGGER.debug("Removing stale device entry %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )

        # Sensor management
        new_sensors = {
            (device_id, sensor)
            for device_id in new_data
            for sensor in new_data[device_id]
            if (device_id, sensor) not in self.known_sensors
        }
        if new_sensors:
            _LOGGER.debug("New sensors found: %s", new_sensors)
            self.known_sensors.update(new_sensors)
            new_sensor_data = list(new_sensors)
            for new_sensor_callback in self.new_sensor_callbacks:
                new_sensor_callback(new_sensor_data)
