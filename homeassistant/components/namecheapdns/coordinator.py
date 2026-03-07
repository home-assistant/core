"""Coordinator for the Namecheap DynamicDNS integration."""

from datetime import timedelta
import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helpers import AuthFailed, update_namecheapdns

_LOGGER = logging.getLogger(__name__)


type NamecheapConfigEntry = ConfigEntry[NamecheapDnsUpdateCoordinator]


INTERVAL = timedelta(minutes=5)


class NamecheapDnsUpdateCoordinator(DataUpdateCoordinator[None]):
    """Namecheap DynamicDNS update coordinator."""

    config_entry: NamecheapConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: NamecheapConfigEntry) -> None:
        """Initialize the Namecheap DynamicDNS update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=INTERVAL,
        )

        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> None:
        """Update Namecheap DNS."""
        host = self.config_entry.data[CONF_HOST]
        domain = self.config_entry.data[CONF_DOMAIN]
        password = self.config_entry.data[CONF_PASSWORD]

        try:
            if not await update_namecheapdns(self.session, host, domain, password):
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                    translation_placeholders={CONF_DOMAIN: f"{host}.{domain}"},
                )
        except AuthFailed as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={CONF_DOMAIN: f"{host}.{domain}"},
            ) from e
        except ClientError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={CONF_DOMAIN: f"{host}.{domain}"},
            ) from e
