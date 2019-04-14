"""Support for PlayStation 4 consoles."""
import logging

from homeassistant.const import CONF_REGION
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

    reason = {1: "Region codes have changed"}  # From 0.89

    # Migrate Version 1 -> Version 2
    if version == 1:
        loc = await hass.async_add_executor_job(location.detect_location_info)
        if loc:
            country = loc.country_name
            if country in COUNTRIES:
                for device in data['devices']:
                    device[CONF_REGION] = country
                entry.version = 2
                config_entries.async_update_entry(entry, data=data)
                _LOGGER.info(
                    "PlayStation 4 Config Updated: \
                    Region changed to: %s", country)
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
