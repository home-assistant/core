"""Services for the Fully Kiosk Browser integration."""

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

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


async def _collect_coordinators(
    call: ServiceCall,
) -> list[FullyKioskDataUpdateCoordinator]:
    device_ids: list[str] = call.data[ATTR_DEVICE_ID]
    return [
        service.async_get_device_and_config_entry(call.hass, DOMAIN, device_id)[
            1
        ].runtime_data
        for device_id in device_ids
    ]


async def _async_load_url(call: ServiceCall) -> None:
    """Load a URL on the Fully Kiosk Browser."""
    for coordinator in await _collect_coordinators(call):
        await coordinator.fully.loadUrl(call.data[ATTR_URL])


async def _async_start_app(call: ServiceCall) -> None:
    """Start an app on the device."""
    for coordinator in await _collect_coordinators(call):
        await coordinator.fully.startApplication(call.data[ATTR_APPLICATION])


async def _async_set_config(call: ServiceCall) -> None:
    """Set a Fully Kiosk Browser config value on the device."""
    for coordinator in await _collect_coordinators(call):
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Fully Kiosk Browser integration."""

    # Register all the above services
    service_mapping = [
        (_async_load_url, SERVICE_LOAD_URL, ATTR_URL),
        (_async_start_app, SERVICE_START_APPLICATION, ATTR_APPLICATION),
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
        _async_set_config,
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
