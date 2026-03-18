"""The SunSynk integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLANT_IGNORE_LIST,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SunSynkAuthError,
)
from .data_fetcher import ErrorTracker, TokenManager, async_fetch_all_data

_LOGGER = logging.getLogger(__name__)

# Number of consecutive failures before creating a repair issue
CONSECUTIVE_FAILURE_THRESHOLD = 3

ISSUE_API_FAILURE = "persistent_api_failure"

type SunSynkCoordinator = DataUpdateCoordinator[dict[str, Any]]


@dataclass
class SunSynkRuntimeData:
    """Runtime data for the SunSynk integration."""

    coordinator: SunSynkCoordinator
    token_manager: TokenManager


type SunSynkConfigEntry = ConfigEntry[SunSynkRuntimeData]

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SunSynkConfigEntry) -> bool:
    """Set up SunSynk from a config entry."""
    region_idx: int = entry.data[CONF_REGION]
    email: str = entry.data[CONF_EMAIL]
    password: str = entry.data[CONF_PASSWORD]

    httpx_client = get_async_client(hass)
    token_manager = TokenManager(email, password, region_idx, httpx_client)
    error_tracker = ErrorTracker()

    ignore_raw = entry.options.get(CONF_PLANT_IGNORE_LIST, "")
    plant_ignore_list = {s.strip() for s in str(ignore_raw).split(",") if s.strip()}

    consecutive_failures = 0

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from SunSynk."""
        nonlocal consecutive_failures
        try:
            data = await async_fetch_all_data(
                token_manager,
                region_idx,
                error_tracker,
                plant_ignore_list,
                async_client=httpx_client,
            )
        except SunSynkAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except Exception as err:
            consecutive_failures += 1
            if consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    ISSUE_API_FAILURE,
                    is_fixable=False,
                    is_persistent=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="persistent_api_failure",
                    translation_placeholders={
                        "error": str(err),
                        "count": str(consecutive_failures),
                    },
                )
            raise UpdateFailed(f"Error communicating with SunSynk: {err}") from err

        # Success — reset counter and clear any repair issue
        if consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
            ir.async_delete_issue(hass, DOMAIN, ISSUE_API_FAILURE)
        consecutive_failures = 0

        _async_remove_stale_devices(hass, entry, data)

        return data

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    coordinator: SunSynkCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SunSynkRuntimeData(
        coordinator=coordinator,
        token_manager=token_manager,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
    data: dict[str, Any],
) -> None:
    """Remove devices that are no longer present in the API response."""
    device_reg = dr.async_get(hass)

    # Build set of current device identifiers from fetched data
    current_identifiers: set[tuple[str, str]] = set()

    for plant_id, plant_data in data.get("plants", {}).items():
        current_identifiers.add((DOMAIN, f"plant_{plant_id}"))
        for sn in plant_data.get("inverters", {}):
            current_identifiers.add((DOMAIN, f"inverter_{sn}"))

    for gw in data.get("gateways", []):
        gw_sn = getattr(gw, "sn", None)
        if gw_sn:
            current_identifiers.add((DOMAIN, f"gateway_{gw_sn}"))

    # Remove devices registered to this config entry that are no longer in the API
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN and identifier not in current_identifiers:
                _LOGGER.info("Removing stale device: %s (%s)", device.name, identifier)
                device_reg.async_remove_device(device.id)
                break


async def _async_update_listener(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
) -> None:
    """Handle options update - reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SunSynkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
