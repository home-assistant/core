"""Services for the Fully Kiosk Browser integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_APPLICATION,
    ATTR_URL,
    DOMAIN,
    SERVICE_LOAD_URL,
    SERVICE_START_APPLICATION,
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Fully Kiosk Browser integration."""

    async def async_load_url(call: ServiceCall) -> None:
        """Load a URL on the Fully Kiosk Browser."""
        registry = dr.async_get(hass)
        for target in call.data[ATTR_DEVICE_ID]:

            device = registry.async_get(target)
            if device:
                coordinator = hass.data[DOMAIN][list(device.config_entries)[0]]
                await coordinator.fully.loadUrl(call.data[ATTR_URL])

    async def async_start_app(call: ServiceCall) -> None:
        """Start an app on the device."""
        registry = dr.async_get(hass)
        for target in call.data[ATTR_DEVICE_ID]:

            device = registry.async_get(target)
            if device:
                coordinator = hass.data[DOMAIN][list(device.config_entries)[0]]
                await coordinator.fully.startApplication(call.data[ATTR_APPLICATION])

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOAD_URL,
        async_load_url,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
                    vol.Required(
                        ATTR_URL,
                    ): cv.string,
                },
            )
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_APPLICATION,
        async_start_app,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
                    vol.Required(
                        ATTR_APPLICATION,
                    ): cv.string,
                },
            )
        ),
    )
