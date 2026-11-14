"""Services for the Fully Kiosk Browser integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator


class FullyKioskService(StrEnum):
    """Store keys for Fully Kiosk Browser services."""

    LOAD_URL = "load_url"
    SET_CONFIG = "set_config"
    START_APPLICATION = "start_application"


class FullyKioskServiceArgument(StrEnum):
    """Store keys for Fully Kiosk Browser service arguments."""

    URL = "url"
    KEY = "key"
    VALUE = "value"
    APPLICATION = "application"


async def _collect_coordinators(
    call: ServiceCall,
) -> list[FullyKioskDataUpdateCoordinator]:
    device_ids: list[str] = call.data[CommonServiceArgument.DEVICE_ID]
    return [
        service.async_get_device_and_config_entry(call.hass, DOMAIN, device_id)[
            1
        ].runtime_data
        for device_id in device_ids
    ]


async def _async_load_url(call: ServiceCall) -> None:
    """Load a URL on the Fully Kiosk Browser."""
    for coordinator in await _collect_coordinators(call):
        await coordinator.fully.loadUrl(call.data[FullyKioskServiceArgument.URL])


async def _async_start_app(call: ServiceCall) -> None:
    """Start an app on the device."""
    for coordinator in await _collect_coordinators(call):
        await coordinator.fully.startApplication(
            call.data[FullyKioskServiceArgument.APPLICATION]
        )


async def _async_set_config(call: ServiceCall) -> None:
    """Set a Fully Kiosk Browser config value on the device."""
    for coordinator in await _collect_coordinators(call):
        key = call.data[FullyKioskServiceArgument.KEY]
        value = call.data[FullyKioskServiceArgument.VALUE]

        # Fully API has different methods for setting string and bool values.
        # check if call.data[FullyKioskServiceArgument.VALUE] is a bool
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
        (_async_load_url, FullyKioskService.LOAD_URL, FullyKioskServiceArgument.URL),
        (
            _async_start_app,
            FullyKioskService.START_APPLICATION,
            FullyKioskServiceArgument.APPLICATION,
        ),
    ]
    for service_handler, service_name, attrib in service_mapping:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
            schema=probatio.Schema(
                probatio.All(
                    {
                        probatio.Required(
                            CommonServiceArgument.DEVICE_ID
                        ): probatio.EnsureList(),
                        probatio.Required(attrib): cv.string,
                    }
                )
            ),
        )

    hass.services.async_register(
        DOMAIN,
        FullyKioskService.SET_CONFIG,
        _async_set_config,
        schema=probatio.Schema(
            probatio.All(
                {
                    probatio.Required(
                        CommonServiceArgument.DEVICE_ID
                    ): probatio.EnsureList(),
                    probatio.Required(FullyKioskServiceArgument.KEY): cv.string,
                    probatio.Required(FullyKioskServiceArgument.VALUE): probatio.Any(
                        str, bool, int
                    ),
                }
            )
        ),
    )
