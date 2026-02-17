"""The Control4 integration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import (
    API_RETRY_TIMES,
    CONF_CONTROLLER_UNIQUE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.LIGHT, Platform.MEDIA_PLAYER]


@dataclass
class Control4RuntimeData:
    """Control4 runtime data."""

    account: C4Account
    controller_unique_id: str
    director: C4Director
    director_all_items: list[dict[str, Any]]
    director_model: str
    director_sw_version: str
    scan_interval: int
    ui_configuration: dict[str, Any] | None


type Control4ConfigEntry = ConfigEntry[Control4RuntimeData]


async def call_c4_api_retry(func, *func_args):
    """Call C4 API function and retry on failure."""
    exc = None
    for i in range(API_RETRY_TIMES):
        try:
            return await func(*func_args)
        except client_exceptions.ClientError as exception:
            _LOGGER.debug(
                "Attempt %d/%d failed connecting to Control4 account API: %s",
                i + 1,
                API_RETRY_TIMES,
                exception,
            )
            exc = exception

    _LOGGER.error(
        "Failed to connect to Control4 account API after %d attempts: %s",
        API_RETRY_TIMES,
        exc,
    )
    raise ConfigEntryNotReady(
        f"Failed to connect to Control4 account API after {API_RETRY_TIMES} attempts"
    ) from exc


async def async_setup_entry(hass: HomeAssistant, entry: Control4ConfigEntry) -> bool:
    """Set up Control4 from a config entry."""
    account_session = aiohttp_client.async_get_clientsession(hass)

    config = entry.data
    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD], account_session)
    try:
        await account.getAccountBearerToken()
    except client_exceptions.ClientError as exception:
        _LOGGER.error("Error connecting to Control4 account API: %s", exception)
        raise ConfigEntryNotReady(
            "Error connecting to Control4 account API to get bearer token"
        ) from exception
    except BadCredentials as exception:
        _LOGGER.error(
            (
                "Error authenticating with Control4 account API, incorrect username or"
                " password: %s"
            ),
            exception,
        )
        return False

    controller_unique_id: str = config[CONF_CONTROLLER_UNIQUE_ID]

    director_token_dict = await call_c4_api_retry(
        account.getDirectorBearerToken, controller_unique_id
    )

    director_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], director_session
    )

    controller_href = (await call_c4_api_retry(account.getAccountControllers))["href"]
    director_sw_version = await call_c4_api_retry(
        account.getControllerOSVersion, controller_href
    )

    _, model, mac_address = controller_unique_id.split("_", 3)
    director_model = model.upper()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller_unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
        manufacturer="Control4",
        name=controller_unique_id,
        model=director_model,
        sw_version=director_sw_version,
    )

    # Store all items found on controller for platforms to use
    try:
        all_items_raw = await director.getAllItemInfo()
    except (TimeoutError, client_exceptions.ClientError) as err:
        _LOGGER.error(
            "Timeout connecting to Control4 controller at %s",
            config[CONF_HOST],
        )
        raise ConfigEntryNotReady(
            f"Timeout connecting to Control4 controller at {config[CONF_HOST]}"
        ) from err

    director_all_items: list[dict[str, Any]] = json.loads(all_items_raw)

    # Check if OS version is 3 or higher to get UI configuration
    ui_configuration: dict[str, Any] | None = None
    if int(director_sw_version.split(".")[0]) >= 3:
        try:
            ui_config_raw = await director.getUiConfiguration()
        except (TimeoutError, client_exceptions.ClientError) as err:
            _LOGGER.error(
                "Timeout getting UI configuration from Control4 controller at %s",
                config[CONF_HOST],
            )
            raise ConfigEntryNotReady(
                f"Timeout getting UI configuration from Control4 controller at {config[CONF_HOST]}"
            ) from err

        ui_configuration = json.loads(ui_config_raw)

    # Load options from config entry
    scan_interval: int = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    entry.runtime_data = Control4RuntimeData(
        account=account,
        controller_unique_id=controller_unique_id,
        director=director,
        director_all_items=director_all_items,
        director_model=director_model,
        director_sw_version=director_sw_version,
        scan_interval=scan_interval,
        ui_configuration=ui_configuration,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Control4ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def get_items_of_category(
    hass: HomeAssistant, entry: Control4ConfigEntry, category: str
):
    """Return a list of all Control4 items with the specified category."""
    return [
        item
        for item in entry.runtime_data.director_all_items
        if "categories" in item and category in item["categories"]
    ]
