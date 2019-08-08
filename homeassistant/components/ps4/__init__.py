"""Support for PlayStation 4 consoles."""
import logging
import os

import voluptuous as vol
from pyps4_homeassistant.ddp import async_create_ddp_endpoint
from pyps4_homeassistant.media_art import COUNTRIES

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_GAME,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    ATTR_LOCKED,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry, config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import location
from homeassistant.util.json import load_json, save_json

from .config_flow import PlayStation4FlowHandler  # noqa: pylint: disable=unused-import
from .const import (
    ATTR_MEDIA_IMAGE_URL,
    COMMANDS,
    DEFAULT_URL,
    DOMAIN,
    GAMES_FILE,
    PS4_DATA,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_COMMAND = "send_command"
SERVICE_MEDIA_ADD = "media_add"
SERVICE_MEDIA_REMOVE = "media_remove"
SERVICE_MEDIA_EDIT = "media_edit"
SERVICE_MEDIA_EDIT_PLAYING = "media_edit_playing"
SERVICE_MEDIA_UNLOCK = "media_unlock"
SERVICE_MEDIA_UNLOCK_PLAYING = "media_unlock_playing"

PS4_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_COMMAND): vol.In(list(COMMANDS)),
    }
)

PS4_MEDIA_ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
        vol.Required(ATTR_MEDIA_TITLE): str,
        vol.Optional(ATTR_MEDIA_IMAGE_URL, default=""): vol.Any(cv.url, str),
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
            [MEDIA_TYPE_GAME, MEDIA_TYPE_APP]
        ),
    }
)

PS4_MEDIA_REMOVE_SCHEMA = vol.Schema({vol.Required(ATTR_MEDIA_CONTENT_ID): str})

PS4_MEDIA_EDIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
        vol.Optional(ATTR_MEDIA_TITLE, default=""): str,
        vol.Optional(ATTR_MEDIA_IMAGE_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
            [MEDIA_TYPE_GAME, MEDIA_TYPE_APP]
        ),
    }
)

PS4_MEDIA_EDIT_PLAYING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_MEDIA_TITLE, default=""): str,
        vol.Optional(ATTR_MEDIA_IMAGE_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
            [MEDIA_TYPE_GAME, MEDIA_TYPE_APP]
        ),
    }
)

PS4_MEDIA_UNLOCK_SCHEMA = vol.Schema({vol.Required(ATTR_MEDIA_CONTENT_ID): str})

PS4_MEDIA_UNLOCK_PLAYING_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_id}
)


class PS4Data:
    """Init Data Class."""

    def __init__(self):
        """Init Class."""
        self.devices = []
        self.protocol = None


async def async_setup(hass, config):
    """Set up the PS4 Component."""
    hass.data[PS4_DATA] = PS4Data()

    transport, protocol = await async_create_ddp_endpoint()
    hass.data[PS4_DATA].protocol = protocol
    _LOGGER.debug("PS4 DDP endpoint created: %s, %s", transport, protocol)
    service_handle(hass)
    return True


async def async_setup_entry(hass, config_entry):
    """Set up PS4 from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "media_player")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a PS4 config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "media_player")
    return True


async def async_migrate_entry(hass, entry):
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
        loc = await location.async_detect_location_info(
            hass.helpers.aiohttp_client.async_get_clientsession()
        )
        if loc:
            country = loc.country_name
            if country in COUNTRIES:
                for device in data["devices"]:
                    device[CONF_REGION] = country
                version = entry.version = 2
                config_entries.async_update_entry(entry, data=data)
                _LOGGER.info(
                    "PlayStation 4 Config Updated: \
                    Region changed to: %s",
                    country,
                )

    # Migrate Version 2 -> Version 3: Update identifier format.
    if version == 2:
        # Prevent changing entity_id. Updates entity registry.
        registry = await entity_registry.async_get_registry(hass)

        for entity_id, e_entry in registry.entities.items():
            if e_entry.config_entry_id == entry.entry_id:
                unique_id = e_entry.unique_id

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
                    config_entry_id=e_entry.config_entry_id,
                    device_id=e_entry.device_id,
                )
                entry.version = 3
                _LOGGER.info(
                    "PlayStation 4 identifier for entity: %s \
                    has changed",
                    entity_id,
                )
                config_entries.async_update_entry(entry)
                return True

    msg = """{} for the PlayStation 4 Integration.
            Please remove the PS4 Integration and re-configure
            [here](/config/integrations).""".format(
        reason[version]
    )

    hass.components.persistent_notification.async_create(
        title="PlayStation 4 Integration Configuration Requires Update",
        message=msg,
        notification_id="config_entry_migration",
    )
    return False


def format_unique_id(creds, mac_address):
    """Use last 4 Chars of credential as suffix. Unique ID per PSN user."""
    suffix = creds[-4:]
    return "{}_{}".format(mac_address, suffix)


def load_games(hass: HomeAssistantType) -> dict:
    """Load games for sources."""
    g_file = hass.config.path(GAMES_FILE)
    try:
        games = load_json(g_file, dict)
    except HomeAssistantError as error:
        games = {}
        _LOGGER.error("Failed to load games file: %s", error)

    if not isinstance(games, dict):
        _LOGGER.error("Games file was not parsed correctly")
        games = {}

    # If file does not exist, create empty file.
    if not os.path.isfile(g_file):
        _LOGGER.info("Creating PS4 Games File")
        games = {}
        save_games(hass, games)
    else:
        games = _reformat_data(hass, games)
    return games


def save_games(hass: HomeAssistantType, games: dict):
    """Save games to file."""
    g_file = hass.config.path(GAMES_FILE)
    try:
        save_json(g_file, games)
    except OSError as error:
        _LOGGER.error("Could not save game list, %s", error)


def _reformat_data(hass: HomeAssistantType, games: dict) -> dict:
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
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
            }
            data_reformatted = True

            _LOGGER.debug("Reformatting media data for item: %s, %s", game, data)

    if data_reformatted:
        save_games(hass, games)
    return games


def service_handle(hass: HomeAssistantType):
    """Handle for services."""

    async def async_service_command(call):
        """Service for sending commands."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        command = call.data[ATTR_COMMAND]
        for device in hass.data[PS4_DATA].devices:
            if device.entity_id in entity_ids:
                await device.async_send_command(command)

    async def async_service_media_unlock(call):
        """Service to unlock media data."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        data = games.get(media_content_id)
        if data is not None:
            data[ATTR_LOCKED] = False
            games[media_content_id] = data
            _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])
            _LOGGER.debug("Edited data %s", games[media_content_id])
            save_games(hass, games)
            _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])
            refresh_entity_media(hass, media_content_id)
        else:
            raise HomeAssistantError(
                "Media ID: {} is not in source list".format(media_content_id)
            )

    async def async_service_media_unlock_playing(call):
        """Service to unlock media data that entity is playing."""
        games = load_games(hass)
        media_content_id = None
        entity_id = call.data[ATTR_ENTITY_ID]
        for device in hass.data[PS4_DATA].devices:
            if device.entity_id == entity_id:
                entity = device
                media_id = entity.media_content_id
                if media_id is not None:
                    media_content_id = media_id

        if media_content_id is not None:
            data = games.get(media_content_id)
            if data is not None:
                data[ATTR_LOCKED] = False
                games[media_content_id] = data
                save_games(hass, games)
                _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])
                refresh_entity_media(hass, media_content_id)
            else:
                raise HomeAssistantError(
                    "Media ID: {} is not in source list".format(media_content_id)
                )
        else:
            raise HomeAssistantError(
                "Entity: {} has no current media data".format(entity_id)
            )

    async def async_service_media_add(call):
        """Add media data manually."""
        games = load_games(hass)

        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        media_title = call.data[ATTR_MEDIA_TITLE]

        media_url = (
            None
            if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL
            else call.data[ATTR_MEDIA_IMAGE_URL]
        )

        media_type = (
            MEDIA_TYPE_GAME
            if call.data[ATTR_MEDIA_CONTENT_TYPE] == ""
            else call.data[ATTR_MEDIA_CONTENT_TYPE]
        )

        _set_media(hass, games, media_content_id, media_title, media_url, media_type)

    async def async_service_media_remove(call):
        """Remove media data manually."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]

        if media_content_id in games:
            games.pop(media_content_id)
            save_games(hass, games)
            _LOGGER.debug("Removed media from source list: %s", media_content_id)

    async def async_service_media_edit(call):
        """Service call for editing existing media data."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        data = games.get(media_content_id)

        if data is not None:
            media_title = (
                None
                if call.data[ATTR_MEDIA_TITLE] == ""
                else call.data[ATTR_MEDIA_TITLE]
            )

            media_url = (
                None
                if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL
                else call.data[ATTR_MEDIA_IMAGE_URL]
            )

            media_type = (
                MEDIA_TYPE_GAME
                if call.data[ATTR_MEDIA_CONTENT_TYPE] == ""
                else call.data[ATTR_MEDIA_CONTENT_TYPE]
            )

            if media_title is None:
                stored_title = data.get(ATTR_MEDIA_TITLE)
                if stored_title is not None:
                    media_title = stored_title

            if media_url is None:
                stored_url = data.get(ATTR_MEDIA_IMAGE_URL)
                if stored_url is not None:
                    media_url = stored_url

            if media_type is None:
                stored_type = data.get(ATTR_MEDIA_CONTENT_TYPE)
                if stored_type is not None:
                    media_type = stored_type

            _set_media(
                hass, games, media_content_id, media_title, media_url, media_type
            )
            refresh_entity_media(hass, media_content_id)
        else:
            raise HomeAssistantError(
                "Media ID: {} is not in source list".format(media_content_id)
            )

    async def async_service_media_edit_playing(call):
        """Service for editing existing media data that entity is playing."""
        games = load_games(hass)
        media_content_id = None
        entity_id = call.data[ATTR_ENTITY_ID]
        for device in hass.data[PS4_DATA].devices:
            if device.entity_id == entity_id:
                entity = device
                media_id = entity.media_content_id
                if media_id is not None:
                    media_content_id = media_id

        if media_content_id is not None:
            data = games.get(media_content_id)
            if data is not None:

                media_title = (
                    None
                    if call.data[ATTR_MEDIA_TITLE] == ""
                    else call.data[ATTR_MEDIA_TITLE]
                )

                media_url = (
                    None
                    if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL
                    else call.data[ATTR_MEDIA_IMAGE_URL]
                )

                media_type = (
                    MEDIA_TYPE_GAME
                    if call.data[ATTR_MEDIA_CONTENT_TYPE] == ""
                    else call.data[ATTR_MEDIA_CONTENT_TYPE]
                )

                if media_title is None:
                    stored_title = data.get(ATTR_MEDIA_TITLE)
                    if stored_title is not None:
                        media_title = stored_title

                if media_url is None:
                    stored_url = data.get(ATTR_MEDIA_IMAGE_URL)
                    if stored_url is not None:
                        media_url = stored_url

                if media_type is None:
                    stored_type = data.get(ATTR_MEDIA_CONTENT_TYPE)
                    if stored_type is not None:
                        media_type = stored_type

                _set_media(
                    hass, games, media_content_id, media_title, media_url, media_type
                )
                refresh_entity_media(hass, media_content_id)

            else:
                raise HomeAssistantError(
                    "Media ID: {} is not in source list".format(media_content_id)
                )
        else:
            raise HomeAssistantError(
                "Entity: {} has no current media data".format(entity_id)
            )

    hass.services.async_register(
        DOMAIN, SERVICE_COMMAND, async_service_command, schema=PS4_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MEDIA_ADD, async_service_media_add, schema=PS4_MEDIA_ADD_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_REMOVE,
        async_service_media_remove,
        schema=PS4_MEDIA_REMOVE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_EDIT,
        async_service_media_edit,
        schema=PS4_MEDIA_EDIT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_EDIT_PLAYING,
        async_service_media_edit_playing,
        schema=PS4_MEDIA_EDIT_PLAYING_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_UNLOCK,
        async_service_media_unlock,
        schema=PS4_MEDIA_UNLOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_UNLOCK_PLAYING,
        async_service_media_unlock_playing,
        schema=PS4_MEDIA_UNLOCK_PLAYING_SCHEMA,
    )


def _set_media(
    hass: HomeAssistantType,
    games: dict,
    media_content_id,
    media_title,
    media_url,
    media_type,
):
    """Set media data."""
    if games.get(media_content_id) is not None:
        data = games[media_content_id]
    else:
        data = {}
        data[ATTR_MEDIA_CONTENT_ID] = media_content_id

    data[ATTR_LOCKED] = True
    data[ATTR_MEDIA_TITLE] = media_title
    data[ATTR_MEDIA_IMAGE_URL] = media_url
    data[ATTR_MEDIA_CONTENT_TYPE] = media_type
    games[media_content_id] = data
    save_games(hass, games)
    _LOGGER.debug("Setting media data, %s: %s", media_content_id, data)


def refresh_entity_media(hass: HomeAssistantType, media_content_id, update_entity=True):
    """Refresh media properties if data is changed.."""
    for device in hass.data[PS4_DATA].devices:
        if device.media_content_id == media_content_id:
            device.reset_title()
            if update_entity:
                device.schedule_update()
            _LOGGER.debug("Refreshing media data for: %s", device.entity_id)
