"""Support for a Genius Hub system."""

from geniushubclient import GeniusHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_MANUFACTURER, DOMAIN, IDENTIFIER_ZONE, SERIAL_NO
from .coordinator import GeniusCoordinator
from .services import async_setup_services

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)

type GeniusHubConfigEntry = ConfigEntry[GeniusCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # pylint: disable=unused-argument
    """Initialise GeniusHub."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GeniusHubConfigEntry) -> None:
    """Create a Genius Hub system."""
    if CONF_TOKEN in entry.data and CONF_MAC in entry.data:
        entity_registry = er.async_get(hass)
        registry_entries = er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        for reg_entry in registry_entries:
            if reg_entry.unique_id.startswith(entry.data[CONF_MAC]):
                entity_registry.async_update_entity(
                    reg_entry.entity_id,
                    new_unique_id=reg_entry.unique_id.replace(
                        entry.data[CONF_MAC], entry.entry_id
                    ),
                )

    session = async_get_clientsession(hass)
    if CONF_HOST in entry.data:
        api = "Local"
        client = GeniusHub(
            entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
    else:
        api = "Cloud"
        client = GeniusHub(entry.data[CONF_TOKEN], session=session)

    unique_id = entry.unique_id or entry.entry_id

    coordinator = entry.runtime_data = GeniusCoordinator(hass, client, entry, unique_id)

    await coordinator.async_config_entry_first_refresh()
    coordinator.make_debug_log_entries()

    _create_hub_devices(hass, entry, unique_id, api, coordinator.client.zone_by_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GeniusHubConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _create_hub_devices(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    hub_uid: str,
    api: str,
    zones: dict,
):
    device_registry = dr.async_get(hass)
    hub_identifiers = (DOMAIN, hub_uid)
    hub = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={hub_identifiers},
        name=hub_uid,
        manufacturer=ATTR_MANUFACTURER,
        model=f"{api} API",
    )
    for zone in zones.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, IDENTIFIER_ZONE.format(zone.id))},
            via_device_id=hub.id,
            name=zone.name,
            manufacturer=ATTR_MANUFACTURER,
            model=zone.name,
            serial_number=SERIAL_NO.format("Zone", zone.id),
        )
