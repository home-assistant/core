"""Services for the seventeentrack integration."""

from typing import Any, Final

from pyseventeentrack.package import PACKAGE_STATUS_MAP, Package
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_LOCATION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.util import slugify

from . import SeventeenTrackCoordinator
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_STATE,
    ATTR_PACKAGE_TRACKING_NUMBER,
    ATTR_PACKAGE_TYPE,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    DOMAIN,
    SERVICE_ARCHIVE_PACKAGE,
    SERVICE_GET_PACKAGES,
)

SERVICE_GET_PACKAGES_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_PACKAGE_STATE): selector.SelectSelector(
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

SERVICE_ARCHIVE_PACKAGE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PACKAGE_TRACKING_NUMBER): cv.string,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the seventeentrack integration."""

    async def get_packages(call: ServiceCall) -> ServiceResponse:
        """Get packages from 17Track."""
        config_entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        package_states = call.data.get(ATTR_PACKAGE_STATE, [])

        await _validate_service(config_entry_id)

        seventeen_coordinator: SeventeenTrackCoordinator = hass.data[DOMAIN][
            config_entry_id
        ]
        live_packages = sorted(
            await seventeen_coordinator.client.profile.packages(
                show_archived=seventeen_coordinator.show_archived
            )
        )

        return {
            "packages": [
                package_to_dict(package)
                for package in live_packages
                if slugify(package.status) in package_states or package_states == []
            ]
        }

    async def archive_package(call: ServiceCall) -> None:
        config_entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        tracking_number = call.data[ATTR_PACKAGE_TRACKING_NUMBER]

        await _validate_service(config_entry_id)

        seventeen_coordinator: SeventeenTrackCoordinator = hass.data[DOMAIN][
            config_entry_id
        ]

        await seventeen_coordinator.client.profile.archive_package(tracking_number)

    def package_to_dict(package: Package) -> dict[str, Any]:
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

    async def _validate_service(config_entry_id):
        entry: ConfigEntry | None = hass.config_entries.async_get_entry(config_entry_id)
        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={
                    "config_entry_id": config_entry_id,
                },
            )
        if entry.state != ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unloaded_config_entry",
                translation_placeholders={
                    "config_entry_id": entry.title,
                },
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        get_packages,
        schema=SERVICE_GET_PACKAGES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ARCHIVE_PACKAGE,
        archive_package,
        schema=SERVICE_ARCHIVE_PACKAGE_SCHEMA,
    )
