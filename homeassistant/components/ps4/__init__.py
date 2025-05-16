"""Support for PlayStation 4 consoles."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import TYPE_CHECKING

from pyps4_2ndscreen.ddp import DDPProtocol, async_create_ddp_endpoint
from pyps4_2ndscreen.media_art import COUNTRIES

from homeassistant.components import persistent_notification
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LOCKED, CONF_REGION, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import location as location_util
from homeassistant.util.json import JsonObjectType, load_json_object

from .config_flow import PlayStation4FlowHandler  # noqa: F401
from .const import ATTR_MEDIA_IMAGE_URL, COUNTRYCODE_NAMES, DOMAIN, GAMES_FILE, PS4_DATA
from .services import register_services

if TYPE_CHECKING:
    from .media_player import PS4Device

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class PS4Data:
    """Init Data Class."""

    devices: list[PS4Device]
    protocol: DDPProtocol


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PS4 Component."""
    transport, protocol = await async_create_ddp_endpoint()
    hass.data[PS4_DATA] = PS4Data(
        devices=[],
        protocol=protocol,
    )
    _LOGGER.debug("PS4 DDP endpoint created: %s, %s", transport, protocol)
    register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PS4 from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a PS4 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    config_entries = hass.config_entries
    data = entry.data
    version = entry.version

    _LOGGER.debug("Migrating PS4 entry from Version %s", version)

    reason = {
        1: "Region codes have changed",
        2: "Format for Unique ID for entity registry has changed",
    }

    # Migrate Version 1 -> Version 2: New region codes.
    if version == 1:
        loc = await location_util.async_detect_location_info(
            async_get_clientsession(hass)
        )
        if loc:
            country = COUNTRYCODE_NAMES.get(loc.country_code)
            if country in COUNTRIES:
                for device in data["devices"]:
                    device[CONF_REGION] = country
                version = 2
                config_entries.async_update_entry(entry, data=data, version=2)
                _LOGGER.debug(
                    "PlayStation 4 Config Updated: Region changed to: %s",
                    country,
                )

    # Migrate Version 2 -> Version 3: Update identifier format.
    if version == 2:
        # Prevent changing entity_id. Updates entity registry.
        registry = er.async_get(hass)

        for e_entry in registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        ):
            unique_id = e_entry.unique_id
            entity_id = e_entry.entity_id

            # Remove old entity entry.
            registry.async_remove(entity_id)

            # Format old unique_id.
            unique_id = format_unique_id(entry.data[CONF_TOKEN], unique_id)

            # Create new entry with old entity_id.
            new_id = split_entity_id(entity_id)[1]
            registry.async_get_or_create(
                "media_player",
                DOMAIN,
                unique_id,
                suggested_object_id=new_id,
                config_entry=entry,
                device_id=e_entry.device_id,
            )
            _LOGGER.debug(
                "PlayStation 4 identifier for entity: %s has changed",
                entity_id,
            )
            config_entries.async_update_entry(entry, version=3)
            return True

    msg = f"""{reason[version]} for the PlayStation 4 Integration.
            Please remove the PS4 Integration and re-configure
            [here](/config/integrations)."""

    persistent_notification.async_create(
        hass,
        title="PlayStation 4 Integration Configuration Requires Update",
        message=msg,
        notification_id="config_entry_migration",
    )
    return False


def format_unique_id(creds, mac_address):
    """Use last 4 Chars of credential as suffix. Unique ID per PSN user."""
    suffix = creds[-4:]
    return f"{mac_address}_{suffix}"


def load_games(hass: HomeAssistant, unique_id: str) -> JsonObjectType:
    """Load games for sources."""
    g_file = hass.config.path(GAMES_FILE.format(unique_id))
    try:
        games = load_json_object(g_file)
    except HomeAssistantError as error:
        games = {}
        _LOGGER.error("Failed to load games file: %s", error)

    # If file exists
    if os.path.isfile(g_file):
        games = _reformat_data(hass, games, unique_id)
    return games


def save_games(hass: HomeAssistant, games: dict, unique_id: str):
    """Save games to file."""
    g_file = hass.config.path(GAMES_FILE.format(unique_id))
    try:
        save_json(g_file, games)
    except OSError as error:
        _LOGGER.error("Could not save game list, %s", error)


def _reformat_data(hass: HomeAssistant, games: dict, unique_id: str) -> dict:
    """Reformat data to correct format."""
    data_reformatted = False

    for game, data in games.items():
        # Convert str format to dict format.
        if not isinstance(data, dict):
            # Use existing title. Assign defaults.
            games[game] = {
                ATTR_LOCKED: False,
                ATTR_MEDIA_TITLE: data,
                ATTR_MEDIA_IMAGE_URL: None,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.GAME,
            }
            data_reformatted = True

            _LOGGER.debug("Reformatting media data for item: %s, %s", game, data)

    if data_reformatted:
        save_games(hass, games, unique_id)
    return games
