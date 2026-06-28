"""DataUpdateCoordinator for Teltonika."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from aiohttp import ClientResponseError, ContentTypeError
from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError
from teltasync.error_codes import TeltonikaErrorCode
from teltasync.modems import Modems, ModemStatusFull

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import TeltonikaConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
AUTH_ERROR_CODES = frozenset(
    {
        TeltonikaErrorCode.UNAUTHORIZED_ACCESS,
        TeltonikaErrorCode.LOGIN_FAILED,
        TeltonikaErrorCode.INVALID_JWT_TOKEN,
    }
)


def _is_auth_error(err: ClientResponseError) -> bool:
    """Return whether an HTTP error indicates an authentication failure."""
    return err.status in (401, 403)


class TeltonikaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ModemStatusFull]]):
    """Class to manage fetching Teltonika data."""

    device_info: DeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        client: Teltasync,
        config_entry: TeltonikaConfigEntry,
        base_url: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Teltonika",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.base_url = base_url

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator - authenticate and fetch device info."""
        try:
            await self.client.get_device_info()
            system_info_response = await self.client.get_system_info()
        except TeltonikaAuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (ClientResponseError, ContentTypeError) as err:
            if _is_auth_error(err):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err
        except TeltonikaConnectionError as err:
            raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err

        # Store device info for use by entities
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info_response.mnf_info.serial)},
            connections={
                (CONNECTION_NETWORK_MAC, mac)
                for mac in (
                    system_info_response.mnf_info.mac_eth,
                    system_info_response.mnf_info.mac,
                )
                if mac
            },
            name=system_info_response.static.device_name,
            manufacturer="Teltonika",
            model=system_info_response.static.model,
            sw_version=system_info_response.static.fw_version,
            serial_number=system_info_response.mnf_info.serial,
            configuration_url=self.base_url,
        )

    @override
    async def _async_update_data(self) -> dict[str, ModemStatusFull]:
        """Fetch data from Teltonika device."""
        return await self._async_with_reauth(self._async_fetch_modems)

    async def _async_with_reauth[DataT](
        self, fetch: Callable[[], Awaitable[DataT]]
    ) -> DataT:
        """Run a device call, re-authenticating once if the session was rejected.

        After e.g. a device reboot, the session might become invalidated, but still
        look valid from the timestamp in the JWT. In this case, we try to authenticate
        again with the same credentials and retry the request. A reauth flow is only
        started when re-authentication itself is rejected, i.e. the stored
        credentials are no longer valid.
        """
        try:
            return await fetch()
        except TeltonikaConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except TeltonikaAuthenticationError:
            self.client.auth.clear_token()

            try:
                await self.client.auth.authenticate()
            except TeltonikaAuthenticationError as err:
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            except TeltonikaConnectionError as err:
                raise UpdateFailed(f"Error communicating with device: {err}") from err

            try:
                return await fetch()
            except (TeltonikaAuthenticationError, TeltonikaConnectionError) as err:
                raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _async_fetch_modems(self) -> dict[str, ModemStatusFull]:
        """Fetch the online modems keyed by id."""
        modems = Modems(self.client.auth)
        try:
            modems_response = await modems.get_status()
        except (ClientResponseError, ContentTypeError) as err:
            if _is_auth_error(err):
                raise TeltonikaAuthenticationError(str(err)) from err
            raise TeltonikaConnectionError(str(err)) from err

        if not modems_response.success:
            if modems_response.errors and any(
                error.code in AUTH_ERROR_CODES for error in modems_response.errors
            ):
                raise TeltonikaAuthenticationError("unauthorized access")

            error_message = (
                modems_response.errors[0].error
                if modems_response.errors
                else "Unknown API error"
            )
            raise TeltonikaConnectionError(error_message)

        return {
            modem.id: modem
            for modem in (modems_response.data or [])
            if isinstance(modem, ModemStatusFull)
        }
