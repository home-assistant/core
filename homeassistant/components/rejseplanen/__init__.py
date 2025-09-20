"""The rejseplanen component."""

from __future__ import annotations

import logging

from dbus_fast import AuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type RejseplanenConfigEntry = ConfigEntry[RejseplanenDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    _LOGGER.debug(
        "Setting up Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    coordinator: RejseplanenDataUpdateCoordinator | None = getattr(
        config_entry, "runtime_data", None
    )
    if coordinator is None:
        coordinator = RejseplanenDataUpdateCoordinator(
            hass,
            config_entry,
        )
        config_entry.runtime_data = coordinator
        # Test the connection/setup BEFORE forwarding to platforms
        try:
            await coordinator.async_config_entry_first_refresh()
        except (ConnectionError, TimeoutError, AuthError) as err:
            raise ConfigEntryNotReady(
                f"Unable to connect to Rejseplanen: {err}"
            ) from err

    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.SENSOR]
    )
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
        "Unloading Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> None:
    """Handle update."""
    _LOGGER.debug("Update listener triggered for entry: %s", config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Warn if Rejseplanen is configured via YAML sensor platform."""
    if "sensor" in config:
        for entry in config["sensor"]:
            if entry.get("platform") == DOMAIN:
                # Found a deprecated YAML config for Rejseplanen
                _LOGGER.warning(
                    "Configuration of Rejseplanen via configuration.yaml is deprecated and will be ignored"
                    " Please use the UI to configure the integration"
                )
                async_create_issue(
                    hass,
                    DOMAIN,
                    "rp_yaml_deprecated",
                    is_fixable=False,
                    is_persistent=True,
                    severity=IssueSeverity.WARNING,
                    translation_key="yaml_deprecated",
                )
                break
    return True
