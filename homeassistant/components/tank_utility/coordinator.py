"""DataUpdateCoordinator for the Tank Utility integration."""

from typing import Any, override

import requests
from tank_utility import auth, device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type TankUtilityConfigEntry = ConfigEntry[TankUtilityDataUpdateCoordinator]


class TankUtilityDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, Any]]]
):
    """Class to manage fetching Tank Utility data from the API."""

    config_entry: TankUtilityConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TankUtilityConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    def _get_raw_data(
        self, email: str, password: str, configured_devices: list[str] | None
    ) -> dict[str, dict[str, Any]]:
        """Retrieve raw device data from Tank Utility."""
        if configured_devices is None:
            return device.get_data(email, password)
        token = auth.get_token(email, password)
        data: dict[str, dict[str, Any]] = {}
        for dev_id in configured_devices:
            try:
                data[dev_id] = device.get_device_data(token, dev_id)
            except requests.exceptions.HTTPError as err:
                if (
                    err.response is None
                    or err.response.status_code != requests.codes.not_found
                ):
                    raise
        return data

    def _fetch_data(self) -> dict[str, dict[str, Any]]:
        """Fetch and flatten device data from Tank Utility API."""
        email = self.config_entry.data[CONF_EMAIL]
        password = self.config_entry.data[CONF_PASSWORD]
        configured_devices: list[str] | None = self.config_entry.data.get(CONF_DEVICES)
        try:
            raw_data = self._get_raw_data(email, password, configured_devices)
        except requests.exceptions.HTTPError as err:
            if err.response is not None and err.response.status_code in (
                requests.codes.bad_request,
                requests.codes.unauthorized,
            ):
                auth.get_token(email, password, force=True)
                raw_data = self._get_raw_data(email, password, configured_devices)
            else:
                raise

        flattened: dict[str, dict[str, Any]] = {}
        for dev_id, dev_data in raw_data.items():
            item = dict(dev_data)
            item.update(item.pop("device", {}))
            item.update(item.pop("lastReading", {}))
            flattened[dev_id] = item
        return flattened

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Tank Utility."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except requests.exceptions.HTTPError as err:
            if (
                err.response is not None
                and err.response.status_code == requests.codes.unauthorized
            ):
                raise ConfigEntryAuthFailed("Invalid credentials") from None
            status = (
                f"HTTP {err.response.status_code}"
                if err.response is not None
                else type(err).__name__
            )
            raise UpdateFailed(
                f"Error communicating with Tank Utility: {status}"
            ) from None
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(
                f"Error communicating with Tank Utility: {type(err).__name__}"
            ) from None
