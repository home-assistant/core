"""Services for the seventeentrack integration."""

from enum import StrEnum
from typing import Any, Final

import probatio
from pyseventeentrack.package import PACKAGE_STATUS_MAP, Package

from homeassistant.const import ATTR_LOCATION, CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.util import slugify

from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_TYPE,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    DOMAIN,
)
from .coordinator import SeventeenTrackConfigEntry


class SeventeenTrackService(StrEnum):
    """Store keys for 17Track services."""

    GET_PACKAGES = "get_packages"
    ADD_PACKAGE = "add_package"
    ARCHIVE_PACKAGE = "archive_package"


class SeventeenTrackServiceArgument(StrEnum):
    """Store keys for 17Track service arguments."""

    PACKAGE_STATE = "package_state"
    PACKAGE_TRACKING_NUMBER = "package_tracking_number"
    PACKAGE_FRIENDLY_NAME = "package_friendly_name"


_ATTR_FRIENDLY_NAME = "friendly_name"

SERVICE_GET_PACKAGES_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(
            SeventeenTrackServiceArgument.PACKAGE_STATE
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True,
                options=[
                    value.lower().replace(" ", "_")
                    for value in PACKAGE_STATUS_MAP.values()
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="package_state",
            )
        ),
    }
)

SERVICE_ADD_PACKAGE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(
            SeventeenTrackServiceArgument.PACKAGE_TRACKING_NUMBER
        ): cv.string,
        probatio.Required(
            SeventeenTrackServiceArgument.PACKAGE_FRIENDLY_NAME
        ): cv.string,
    }
)

SERVICE_ARCHIVE_PACKAGE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(
            SeventeenTrackServiceArgument.PACKAGE_TRACKING_NUMBER
        ): cv.string,
    }
)


async def _get_packages(call: ServiceCall) -> ServiceResponse:
    """Get packages from 17Track."""
    package_states = call.data.get(SeventeenTrackServiceArgument.PACKAGE_STATE, [])

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    seventeen_coordinator = entry.runtime_data
    live_packages = sorted(
        await seventeen_coordinator.client.profile.packages(
            show_archived=seventeen_coordinator.show_archived
        )
    )

    return {
        "packages": [
            _package_to_dict(package)
            for package in live_packages
            if slugify(package.status) in package_states or package_states == []
        ]
    }


async def _add_package(call: ServiceCall) -> None:
    """Add a new package to 17Track."""
    tracking_number = call.data[SeventeenTrackServiceArgument.PACKAGE_TRACKING_NUMBER]
    friendly_name = call.data[SeventeenTrackServiceArgument.PACKAGE_FRIENDLY_NAME]

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    seventeen_coordinator = entry.runtime_data

    await seventeen_coordinator.client.profile.add_package(
        tracking_number, friendly_name
    )


async def _archive_package(call: ServiceCall) -> None:
    tracking_number = call.data[SeventeenTrackServiceArgument.PACKAGE_TRACKING_NUMBER]

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    seventeen_coordinator = entry.runtime_data

    await seventeen_coordinator.client.profile.archive_package(tracking_number)


def _package_to_dict(package: Package) -> dict[str, Any]:
    result = {
        ATTR_DESTINATION_COUNTRY: package.destination_country,
        ATTR_ORIGIN_COUNTRY: package.origin_country,
        ATTR_PACKAGE_TYPE: package.package_type,
        ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
        ATTR_TRACKING_NUMBER: package.tracking_number,
        ATTR_LOCATION: package.location,
        ATTR_STATUS: package.status,
        ATTR_INFO_TEXT: package.info_text,
        _ATTR_FRIENDLY_NAME: package.friendly_name,
    }
    if timestamp := package.timestamp:
        result[ATTR_TIMESTAMP] = timestamp.isoformat()
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the seventeentrack integration."""

    hass.services.async_register(
        DOMAIN,
        SeventeenTrackService.GET_PACKAGES,
        _get_packages,
        schema=SERVICE_GET_PACKAGES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SeventeenTrackService.ADD_PACKAGE,
        _add_package,
        schema=SERVICE_ADD_PACKAGE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SeventeenTrackService.ARCHIVE_PACKAGE,
        _archive_package,
        schema=SERVICE_ARCHIVE_PACKAGE_SCHEMA,
    )
