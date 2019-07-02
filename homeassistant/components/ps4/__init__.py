"""Support for PlayStation 4 consoles."""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, ATTR_LOCKED, CONF_REGION, CONF_TOKEN)
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry, config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_TITLE,
    MEDIA_TYPE_APP, MEDIA_TYPE_GAME)
from homeassistant.util import location
from homeassistant.util.json import load_json, save_json


from .config_flow import PlayStation4FlowHandler  # noqa: pylint: disable=unused-import
from .const import (
    ATTR_MEDIA_IMAGE_URL, COMMANDS, DEFAULT_URL, DOMAIN, GAMES_FILE, PS4_DATA)

_LOGGER = logging.getLogger(__name__)

SERVICE_COMMAND = 'send_command'
SERVICE_LOCK_MEDIA = 'lock_media'
SERVICE_LOCK_CURRENT_MEDIA = 'lock_current_media'
SERVICE_UNLOCK_MEDIA = 'unlock_media'
SERVICE_UNLOCK_CURRENT_MEDIA = 'unlock_current_media'
SERVICE_EDIT_MEDIA = 'edit_media'
SERVICE_EDIT_CURRENT_MEDIA = 'edit_current_media'
SERVICE_ADD_MEDIA = 'add_media'
SERVICE_REMOVE_MEDIA = 'remove_media'


PS4_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [COMMANDS])
})

PS4_LOCK_CURRENT_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id
})

PS4_UNLOCK_CURRENT_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id
})

PS4_LOCK_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_MEDIA_CONTENT_ID): str,
})

PS4_UNLOCK_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_MEDIA_CONTENT_ID): str,
})

PS4_EDIT_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_MEDIA_CONTENT_ID): str,
    vol.Optional(ATTR_MEDIA_TITLE, default=''): str,
    vol.Optional(ATTR_MEDIA_IMAGE_URL, default=DEFAULT_URL): cv.url,
    vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
        [MEDIA_TYPE_GAME, MEDIA_TYPE_APP])
})

PS4_EDIT_CURRENT_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_MEDIA_TITLE, default=''): str,
    vol.Optional(ATTR_MEDIA_IMAGE_URL, default=DEFAULT_URL): cv.url,
    vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
        [MEDIA_TYPE_GAME, MEDIA_TYPE_APP])
})

PS4_ADD_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_MEDIA_CONTENT_ID): str,
    vol.Required(ATTR_MEDIA_TITLE): str,
    vol.Optional(ATTR_MEDIA_IMAGE_URL, default=''): vol.Any(
        cv.url, str),
    vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default=MEDIA_TYPE_GAME): vol.In(
        [MEDIA_TYPE_GAME, MEDIA_TYPE_APP])
})

PS4_REMOVE_MEDIA_SCHEMA = vol.Schema({
    vol.Required(ATTR_MEDIA_CONTENT_ID): str,
})


class PS4Data():
    """Init Data Class."""

    def __init__(self):
        """Init Class."""
        self.devices = []
        self.protocol = None


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the PS4 Component."""
    from pyps4_homeassistant.ddp import async_create_ddp_endpoint

    hass.data[PS4_DATA] = PS4Data()

    # Create async transport/protocol to poll for status updates.
    transport, protocol = await async_create_ddp_endpoint()
    hass.data[PS4_DATA].protocol = protocol
    _LOGGER.debug("PS4 DDP endpoint created: %s, %s", transport, protocol)
    await async_service_handle(hass)
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry) -> bool:
    """Set up PS4 from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'media_player'))
    return True


async def async_unload_entry(hass: HomeAssistantType, entry) -> bool:
    """Unload a PS4 config entry."""
    await hass.config_entries.async_forward_entry_unload(
        entry, 'media_player')
    return True


async def async_migrate_entry(hass: HomeAssistantType, entry) -> bool:
    """Migrate old entry."""
    from pyps4_homeassistant.media_art import COUNTRIES

    config_entries = hass.config_entries
    data = entry.data
    version = entry.version

    _LOGGER.debug("Migrating PS4 entry from Version %s", version)

    reason = {
        1: "Region codes have changed",
        2: "Format for Unique ID for entity registry has changed"
    }

    # Migrate Version 1 -> Version 2: New region codes.
    if version == 1:
        loc = await location.async_detect_location_info(
            hass.helpers.aiohttp_client.async_get_clientsession()
        )
        if loc:
            country = loc.country_name
            if country in COUNTRIES:
                for device in data['devices']:
                    device[CONF_REGION] = country
                version = entry.version = 2
                config_entries.async_update_entry(entry, data=data)
                _LOGGER.info(
                    "PlayStation 4 Config Updated: \
                    Region changed to: %s", country)

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
                    'media_player', DOMAIN, unique_id,
                    suggested_object_id=new_id,
                    config_entry_id=e_entry.config_entry_id,
                    device_id=e_entry.device_id
                )
                entry.version = 3
                _LOGGER.info(
                    "PlayStation 4 identifier for entity: %s \
                    has changed", entity_id)
                config_entries.async_update_entry(entry)
                return True

    msg = """{} for the PlayStation 4 Integration.
            Please remove the PS4 Integration and re-configure
            [here](/config/integrations).""".format(reason[version])

    hass.components.persistent_notification.async_create(
        title="PlayStation 4 Integration Configuration Requires Update",
        message=msg,
        notification_id='config_entry_migration'
    )
    return False


def format_unique_id(creds, mac_address):
    """Use last 4 Chars of credential as suffix. Unique ID per PSN user."""
    suffix = creds[-4:]
    return "{}_{}".format(mac_address, suffix)


async def async_service_handle(hass: HomeAssistantType):
    """Handle for services."""
    async def async_service_command(call):
        """Service for sending commands."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        command = call.data[ATTR_COMMAND]
        for device in hass.data[PS4_DATA].devices:
            if device.entity_id in entity_ids:
                await device.async_send_command(command)

    async def async_service_lock_media(call):
        """Service to lock media data that entity is playing."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        data = games.get(media_content_id)
        if data is not None:
            data[ATTR_LOCKED] = True
            games[media_content_id] = data
            save_games(hass, games)
            _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])
        else:
            raise HomeAssistantError(
                "Media ID: {} is not in source list".format(
                    media_content_id))

    async def async_service_unlock_media(call):
        """Service to lock media data that entity is playing."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        data = games.get(media_content_id)
        if data is not None:
            data[ATTR_LOCKED] = False
            games[media_content_id] = data
            save_games(hass, games)
            _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])

            _refresh_entity_media(hass, media_content_id)
        else:
            raise HomeAssistantError(
                "Media ID: {} is not in source list".format(
                    media_content_id))

    async def async_service_lock_current_media(call):
        """Service to lock media data that entity is playing."""
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
                data[ATTR_LOCKED] = True
                games[media_content_id] = data
                save_games(hass, games)
                _LOGGER.debug("Setting Lock to %s", data[ATTR_LOCKED])
            else:
                raise HomeAssistantError(
                    "Media ID: {} is not in source list".format(
                        media_content_id))
        else:
            raise HomeAssistantError(
                "Entity: {} has no current media data".format(entity_id))

    async def async_service_unlock_current_media(call):
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
                _refresh_entity_media(hass, media_content_id)
            else:
                raise HomeAssistantError(
                    "Media ID: {} is not in source list".format(
                        media_content_id))
        else:
            raise HomeAssistantError(
                "Entity: {} has no current media data".format(entity_id))

    async def async_service_add_media(call):
        """Add media data manually."""
        games = load_games(hass)

        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        media_title = call.data[ATTR_MEDIA_TITLE]

        media_url = None if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL\
            else call.data[ATTR_MEDIA_IMAGE_URL]

        media_type = MEDIA_TYPE_GAME\
            if call.data[ATTR_MEDIA_CONTENT_TYPE] == ''\
            else call.data[ATTR_MEDIA_CONTENT_TYPE]

        _set_media(hass, games, media_content_id, media_title,
                   media_url, media_type)

    async def async_service_remove_media(call):
        """Remove media data manually."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]

        if media_content_id in games:
            games.pop(media_content_id)
            save_games(hass, games)
            _LOGGER.debug(
                "Removed media from source list: %s", media_content_id)

    async def async_service_edit_media(call):
        """Service call for editing existing media data."""
        games = load_games(hass)
        media_content_id = call.data[ATTR_MEDIA_CONTENT_ID]
        data = games.get(media_content_id)

        if data is not None:
            media_title = None if call.data[ATTR_MEDIA_TITLE] == ''\
                else call.data[ATTR_MEDIA_TITLE]

            media_url = None\
                if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL\
                else call.data[ATTR_MEDIA_IMAGE_URL]

            media_type = MEDIA_TYPE_GAME\
                if call.data[ATTR_MEDIA_CONTENT_TYPE] == ''\
                else call.data[ATTR_MEDIA_CONTENT_TYPE]

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

            _set_media(hass, games, media_content_id, media_title,
                       media_url, media_type)
            _refresh_entity_media(hass, media_content_id)
        else:
            raise HomeAssistantError(
                "Media ID: {} is not in source list".format(
                    media_content_id))

    async def async_service_edit_current_media(call):
        """Service call for editing existing media data."""
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

                media_title = None if call.data[ATTR_MEDIA_TITLE] == ''\
                    else call.data[ATTR_MEDIA_TITLE]

                media_url = None\
                    if call.data[ATTR_MEDIA_IMAGE_URL] == DEFAULT_URL\
                    else call.data[ATTR_MEDIA_IMAGE_URL]

                media_type = MEDIA_TYPE_GAME\
                    if call.data[ATTR_MEDIA_CONTENT_TYPE] == ''\
                    else call.data[ATTR_MEDIA_CONTENT_TYPE]

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

                _set_media(hass, games, media_content_id, media_title,
                           media_url, media_type)
                _refresh_entity_media(hass, media_content_id)

            else:
                raise HomeAssistantError(
                    "Media ID: {} is not in source list".format(
                        media_content_id))
        else:
            raise HomeAssistantError(
                "Entity: {} has no current media data".format(entity_id))

    hass.services.async_register(
        DOMAIN, SERVICE_COMMAND, async_service_command,
        schema=PS4_COMMAND_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_LOCK_MEDIA, async_service_lock_media,
        schema=PS4_LOCK_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_UNLOCK_MEDIA,
        async_service_unlock_media,
        schema=PS4_UNLOCK_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_LOCK_CURRENT_MEDIA,
        async_service_lock_current_media,
        schema=PS4_LOCK_CURRENT_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_UNLOCK_CURRENT_MEDIA,
        async_service_unlock_current_media,
        schema=PS4_UNLOCK_CURRENT_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_MEDIA, async_service_add_media,
        schema=PS4_ADD_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_MEDIA,
        async_service_remove_media,
        schema=PS4_REMOVE_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_EDIT_MEDIA, async_service_edit_media,
        schema=PS4_EDIT_MEDIA_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_EDIT_CURRENT_MEDIA, async_service_edit_current_media,
        schema=PS4_EDIT_CURRENT_MEDIA_SCHEMA)


def load_games(hass: HomeAssistantType) -> dict:
    """Load games for sources."""
    g_file = hass.config.path(GAMES_FILE)
    try:
        games = load_json(g_file)

    # If file does not exist, create empty file.
    except FileNotFoundError:
        games = {}
        save_games(hass, games)

    # Convert str format to dict format if not already.
    if games is not None:
        for game, data in games.items():
            if type(data) is not dict:
                games[game] = {ATTR_MEDIA_TITLE: data,
                               ATTR_MEDIA_IMAGE_URL: None,
                               ATTR_LOCKED: False,
                               ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME}
    return games


def save_games(hass: HomeAssistantType, games: dict):
    """Save games to file."""
    g_file = hass.config.path(GAMES_FILE)
    try:
        save_json(g_file, games)
    except OSError as error:
        _LOGGER.error("Could not save game list, %s", error)

    # Retry loading file
    if games is None:
        load_games()


def _set_media(hass: HomeAssistantType, games: dict, media_content_id,
               media_title, media_url, media_type):
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


def _refresh_entity_media(hass: HomeAssistantType, media_content_id):
    """Refresh media properties if data is changed.."""
    for device in hass.data[PS4_DATA].devices:
        if device.media_content_id == media_content_id:
            device.reset_title()
            device.schedule_update()
            _LOGGER.debug(
                "Refreshing media data for: %s", device.entity_id)
