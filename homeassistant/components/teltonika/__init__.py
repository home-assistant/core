"""The Teltonika integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError, ContentTypeError
from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_VALIDATE_SSL, DOMAIN
from .coordinator import TeltonikaDataUpdateCoordinator
from .util import base_url_to_host, candidate_base_urls

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type TeltonikaConfigEntry = ConfigEntry[TeltonikaData]


class TeltonikaData:
    """Runtime data for Teltonika integration."""

    def __init__(
        self,
        coordinator: TeltonikaDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the runtime data."""
        self.coordinator = coordinator
        self.device_info = device_info


async def _try_connect(
    host: str,
    username: str,
    password: str,
    validate_ssl: bool,
    session: Any,
) -> tuple[Teltasync, str, Any]:
    """Try to connect to device with different protocol schemes.

    Returns tuple of (client, base_url, system_info_response).
    Raises ConfigEntryAuthFailed for authentication issues.
    Raises ConfigEntryNotReady for connection issues.
    """
    last_error: Exception | None = None

    for candidate in candidate_base_urls(host):
        candidate_client = Teltasync(
            base_url=candidate,
            username=username,
            password=password,
            session=session,
            verify_ssl=validate_ssl,
        )

        try:
            await candidate_client.get_device_info()
            system_info_response = await candidate_client.get_system_info()
        except TeltonikaConnectionError as err:
            last_error = err
            await candidate_client.close()
        except TeltonikaAuthenticationError as err:
            await candidate_client.close()
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except ContentTypeError as err:
            # Device returned HTML instead of JSON - likely auth failure
            await candidate_client.close()
            if err.status == 403:
                raise ConfigEntryAuthFailed(
                    f"Access denied - check credentials: {err}"
                ) from err
            last_error = err
        except ClientResponseError as err:
            await candidate_client.close()
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    f"Authentication failed (HTTP {err.status}): {err.message}"
                ) from err
            last_error = err
        except Exception as err:  # pylint: disable=broad-except
            await candidate_client.close()
            # Check if error message indicates authentication issues
            error_str = str(err).lower()
            if any(
                keyword in error_str
                for keyword in ("auth", "unauthorized", "forbidden", "credentials")
            ):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            last_error = err
        else:
            return candidate_client, candidate, system_info_response

    raise ConfigEntryNotReady(
        f"Failed to connect to device at {host}: {last_error}"
    ) from last_error


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Set up Teltonika from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    validate_ssl = entry.data.get(CONF_VALIDATE_SSL, False)
    session = async_get_clientsession(hass)

    client, selected_base_url, system_info_response = await _try_connect(
        host, username, password, validate_ssl, session
    )

    selected_host = base_url_to_host(selected_base_url)
    if selected_host != host:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HOST: selected_host},
        )

    # Create device info for device registry
    device_info = DeviceInfo(
        identifiers={(DOMAIN, system_info_response.mnf_info.serial)},
        name=system_info_response.static.device_name,
        manufacturer="Teltonika",
        model=system_info_response.static.model,
        sw_version=system_info_response.static.fw_version,
        serial_number=system_info_response.mnf_info.serial,
        configuration_url=selected_host,
    )

    # Create coordinator
    coordinator = TeltonikaDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data to ensure device is reachable
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = TeltonikaData(coordinator, device_info)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.coordinator.client.close()

    return unload_ok
