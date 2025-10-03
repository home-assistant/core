"""Support for Alexa Devices."""

from datetime import timedelta

from aioamazondevices.api import AmazonDevice, AmazonEchoApi
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, CONF_LOGIN_DATA, DOMAIN

SCAN_INTERVAL = 30

type AmazonConfigEntry = ConfigEntry[AmazonDevicesCoordinator]


class AmazonDevicesCoordinator(DataUpdateCoordinator[dict[str, AmazonDevice]]):
    """Base coordinator for Alexa Devices."""

    config_entry: AmazonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AmazonConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            config_entry=entry,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api = AmazonEchoApi(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_LOGIN_DATA],
        )
        self.previous_devices: set[str] = set()

    async def _async_update_data(self) -> dict[str, AmazonDevice]:
        """Update device data."""
        try:
            await self.api.login_mode_stored_data()
            data = await self.api.get_devices_data()
        except CannotConnect as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotRetrieveData as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotAuthenticate as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        else:
            current_devices = set(data.keys())
            if stale_devices := self.previous_devices - current_devices:
                await self._async_remove_device_stale(stale_devices)

            self.previous_devices = current_devices
            return data

    async def _async_remove_device_stale(
        self,
        stale_devices: set[str],
    ) -> None:
        """Remove stale device."""
        device_registry = dr.async_get(self.hass)

        for serial_num in stale_devices:
            _LOGGER.debug(
                "Detected change in devices: serial %s removed",
                serial_num,
            )
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, serial_num)}
            )
            if device:
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
