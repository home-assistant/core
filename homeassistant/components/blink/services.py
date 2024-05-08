"""Services for the Blink integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_REFRESH, SERVICE_SEND_PIN
from .coordinator import BlinkUpdateCoordinator

SERVICE_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    def collect_coordinators(
        device_ids: list[str],
    ) -> list[BlinkUpdateCoordinator]:
        config_entries: list[ConfigEntry] = []
        registry = dr.async_get(hass)
        for target in device_ids:
            device = registry.async_get(target)
            if device:
                device_entries: list[ConfigEntry] = []
                for entry_id in device.config_entries:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry and entry.domain == DOMAIN:
                        device_entries.append(entry)
                if not device_entries:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_device",
                        translation_placeholders={"target": target, "domain": DOMAIN},
                    )
                config_entries.extend(device_entries)
            else:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="device_not_found",
                    translation_placeholders={"target": target},
                )

        coordinators: list[BlinkUpdateCoordinator] = []
        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_loaded",
                    translation_placeholders={"target": config_entry.title},
                )

            coordinators.append(hass.data[DOMAIN][config_entry.entry_id])
        return coordinators

    async def send_pin(call: ServiceCall):
        """Call blink to send new pin."""
        for entry_id in call.data[ATTR_CONFIG_ENTRY_ID]:
            if not (config_entry := hass.config_entries.async_get_entry(entry_id)):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="integration_not_found",
                    translation_placeholders={"target": DOMAIN},
                )
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_loaded",
                    translation_placeholders={"target": config_entry.title},
                )
            coordinator = hass.data[DOMAIN][entry_id]
            await coordinator.api.auth.send_auth_key(
                coordinator.api,
                call.data[CONF_PIN],
            )

    async def blink_refresh(call: ServiceCall):
        """Call blink to refresh info."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            "service_deprecation",
            breaks_in_ha_version="2024.7.0",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="service_deprecation",
        )

        for coordinator in collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.api.refresh(force_cache=True)

    # Register all the above services
    # Refresh service is deprecated and will be removed in 7/2024
    service_mapping = [
        (blink_refresh, SERVICE_REFRESH, SERVICE_UPDATE_SCHEMA),
        (send_pin, SERVICE_SEND_PIN, SERVICE_SEND_PIN_SCHEMA),
    ]

    for service_handler, service_name, schema in service_mapping:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
            schema=schema,
        )
