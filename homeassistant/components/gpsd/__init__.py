"""The GPSD integration."""

from __future__ import annotations

from gps3.agps3threaded import AGPS3mechanism

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GPSDConfigEntry = ConfigEntry[AGPS3mechanism]
DEPRECATED_ISSUE_ID = f"deprecated_system_packages_config_flow_integration_{DOMAIN}"


async def async_setup_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Set up GPSD from a config entry."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        DEPRECATED_ISSUE_ID,
        breaks_in_ha_version="2025.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_system_packages_config_flow_integration",
        translation_placeholders={
            "integration_title": "GPSD",
        },
    )

    agps_thread = AGPS3mechanism()
    entry.runtime_data = agps_thread

    def setup_agps() -> None:
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_PORT)
        agps_thread.stream_data(host, port)
        agps_thread.run_thread()

    await hass.async_add_executor_job(setup_agps)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        agps_thread = entry.runtime_data
        await hass.async_add_executor_job(
            lambda: agps_thread.stream_data(
                host=entry.data.get(CONF_HOST),
                port=entry.data.get(CONF_PORT),
                enable=False,
            )
        )

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        async_delete_issue(hass, HOMEASSISTANT_DOMAIN, DEPRECATED_ISSUE_ID)

    return unload_ok
