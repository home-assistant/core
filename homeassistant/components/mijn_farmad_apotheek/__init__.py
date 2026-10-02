"""The Mijn Farmad Apotheek integration."""

from dataclasses import dataclass

from aiofarmad import FarmadClient, FarmadError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .services import async_setup_service_schemas, async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class FarmadData:
    """Runtime data of the Mijn Farmad Apotheek integration.

    The pharmacies hold the options of the pharmacy fields of the
    actions and the products the options of the product field, with the
    CNK code as value and the product name as label.
    """

    client: FarmadClient
    pharmacies: list[dict[str, str]]
    products: dict[str, str]


type FarmadConfigEntry = ConfigEntry[FarmadData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mijn Farmad Apotheek integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FarmadConfigEntry) -> bool:
    """Set up Mijn Farmad Apotheek from a config entry."""

    async def persist_tokens(access_token: str, refresh_token: str | None) -> None:
        """Store a rotated token pair in the config entry."""
        data = {**entry.data, CONF_ACCESS_TOKEN: access_token}
        if refresh_token is not None:
            data[CONF_REFRESH_TOKEN] = refresh_token
        hass.config_entries.async_update_entry(entry, data=data)

    client = FarmadClient(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        on_token_refresh=persist_tokens,
    )
    try:
        account = await client.async_get_account()
        pharmacies: list[dict[str, str]] = []
        products: dict[str, str] = {}
        for apb in account.entitled_pharmacies:
            organization = await client.async_get_organization(apb)
            pharmacies.append(
                {"value": apb, "label": f"{organization.name} ({organization.city})"}
            )
            for basket in await client.async_get_baskets(apb):
                for line in basket.items:
                    products.setdefault(line.cnk, line.description_nl)
        entry.runtime_data = FarmadData(
            client=client, pharmacies=pharmacies, products=products
        )
        async_setup_service_schemas(hass, entry.runtime_data)
    except FarmadError as err:
        await client.async_close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FarmadConfigEntry) -> bool:
    """Unload a Mijn Farmad Apotheek config entry."""
    await entry.runtime_data.client.async_close()
    return True
