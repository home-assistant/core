"""The Tami4Edge integration."""

from __future__ import annotations

from Tami4EdgeAPI import Tami4EdgeAPI, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, selector

from .const import API, CONF_REFRESH_TOKEN, COORDINATOR, DOMAIN
from .coordinator import Tami4EdgeCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

ENTRY_DATA_FIELD = "entry_id"
DRINKS_DATA_FIELD = "drinks"
API_DATA_FIELD = "api"
DRINK_ID_SERVICE_FIELD = "drink_id"
GET_DRINKS_SERVICE_NAME = "get_drinks"
PREPARE_DRINK_SERVICE_NAME = "prepare_drink"

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ENTRY_DATA_FIELD): selector.ConfigEntrySelector(),
    }
)
PREPARE_DRINK_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(DRINK_ID_SERVICE_FIELD): cv.string})
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tami4 from a config entry."""
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    try:
        api = await hass.async_add_executor_job(Tami4EdgeAPI, refresh_token)
    except exceptions.RefreshTokenExpiredException as ex:
        raise ConfigEntryError("API Refresh token expired") from ex
    except exceptions.TokenRefreshFailedException as ex:
        raise ConfigEntryNotReady("Error connecting to API") from ex

    coordinator = Tami4EdgeCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        API: api,
        COORDINATOR: coordinator,
    }

    setup_hass_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def setup_hass_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    def get_drinks(call: ServiceCall) -> ServiceResponse:
        device = hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]][
            API_DATA_FIELD
        ].get_device()
        hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]][DRINKS_DATA_FIELD] = {
            drink.id: drink for drink in device.drinks
        }
        return {
            "drinks": [
                {"id": drink.id, "name": drink.name, "settings": drink.settings}
                for drink in device.drinks
            ],
        }

    def prepare_drink(call: ServiceCall) -> None:
        if (
            DRINKS_DATA_FIELD not in hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]]
            or call.data[DRINK_ID_SERVICE_FIELD]
            not in hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]][DRINKS_DATA_FIELD]
        ):
            get_drinks(call)
        try:
            hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]][
                API_DATA_FIELD
            ].prepare_drink(
                hass.data[DOMAIN][call.data[ENTRY_DATA_FIELD]][DRINKS_DATA_FIELD][
                    call.data[DRINK_ID_SERVICE_FIELD]
                ]
            )
        except KeyError as ex:
            raise ConfigEntryError("Drink id doesn't exist") from ex

    hass.services.async_register(
        DOMAIN,
        GET_DRINKS_SERVICE_NAME,
        get_drinks,
        schema=SERVICE_BASE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, PREPARE_DRINK_SERVICE_NAME, prepare_drink, schema=PREPARE_DRINK_SCHEMA
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
