"""Services for the Fully Kiosk Browser integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_APPLICATION,
    ATTR_KEY,
    ATTR_URL,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_LOAD_URL,
    SERVICE_SET_CONFIG,
    SERVICE_START_APPLICATION,
)
from .coordinator import FullyKioskDataUpdateCoordinator


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Fully Kiosk Browser integration."""

    async def collect_coordinators(
        device_ids: list[str],
    ) -> list[FullyKioskDataUpdateCoordinator]:
        config_entries = list[ConfigEntry]()
        registry = dr.async_get(hass)
        for target in device_ids:
            device = registry.async_get(target)
            if device:
                device_entries = list[ConfigEntry]()
                for entry_id in device.config_entries:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry and entry.domain == DOMAIN:
                        device_entries.append(entry)
                if not device_entries:
                    raise HomeAssistantError(
                        f"Device '{target}' is not a {DOMAIN} device"
                    )
                config_entries.extend(device_entries)
            else:
                raise HomeAssistantError(
                    f"Device '{target}' not found in device registry"
                )
        coordinators = list[FullyKioskDataUpdateCoordinator]()
        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(f"{config_entry.title} is not loaded")
            coordinators.append(config_entry.runtime_data)
        return coordinators

    async def async_load_url(call: ServiceCall) -> None:
        """Load a URL on the Fully Kiosk Browser."""
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.fully.loadUrl(call.data[ATTR_URL])

    async def async_start_app(call: ServiceCall) -> None:
        """Start an app on the device."""
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.fully.startApplication(call.data[ATTR_APPLICATION])

    async def async_set_config(call: ServiceCall) -> None:
        """Set a Fully Kiosk Browser config value on the device."""
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            key = call.data[ATTR_KEY]
            value = call.data[ATTR_VALUE]

            # Fully API has different methods for setting string and bool values.
            # check if call.data[ATTR_VALUE] is a bool
            if isinstance(value, bool) or (
                isinstance(value, str) and value.lower() in ("true", "false")
            ):
                await coordinator.fully.setConfigurationBool(key, value)
            else:
                # Convert any int values to string
                if isinstance(value, int):
                    value = str(value)

                await coordinator.fully.setConfigurationString(key, value)

    # Register all the above services
    service_mapping = [
        (async_load_url, SERVICE_LOAD_URL, ATTR_URL),
        (async_start_app, SERVICE_START_APPLICATION, ATTR_APPLICATION),
    ]
    for service_handler, service_name, attrib in service_mapping:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
                        vol.Required(attrib): cv.string,
                    }
                )
            ),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONFIG,
        async_set_config,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
                    vol.Required(ATTR_KEY): cv.string,
                    vol.Required(ATTR_VALUE): vol.Any(str, bool, int),
                }
            )
        ),
    )
