"""Services for the seventeentrack integration."""

from json import JSONDecodeError
from typing import Any, Final

import probatio
from pyseventeentrack.errors import SeventeenTrackError
from pyseventeentrack.package import PACKAGE_STATUS_MAP, Package

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_FRIENDLY_NAME, ATTR_LOCATION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.util import slugify

from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_FRIENDLY_NAME,
    ATTR_PACKAGE_STATE,
    ATTR_PACKAGE_TRACKING_NUMBER,
    ATTR_PACKAGE_TYPE,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    DOMAIN,
    LOGGER,
    SERVICE_ADD_PACKAGE,
    SERVICE_ARCHIVE_PACKAGE,
    SERVICE_GET_PACKAGES,
)
from .coordinator import SeventeenTrackConfigEntry

ATTR_FIRST_CARRIER = "first_carrier"
ATTR_SECOND_CARRIER = "second_carrier"

CARRIER_CODE = probatio.All(
    probatio.Any(
        probatio.Check(lambda value: type(value) is int, "Expected an integer"),
        probatio.Match(r"[0-9]+\Z"),
        msg="Expected a carrier code",
    ),
    probatio.Coerce(int),
    probatio.Range(min=1),
)

SERVICE_GET_PACKAGES_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(ATTR_PACKAGE_STATE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True,
                options=[
                    value.lower().replace(" ", "_")
                    for value in PACKAGE_STATUS_MAP.values()
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=ATTR_PACKAGE_STATE,
            )
        ),
    }
)

SERVICE_ADD_PACKAGE_SCHEMA: Final = probatio.All(
    probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            probatio.Required(ATTR_PACKAGE_TRACKING_NUMBER): cv.string,
            probatio.Required(ATTR_PACKAGE_FRIENDLY_NAME): cv.string,
            probatio.Optional(ATTR_FIRST_CARRIER): CARRIER_CODE,
            probatio.Optional(ATTR_SECOND_CARRIER): CARRIER_CODE,
        }
    ),
    cv.key_dependency(ATTR_SECOND_CARRIER, ATTR_FIRST_CARRIER),
)

SERVICE_ARCHIVE_PACKAGE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(ATTR_PACKAGE_TRACKING_NUMBER): cv.string,
    }
)


async def _get_packages(call: ServiceCall) -> ServiceResponse:
    """Get packages from 17Track."""
    package_states = call.data.get(ATTR_PACKAGE_STATE, [])

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
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
    tracking_number = call.data[ATTR_PACKAGE_TRACKING_NUMBER]
    friendly_name = call.data[ATTR_PACKAGE_FRIENDLY_NAME]

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    seventeen_coordinator = entry.runtime_data

    try:
        await seventeen_coordinator.client.profile.add_package(
            tracking_number,
            friendly_name,
            first_carrier=call.data.get(ATTR_FIRST_CARRIER),
            second_carrier=call.data.get(ATTR_SECOND_CARRIER),
        )
    except (JSONDecodeError, SeventeenTrackError, TimeoutError) as err:
        LOGGER.debug("Failed to add package to 17TRACK", exc_info=True)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="add_package_failed",
        ) from err


async def _archive_package(call: ServiceCall) -> None:
    tracking_number = call.data[ATTR_PACKAGE_TRACKING_NUMBER]

    entry: SeventeenTrackConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
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
        ATTR_FRIENDLY_NAME: package.friendly_name,
    }
    if timestamp := package.timestamp:
        result[ATTR_TIMESTAMP] = timestamp.isoformat()
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the seventeentrack integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        _get_packages,
        schema=SERVICE_GET_PACKAGES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PACKAGE,
        _add_package,
        schema=SERVICE_ADD_PACKAGE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ARCHIVE_PACKAGE,
        _archive_package,
        schema=SERVICE_ARCHIVE_PACKAGE_SCHEMA,
    )
