"""Util functions for OneDrive."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.instance_id import async_get as async_get_instance_id


async def get_backup_folder_name(hass: HomeAssistant) -> str:
    """Return the backup folder name."""
    instance_id = await async_get_instance_id(hass)
    return f"backups_{instance_id[:8]}"
