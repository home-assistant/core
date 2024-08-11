"""The seventeentrack component."""

from typing import Final

from pyseventeentrack import Client as SeventeenTrackClient
from pyseventeentrack.errors import SeventeenTrackError
from pyseventeentrack.package import PACKAGE_STATUS_MAP
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_LOCATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_STATE,
    ATTR_PACKAGE_TYPE,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    DOMAIN,
    SERVICE_GET_PACKAGES,
)
from .coordinator import SeventeenTrackCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the 17Track component."""

    async def get_packages(call: ServiceCall) -> ServiceResponse:
        """Get packages from 17Track."""
        config_entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        package_states = call.data.get(ATTR_PACKAGE_STATE, [])

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
                {
                    ATTR_DESTINATION_COUNTRY: package.destination_country,
                    ATTR_ORIGIN_COUNTRY: package.origin_country,
                    ATTR_PACKAGE_TYPE: package.package_type,
                    ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
                    ATTR_TRACKING_NUMBER: package.tracking_number,
                    ATTR_LOCATION: package.location,
                    ATTR_STATUS: package.status,
                    ATTR_TIMESTAMP: package.timestamp,
                    ATTR_INFO_TEXT: package.info_text,
                    ATTR_FRIENDLY_NAME: package.friendly_name,
                }
                for package in live_packages
                if slugify(package.status) in package_states or package_states == []
            ]
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        get_packages,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 17Track from a config entry."""

    session = async_get_clientsession(hass)
    client = SeventeenTrackClient(session=session)

    try:
        await client.profile.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except SeventeenTrackError as err:
        raise ConfigEntryNotReady from err

    seventeen_coordinator = SeventeenTrackCoordinator(hass, client)

    await seventeen_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = seventeen_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
