"""Data update coordinator for AVM FRITZ!SmartHome devices."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pyfritzhome import Fritzhome, FritzhomeDevice, LoginError
from pyfritzhome.devicetypes import FritzhomeTemplate
from requests.exceptions import ConnectionError as RequestConnectionError, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CONNECTIONS, DOMAIN, LOGGER


@dataclass
class FritzboxCoordinatorData:
    """Data Type of FritzboxDataUpdateCoordinator's data."""

    devices: dict[str, FritzhomeDevice]
    templates: dict[str, FritzhomeTemplate]


class FritzboxDataUpdateCoordinator(DataUpdateCoordinator[FritzboxCoordinatorData]):
    """Fritzbox Smarthome device data update coordinator."""

    configuration_url: str

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, has_templates: bool
    ) -> None:
        """Initialize the Fritzbox Smarthome device coordinator."""
        self.entry = entry
        self.fritz: Fritzhome = hass.data[DOMAIN][self.entry.entry_id][CONF_CONNECTIONS]
        self.configuration_url = self.fritz.get_prefixed_host()
        self.has_templates = has_templates

        super().__init__(
            hass,
            LOGGER,
            name=entry.entry_id,
            update_interval=timedelta(seconds=30),
        )

    def _update_fritz_devices(self) -> FritzboxCoordinatorData:
        """Update all fritzbox device data."""
        try:
            self.fritz.update_devices()
            if self.has_templates:
                self.fritz.update_templates()
        except RequestConnectionError as ex:
            raise UpdateFailed from ex
        except HTTPError:
            # If the device rebooted, login again
            try:
                self.fritz.login()
            except LoginError as ex:
                raise ConfigEntryAuthFailed from ex
            self.fritz.update_devices()
            if self.has_templates:
                self.fritz.update_templates()

        devices = self.fritz.get_devices()
        device_data = {}
        for device in devices:
            # assume device as unavailable, see #55799
            if (
                device.has_powermeter
                and device.present
                and isinstance(device.voltage, int)
                and device.voltage <= 0
                and isinstance(device.power, int)
                and device.power <= 0
                and device.energy <= 0
            ):
                LOGGER.debug("Assume device %s as unavailable", device.name)
                device.present = False

            device_data[device.ain] = device

        template_data = {}
        if self.has_templates:
            templates = self.fritz.get_templates()
            for template in templates:
                template_data[template.ain] = template

        return FritzboxCoordinatorData(devices=device_data, templates=template_data)

    async def _async_update_data(self) -> FritzboxCoordinatorData:
        """Fetch all device data."""
        return await self.hass.async_add_executor_job(self._update_fritz_devices)
