"""DataUpdateCoordinator for NRGkick integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, override

from nrgkick_api import (
    NRGkickAPI,
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
    NRGkickHTTPError,
    NRGkickInvalidResponseError,
    NRGkickTimeoutError,
    NRGkickUnreachableError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Type alias for typed config entry with runtime_data.
type NRGkickConfigEntry = ConfigEntry[NRGkickDataUpdateCoordinator]


@dataclass(slots=True)
class NRGkickData:
    """Container for coordinator data."""

    info: dict[str, Any]
    control: dict[str, Any]
    values: dict[str, Any]


class NRGkickDataUpdateCoordinator(DataUpdateCoordinator[NRGkickData]):
    """Class to manage fetching NRGkick data from the API."""

    config_entry: NRGkickConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: NRGkickAPI, entry: NRGkickConfigEntry
    ) -> None:
        """Initialize."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> NRGkickData:
        """Update data via library."""
        try:
            info = await self.api.get_info(raw=True)
            control = await self.api.get_control()
            values = await self.api.get_values(raw=True)
        except NRGkickAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NRGkickAPIDisabledError as error:
            # Only the user can enable the API again in the NRGkick app.
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._json_api_disabled_issue_id,
                config_entry_id=self.config_entry.entry_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="json_api_disabled",
                translation_placeholders={"device_name": self.config_entry.title},
            )
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="json_api_disabled",
            ) from error
        except NRGkickTimeoutError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from error
        except NRGkickUnreachableError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unreachable",
            ) from error
        except NRGkickHTTPError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="http_error",
                translation_placeholders={"status": str(error.status)},
            ) from error
        except NRGkickConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error
        except NRGkickInvalidResponseError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error

        ir.async_delete_issue(self.hass, DOMAIN, self._json_api_disabled_issue_id)
        return NRGkickData(info=info, control=control, values=values)

    @property
    def _json_api_disabled_issue_id(self) -> str:
        """Return the ID of the repair issue for a disabled JSON API."""
        return f"json_api_disabled_{self.config_entry.entry_id}"
