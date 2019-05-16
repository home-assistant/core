"""Support for PlayStation 4 consoles."""
import logging

from homeassistant.core import split_entity_id
from homeassistant.const import CONF_REGION, CONF_TOKEN
from homeassistant.helpers import entity_registry
from homeassistant.util import location

from .config_flow import PlayStation4FlowHandler  # noqa: pylint: disable=unused-import
from .const import DOMAIN  # noqa: pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the PS4 Component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up PS4 from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'media_player'))
    return True


async def async_unload_entry(hass, entry):
    """Unload a PS4 config entry."""
    await hass.config_entries.async_forward_entry_unload(
        entry, 'media_player')
    return True


async def async_migrate_entry(hass, entry):
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
                await hass.async_block_till_done()

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
