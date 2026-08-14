"""The ENGIE Belgium integration."""

from dataclasses import dataclass

from aioengiebelgium import (
    BusinessAgreement,
    EngieBeAuthenticationError,
    EngieBeClient,
    EngieBeError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import EngieBePricesCoordinator, household_device_info

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type EngieBeConfigEntry = ConfigEntry[EngieBeRuntimeData]


@dataclass
class EngieBeRuntimeData:
    """Runtime data for the ENGIE Belgium integration."""

    coordinator: EngieBePricesCoordinator
    agreements: dict[str, BusinessAgreement]


async def async_setup_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Set up ENGIE Belgium from a config entry."""

    async def _persist_tokens(access_token: str, refresh_token: str) -> None:
        """Persist rotated tokens to the config entry."""
        if (
            entry.data[CONF_ACCESS_TOKEN] == access_token
            and entry.data[CONF_REFRESH_TOKEN] == refresh_token
        ):
            return
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = EngieBeClient(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        on_token_refresh=_persist_tokens,
    )

    try:
        relations = await client.async_get_customer_account_relations()
    except EngieBeAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except EngieBeError as err:
        raise ConfigEntryNotReady from err

    agreements = {
        agreement.business_agreement_number: agreement
        for account in relations.accounts
        for agreement in account.customer_account.business_agreements
        if agreement.active
    }
    if not agreements:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_active_agreements",
        )

    device_registry = dr.async_get(hass)
    for ban, agreement in agreements.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **household_device_info(ban, agreement),
        )

    coordinator = EngieBePricesCoordinator(hass, entry, client, list(agreements))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EngieBeRuntimeData(
        coordinator=coordinator,
        agreements=agreements,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
