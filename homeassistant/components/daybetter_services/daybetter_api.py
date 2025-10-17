"""DayBetter API client."""

from __future__ import annotations

import logging
from typing import Any

from daybetter_python import DayBetterClient
from daybetter_python.exceptions import APIError, AuthenticationError, DayBetterError

from homeassistant.core import HomeAssistant

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class DayBetterApi:
    """DayBetter API client."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.token = token
        self._client = DayBetterClient(token=token, base_url=API_BASE_URL)
        self._auth_valid = True

    async def fetch_devices(self) -> list[dict[str, Any]]:
        """Get list of devices."""
        try:
            devices = await self._client.fetch_devices()
            _LOGGER.debug("Fetched devices: %s", devices)
            self._auth_valid = True
        except AuthenticationError:
            _LOGGER.error("Authentication failed - token may be expired")
            self._auth_valid = False
            devices = []
        except (APIError, DayBetterError) as e:
            _LOGGER.error("Failed to fetch devices: %s", str(e))
            devices = []
        except Exception:
            _LOGGER.exception("Exception while fetching devices")
            devices = []
        else:
            return devices
        return devices

    async def fetch_pids(self) -> dict[str, Any]:
        """Get list of PIDs for different device types."""
        try:
            pids = await self._client.fetch_pids()
            self._auth_valid = True
        except AuthenticationError:
            _LOGGER.error("Authentication failed - token may be expired")
            self._auth_valid = False
            pids = {}
        except (APIError, DayBetterError) as e:
            _LOGGER.error("Failed to fetch PIDs: %s", str(e))
            pids = {}
        except Exception:
            _LOGGER.exception("Exception while fetching PIDs")
            pids = {}
        else:
            return pids
        return pids

    async def control_device(
        self,
        device_name: str,
        action: bool,
        brightness: int | None,
        hs_color: tuple[float, float] | None,
        color_temp: int | None,
    ) -> dict[str, Any]:
        """Control a device."""
        try:
            result = await self._client.control_device(
                device_name=device_name,
                action=action,
                brightness=brightness,
                hs_color=hs_color,
                color_temp=color_temp,
            )
            self._auth_valid = True
        except AuthenticationError:
            _LOGGER.error("Authentication failed - token may be expired")
            self._auth_valid = False
            result = {"code": 0, "message": "Authentication failed"}
        except (APIError, DayBetterError) as e:
            _LOGGER.error("Failed to control device %s: %s", device_name, str(e))
            result = {"code": 0, "message": str(e)}
        except Exception:
            _LOGGER.exception("Exception while controlling device %s", device_name)
            result = {"code": 0, "message": "Unknown error"}
        else:
            return result
        return result

    async def fetch_mqtt_config(self) -> dict[str, Any]:
        """Get MQTT connection configuration information."""
        try:
            config = await self._client.fetch_mqtt_config()
            _LOGGER.debug("MQTT configuration: %s", config)
            self._auth_valid = True
        except AuthenticationError:
            _LOGGER.error("Authentication failed - token may be expired")
            self._auth_valid = False
            config = {}
        except (APIError, DayBetterError) as e:
            _LOGGER.error("Failed to fetch MQTT config: %s", str(e))
            config = {}
        except Exception:
            _LOGGER.exception("Exception while fetching MQTT config")
            config = {}
        else:
            return config
        return config

    @property
    def is_authenticated(self) -> bool:
        """Check if the API client is authenticated."""
        return self._auth_valid
