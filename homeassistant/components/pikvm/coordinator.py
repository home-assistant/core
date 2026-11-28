"""Data update coordinator for the PiKVM integration."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, override

from pikvm_aio import PiKVMAuthenticationError, PiKVMClient, PiKVMDeviceInfo, PiKVMError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import CONF_TOTP, DOMAIN, LOGGER

type PiKVMConfigEntry = ConfigEntry[PiKVMDataUpdateCoordinator]


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> PiKVMClient:
    """Create a PiKVM API client from config entry data."""
    host = data[CONF_HOST].strip()
    if "://" in host and not host.lower().startswith("https://"):
        raise ValueError("Only HTTPS URLs or bare hostnames are supported")
    # Stock PiKVM certificates are self-signed, so verification is opt-in.
    verify_ssl = data.get(CONF_VERIFY_SSL, False)
    return PiKVMClient(
        host=host,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        totp_secret=data.get(CONF_TOTP) or None,
        session=async_get_clientsession(hass, verify_ssl=verify_ssl),
        ssl_context=(
            get_default_context() if verify_ssl else get_default_no_verify_context()
        ),
    )


class PiKVMDataUpdateCoordinator(DataUpdateCoordinator[PiKVMDeviceInfo]):
    """Class to manage fetching PiKVM data."""

    config_entry: PiKVMConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PiKVMConfigEntry,
        client: PiKVMClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> PiKVMDeviceInfo:
        try:
            return await self.client.get_info()
        except PiKVMAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PiKVMError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
            ) from err
