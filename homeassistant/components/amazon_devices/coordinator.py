"""Support for Amazon Devices."""

from datetime import timedelta
from typing import Any

from aioamazondevices import AmazonDevice, AmazonEchoApi, exceptions
from aioamazondevices.const import DEVICE_TYPE_TO_MODEL

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class AmazonDevicesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base coordinator for Amazon Devices."""

    config_entry: ConfigEntry
    api: AmazonEchoApi

    def __init__(
        self,
        hass: HomeAssistant,
        country: str,
        username: str,
        password: str,
        login_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the scanner."""

        self.api = AmazonEchoApi(country, username, password, login_data)

        self._login_username = username
        self._login_country = country
        assert login_data

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{username}-coordinator",
            update_interval=timedelta(seconds=30),
        )
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, login_data["customer_info"]["user_id"])},
            name="Amazon Devices",
            manufacturer="Amazon",
        )

    def device_info(self, device: AmazonDevice) -> dr.DeviceInfo:
        """Set device info."""

        return dr.DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.config_entry.entry_id}-{device.serial_number}",
                )
            },
            via_device=(DOMAIN, self.config_entry.entry_id),
            name=device.account_name,
            model=DEVICE_TYPE_TO_MODEL.get(device.device_type),
            manufacturer="Amazon",
            hw_version=device.device_type,
            sw_version=device.software_version,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data."""
        _LOGGER.debug(
            "Polling Amazon %s for %s's devices",
            self._login_country,
            self._login_username,
        )
        try:
            await self.api.login_mode_stored_data()
            return await self.api.get_devices_data()
        except (exceptions.CannotConnect, exceptions.CannotRetrieveData) as err:
            raise UpdateFailed(repr(err)) from err
        except exceptions.CannotAuthenticate as err:
            raise ConfigEntryAuthFailed from err
