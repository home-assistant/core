"""TFA.me station integration: data.py."""

from typing import Any

from tfa_me_ha_local.client import (
    TFAmeClient,
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .helper import resolve_tfa_host


class TFAmeData:
    """Small helper used by the config flow to talk to a TFA.me station."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize helper with user-provided address (IP or station ID)."""
        self._hass = hass
        self._address = address.strip()
        self._host = resolve_tfa_host(self._address)
        self._client: TFAmeClient
        session = async_get_clientsession(self._hass)
        # Same base path and options as in the coordinator
        self._client = TFAmeClient(
            self._host,
            "sensors",
            log_level=1,
            session=session,
        )

    def _get_client(self) -> TFAmeClient:
        """Return a TFA.me client instance for this host."""
        return self._client

    async def get_identifier(self) -> str:
        """Fetch and return the unique station/gateway ID from the device."""
        client = self._get_client()

        try:
            # Fetch the raw JSON once, just like the coordinator does.
            json_data: dict[str, Any] = await client.async_get_sensors()
        except (TFAmeHTTPError, TFAmeJSONError) as err:
            # Device responds but data is invalid
            raise TFAmeException(f"invalid_response: {err}") from err
        except (TFAmeTimeoutError, TFAmeConnectionError) as err:
            # Timeout or connection error
            raise TFAmeException(f"cannot_connect: {err}") from err
        except Exception as err:
            # Catch-all for unknown errors
            raise TFAmeException(f"unknown: {err}") from err

        # Extract the actual station/gateway ID from json_data
        identifier: str | None = None
        identifier = json_data.get("gateway_id")

        if not identifier:
            # No ID, something is wrong with the data format
            raise TFAmeException("missing_identifier")

        return identifier
