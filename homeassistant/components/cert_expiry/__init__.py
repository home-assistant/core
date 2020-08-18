"""The cert_expiry component."""
from datetime import datetime, timedelta
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CA_CERT, DEFAULT_PORT, DOMAIN
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_expiry_timestamp

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


async def async_setup(hass, config):
    """Platform setup, do nothing."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = CertExpiryDataUpdateCoordinator(hass, entry)
    await coordinator.async_set_options()
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[datetime]):
    """Class to manage fetching Cert Expiry data from single endpoint."""

    def __init__(self, hass, config_entry):
        """Initialize global Cert Expiry data updater."""
        self.config_entry = config_entry
        self.cert_error = None
        self.is_cert_valid = False

        self.unique_id = (
            f"{self.config_entry.data[CONF_HOST]}:{self.config_entry.data[CONF_PORT]}"
        )

        display_port = config_entry.options.get(
            CONF_PORT, config_entry.data.get(CONF_PORT, "")
        )
        host = config_entry.options.get(CONF_HOST, config_entry.data.get(CONF_HOST))
        name = f"{host}{display_port}"

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Optional[datetime]:
        """Fetch certificate."""

        try:
            timestamp = await get_cert_expiry_timestamp(
                self.hass,
                self.config_entry.options[CONF_HOST],
                self.config_entry.options[CONF_PORT],
                self.config_entry.options[CONF_CA_CERT],
            )
        except TemporaryFailure as err:
            raise UpdateFailed(err.args[0]) from err
        except ValidationFailure as err:
            self.cert_error = err
            self.is_cert_valid = False
            _LOGGER.error(
                "Certificate validation error: %s [%s]",
                self.config_entry.options[CONF_HOST],
                err,
            )
            return None

        self.cert_error = None
        self.is_cert_valid = True
        return timestamp

    async def async_set_options(self):
        """Set options for cert_expiry entry."""
        if not self.config_entry.options:
            data = {**self.config_entry.data}
            options = {
                CONF_HOST: data.pop(CONF_HOST, ""),
                CONF_PORT: data.pop(CONF_PORT, DEFAULT_PORT),
                CONF_CA_CERT: data.pop(CONF_CA_CERT, ""),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options=options
            )
