"""The FMD integration.

Home Assistant integration for FMD (Find My Device).
Built to work with the FMD-FOSS project: https://fmd-foss.org

FMD Project Attribution:
- Created by Nulide (http://nulide.de)
- Maintained by Thore (https://thore.io) and the FMD-FOSS team
- FMD Android: https://gitlab.com/fmd-foss/fmd-android
- FMD Server: https://gitlab.com/fmd-foss/fmd-server

This Integration:
- MIT License - Copyright (c) 2025 Devin Slick
- https://github.com/devinslick/home-assistant-fmd
- A third-party client for FMD servers
"""

from dataclasses import dataclass
import logging
from typing import Any

from fmd_api import AuthenticationError, FmdApiException, FmdClient, OperationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.TEXT,
]


@dataclass
class FmdRuntimeData:
    """Runtime data for an FMD config entry, stored in entry.runtime_data."""

    api: FmdClient
    device_info: DeviceInfo
    tracker: Any = None
    photo_count_sensor: Any = None
    photo_auto_cleanup_switch: Any = None
    wipe_safety_switch: Any = None
    max_photos_number: Any = None
    wipe_pin_text: Any = None
    lock_message_text: Any = None


type FmdConfigEntry = ConfigEntry[FmdRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Set up FMD from a config entry.

    Raises ConfigEntryNotReady if the device/service is unreachable during setup,
    allowing Home Assistant to retry with exponential backoff.
    """
    if "artifacts" not in entry.data and "password" not in entry.data:
        msg = "Config entry missing both artifacts and password"
        raise ValueError(msg)

    try:
        # Create API client instance from artifacts if available (password-free),
        # otherwise fall back to password-based auth (for migration)
        if "artifacts" in entry.data:
            # Modern artifact-based authentication (password-free)
            api = await FmdClient.from_auth_artifacts(entry.data["artifacts"])
        elif "password" in entry.data:
            # Legacy password-based auth (for migration)
            # Convert to artifacts on next reauth or update
            _LOGGER.info(
                "Using legacy password authentication for %s. "
                "Will migrate to secure artifacts on next authentication.",
                entry.data["id"],
            )
            api = await FmdClient.create(
                entry.data["url"],
                entry.data["id"],
                entry.data["password"],
                drop_password=True,
            )

            # Immediately export and save artifacts for next startup
            try:
                artifacts = await api.export_auth_artifacts()
                new_data = {**entry.data}
                new_data["artifacts"] = artifacts
                # Remove password from storage
                new_data.pop("password", None)
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.info(
                    "Successfully migrated %s to artifact-based authentication",
                    entry.data["id"],
                )
            except Exception as artifact_err:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not export artifacts for %s, will retry on next startup: %s",
                    entry.data["id"],
                    artifact_err,
                )
    except AuthenticationError as err:
        # Authentication failed - trigger reauth flow
        _LOGGER.error(
            "Authentication failed for %s: %s - Please reauthorize",
            entry.data.get("id", "unknown"),
            err,
        )
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

    except OperationError as err:
        # Temporary network/connection issue or API error - retry with backoff
        _LOGGER.warning(
            "Cannot connect to FMD server or API error at %s: %s - Will retry",
            entry.data.get("url", "unknown"),
            err,
        )
        raise ConfigEntryNotReady(f"FMD API error: {err}") from err

    except FmdApiException as err:
        # General FMD API error
        _LOGGER.error("FMD API error for %s: %s", entry.data.get("id", "unknown"), err)
        raise ConfigEntryNotReady(f"FMD API error: {err}") from err

    except Exception as err:
        # Unexpected error - log and raise ConfigEntryNotReady for retry
        _LOGGER.error(
            "Unexpected error setting up FMD for %s: %s",
            entry.data.get("id", "unknown"),
            err,
        )

        raise ConfigEntryNotReady(
            f"Failed to connect to FMD server at {entry.data.get('url', 'unknown')}: {err}"
        ) from err

    entry.runtime_data = FmdRuntimeData(
        api=api,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"FMD {entry.data['id']}",
            manufacturer="FMD",
            model="Device Tracker",
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up API client
        api = entry.runtime_data.api
        try:
            await api.close()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error closing FMD API client: %s", err)

    return unload_ok
