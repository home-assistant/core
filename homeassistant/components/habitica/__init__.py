"""The habitica integration."""

from uuid import UUID

from habiticalib import Habitica

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_API_USER, DOMAIN, X_CLIENT
from .coordinator import (
    HabiticaConfigEntry,
    HabiticaDataUpdateCoordinator,
    HabiticaPartyCoordinator,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
HABITICA_KEY: HassKey[dict[UUID, HabiticaPartyCoordinator]] = HassKey(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.IMAGE,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Habitica service."""

    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HabiticaConfigEntry
) -> bool:
    """Set up habitica from a config entry."""
    party_added_by_this_entry: UUID | None = None
    device_reg = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    session = async_get_clientsession(
        hass, verify_ssl=config_entry.data.get(CONF_VERIFY_SSL, True)
    )

    api = Habitica(
        session,
        api_user=config_entry.data[CONF_API_USER],
        api_key=config_entry.data[CONF_API_KEY],
        url=config_entry.data[CONF_URL],
        x_client=X_CLIENT,
    )

    coordinator = HabiticaDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    party = coordinator.data.user.party.id
    if HABITICA_KEY not in hass.data:
        hass.data[HABITICA_KEY] = {}

    if party is not None and party not in hass.data[HABITICA_KEY]:
        party_coordinator = HabiticaPartyCoordinator(hass, config_entry, api)
        await party_coordinator.async_config_entry_first_refresh()

        hass.data[HABITICA_KEY][party] = party_coordinator
        party_added_by_this_entry = party

    @callback
    def _party_update_listener() -> None:
        """On party change, unload coordinator, remove device and reload."""
        nonlocal party, party_added_by_this_entry
        party_updated = coordinator.data.user.party.id

        if (
            party is not None and (party not in hass.data[HABITICA_KEY])
        ) or party != party_updated:
            if party_added_by_this_entry:
                config_entry.async_create_task(
                    hass, shutdown_party_coordinator(hass, party_added_by_this_entry)
                )
                party_added_by_this_entry = None
            if party:
                identifier = {(DOMAIN, f"{config_entry.unique_id}_{party!s}")}
                if device := device_reg.async_get_device(identifiers=identifier):
                    device_reg.async_update_device(
                        device.id, remove_config_entry_id=config_entry.entry_id
                    )

                notify_entities = [
                    entry.entity_id
                    for entry in entity_registry.entities.values()
                    if entry.domain == NOTIFY_DOMAIN
                    and entry.config_entry_id == config_entry.entry_id
                ]
                for entity_id in notify_entities:
                    entity_registry.async_remove(entity_id)

            hass.config_entries.async_schedule_reload(config_entry.entry_id)

    coordinator.async_add_listener(_party_update_listener)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def shutdown_party_coordinator(hass: HomeAssistant, party_added: UUID) -> None:
    """Handle party coordinator shutdown."""
    await hass.data[HABITICA_KEY][party_added].async_shutdown()
    hass.data[HABITICA_KEY].pop(party_added)


async def async_unload_entry(hass: HomeAssistant, entry: HabiticaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
