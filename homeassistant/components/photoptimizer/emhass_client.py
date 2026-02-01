"""Client for EMHASS communication."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class EmhassClient:
    """HTTP client to interact with EMHASS."""

    def __init__(self, hass, url: str) -> None:
        """Store session and base URL."""
        self._hass = hass
        self._url = url.rstrip("/")
        self._session = async_get_clientsession(hass)

    async def async_post_mpc_optim(
        self, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send payload to endpoint and return JSON response."""

        endpoint = f"{self._url}/action/naive-mpc-optim"
        try:
            async with self._session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("EMHASS response keys: %s", list(data.keys()))
                    return data
                text = await response.text()
                _LOGGER.error("EMHASS error %s: %s", response.status, text)
                return None
        except ClientError as err:
            _LOGGER.error("EMHASS connection error at %s: %s", endpoint, err)
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("EMHASS unexpected error at %s: %s", endpoint, err)
            return None
