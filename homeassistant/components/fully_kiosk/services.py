"""Services for the Fully Kiosk Browser integration."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fullykiosk import FullyKiosk
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_APPLICATION,
    ATTR_URL,
    DOMAIN,
    LOGGER,
    SERVICE_LOAD_URL,
    SERVICE_START_APPLICATION,
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Fully Kiosk Browser integration."""

    async def execute_service(
        call: ServiceCall,
        fully_method: Callable,
        *args: list[str],
        **kwargs: dict[str, Any],
    ) -> None:
        """Execute a Fully service call.

        :param call: {ServiceCall} HA service call.
        :param fully_method: {Callable} A method of the FullyKiosk class.
        :param args: Arguments for fully_method.
        :param kwargs: Key-word arguments for fully_method.
        :return: None
        """
        LOGGER.debug(
            "Calling Fully service %s with args: %s, %s", ServiceCall, args, kwargs
        )
        registry = dr.async_get(hass)
        for target in call.data[ATTR_DEVICE_ID]:
            device = registry.async_get(target)
            if device:
                for key in device.config_entries:
                    entry = hass.config_entries.async_get_entry(key)
                    if not entry:
                        continue
                    if entry.domain != DOMAIN:
                        continue
                    coordinator = hass.data[DOMAIN][key]
                    # fully_method(coordinator.fully, *args, **kwargs) would make
                    # test_services.py fail.
                    await getattr(coordinator.fully, fully_method.__name__)(
                        *args, **kwargs
                    )
                    break

    async def async_load_url(call: ServiceCall) -> None:
        """Load a URL on the Fully Kiosk Browser."""
        await execute_service(call, FullyKiosk.loadUrl, call.data[ATTR_URL])

    async def async_start_app(call: ServiceCall) -> None:
        """Start an app on the device."""
        await execute_service(
            call, FullyKiosk.startApplication, call.data[ATTR_APPLICATION]
        )

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
