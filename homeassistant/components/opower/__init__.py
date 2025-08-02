"""The Opower integration."""

from __future__ import annotations

from opower import select_utility

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_LOGIN_SERVICE_URL, CONF_UTILITY, DOMAIN
from .coordinator import OpowerConfigEntry, OpowerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Set up Opower from a config entry."""

    login_service_missing_issue_id = f"login_service_url_missing_{entry.entry_id}"
    if select_utility(
        entry.data[CONF_UTILITY]
    ).requires_headless_login_service() and not entry.options.get(
        CONF_LOGIN_SERVICE_URL
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            login_service_missing_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="login_service_url_missing",
            translation_placeholders={"utility_name": entry.data[CONF_UTILITY]},
        )
        return False
    ir.async_delete_issue(hass, DOMAIN, login_service_missing_issue_id)

    coordinator = OpowerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
