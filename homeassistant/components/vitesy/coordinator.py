"""Coordinator for the Vitesy integration."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import override

from aiovitesy.api import VitesyApi, VitesyDevice, VitesyModeStatus
from aiovitesy.exceptions import CannotAuthenticate, VitesyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type VitesyConfigEntry = ConfigEntry[VitesyDataUpdateCoordinator]

UPDATE_INTERVAL = timedelta(minutes=5)


def supports_mode(device: VitesyDevice) -> bool:
    """Return True for devices whose mode can be read and set (Shelfy)."""
    return device.device_type.upper().startswith("SHELFY")


@contextmanager
def _translate_errors(*, auth_recoverable: bool = False) -> Iterator[None]:
    """Convert aiovitesy errors into coordinator setup/update failures.

    On a refresh, auth_recoverable must be True: the config flow has no
    reauth step yet, so raising ConfigEntryAuthFailed there would stop
    polling forever with no way to recover.
    """
    try:
        yield
    except CannotAuthenticate as err:
        if auth_recoverable:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except VitesyError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN, translation_key="update_failed"
        ) from err


class VitesyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, VitesyDevice]]):
    """Fetch state for every device of a Vitesy Hub account."""

    config_entry: VitesyConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: VitesyConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = VitesyApi(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
            async_get_clientsession(hass),
        )
        self.mode_status: dict[str, VitesyModeStatus] = {}

    @override
    async def _async_setup(self) -> None:
        """Authenticate against Vitesy Hub before the first refresh."""
        with _translate_errors():
            await self.api.login()

    @override
    async def _async_update_data(self) -> dict[str, VitesyDevice]:
        """Fetch the latest state for every device in the account."""
        with _translate_errors(auth_recoverable=True):
            devices = await self.api.get_all_devices()
        self.mode_status = await self._async_get_mode_status(devices)
        return devices

    async def _async_get_mode_status(
        self, devices: dict[str, VitesyDevice]
    ) -> dict[str, VitesyModeStatus]:
        """Read the mode of every device that supports it.

        The mode lives in the device's AWS IoT shadow, not the REST API, so a
        failure there only drops that device's mode instead of failing the
        whole refresh.
        """
        mode_status: dict[str, VitesyModeStatus] = {}
        for device_id, device in devices.items():
            if not supports_mode(device):
                continue
            try:
                mode_status[device_id] = await self.api.get_mode_status(device_id)
            except VitesyError as err:
                LOGGER.debug("Could not read mode of %s: %s", device.name, err)
        return mode_status
