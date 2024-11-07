"""The Mealie integration."""

from __future__ import annotations

from aiomealie import MealieAuthenticationError, MealieClient, MealieError

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, MIN_REQUIRED_MEALIE_VERSION
from .coordinator import (
    MealieConfigEntry,
    MealieData,
    MealieMealplanCoordinator,
    MealieShoppingListCoordinator,
    MealieStatisticsCoordinator,
)
from .services import setup_services
from .utils import create_version

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mealie component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Set up Mealie from a config entry."""
    client = MealieClient(
        entry.data[CONF_HOST],
        token=entry.data[CONF_API_TOKEN],
        session=async_get_clientsession(
            hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True)
        ),
    )
    try:
        await client.define_household_support()
        about = await client.get_about()
        version = create_version(about.version)
    except MealieAuthenticationError as error:
        raise ConfigEntryAuthFailed from error
    except MealieError as error:
        raise ConfigEntryNotReady(error) from error

    if not version.valid:
        LOGGER.warning(
            "It seems like you are using the nightly version of Mealie, nightly"
            " versions could have changes that stop this integration working"
        )
    if version.valid and version < MIN_REQUIRED_MEALIE_VERSION:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="version_error",
            translation_placeholders={
                "mealie_version": about.version,
                "min_version": MIN_REQUIRED_MEALIE_VERSION,
            },
        )

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        entry_type=DeviceEntryType.SERVICE,
        sw_version=about.version,
    )

    mealplan_coordinator = MealieMealplanCoordinator(hass, client)
    shoppinglist_coordinator = MealieShoppingListCoordinator(hass, client)
    statistics_coordinator = MealieStatisticsCoordinator(hass, client)

    await mealplan_coordinator.async_config_entry_first_refresh()
    await shoppinglist_coordinator.async_config_entry_first_refresh()
    await statistics_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MealieData(
        client, mealplan_coordinator, shoppinglist_coordinator, statistics_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
