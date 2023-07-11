"""The Flux integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH]

# try to silence the hassfest pre-commit check that wants a platform schema
PLATFORM_SCHEMA: None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Give a warning about YAML configuration being old-school."""

    async_create_issue(
        hass,
        DOMAIN,
        "future_yaml_deprecation",
        is_fixable=False,
        is_persistent=True,
        learn_more_url="https://github.com/home-assistant/core/pull/94394#discussion_r1254831583",
        severity=IssueSeverity.WARNING,
        translation_key="future_yaml_deprecation",
    )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flux from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
