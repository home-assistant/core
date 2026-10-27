"""Asynchronous local meter updates."""

from datetime import timedelta
import logging
import re
from typing import Any, override

from iammeter.async_client import (
    AsyncClient,
    IammeterAuthError,
    IammeterConnectionError,
)
from iammeter.models import SUPPORTED_MODELS, IammeterDataError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
type IammeterConfigEntry = ConfigEntry[IammeterDataUpdateCoordinator]


def meter_identity(data: dict[str, Any]) -> str:
    """Use a serial number, or a stable MAC for older single-phase meters."""
    serial = data.get("sn")
    if isinstance(serial, str) and serial.strip():
        return serial
    mac = data.get("mac")
    if isinstance(mac, str):
        normalized = mac.strip().lower().replace(":", "").replace("-", "")
        if re.fullmatch(r"[0-9a-f]{12}", normalized) and normalized not in (
            "000000000000",
            "ffffffffffff",
        ):
            return f"mac_{normalized}"
    raise IammeterDataError("Missing serial number and valid MAC address")


def validate_data(data: dict[str, Any]) -> None:
    """Validate the stable identity and supported model."""
    if data.get("Model") not in SUPPORTED_MODELS:
        raise IammeterDataError("Unsupported meter model")
    meter_identity(data)


def create_client(hass: HomeAssistant, data: dict[str, Any]) -> AsyncClient:
    """Inject the shared HA session into the independent library."""
    return AsyncClient(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data.get(CONF_PORT, DEFAULT_PORT),
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
    )


async def async_get_meter(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a connection before adding or reconfiguring it."""
    result = await create_client(hass, data).async_get_data()
    validate_data(result)
    return result


class IammeterDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll without blocking the event loop or rejecting changed serials."""

    config_entry: IammeterConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
        """Initialize the shared-session client and polling interval."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = create_client(hass, dict(entry.data))

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_get_data()
            validate_data(data)
        except IammeterAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except (IammeterConnectionError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        issue_id = f"identity_changed_{self.config_entry.entry_id}"
        if meter_identity(data) != self.config_entry.unique_id:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="identity_changed",
                translation_placeholders={"name": self.config_entry.title},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return data
