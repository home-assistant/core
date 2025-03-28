"""The foscam component."""

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_migrate_entries

from .config_flow import DEFAULT_RTSP_PORT
from .const import CONF_RTSP_PORT, LOGGER
from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .foscamcgi import FoscamCamera

PLATFORMS = [Platform.CAMERA, Platform.NOTIFY, Platform.NUMBER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Set up foscam from a config entry."""

    session = FoscamCamera(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        verbose=False,
    )
    coordinator = FoscamCoordinator(hass, entry, session)
    await hass.async_add_executor_job(session.set_sub_stream_format, 1)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Change unique id
        @callback
        def update_unique_id(entry):
            return {"new_unique_id": entry.entry_id}

        await async_migrate_entries(hass, entry.entry_id, update_unique_id)

        # Get RTSP port from the camera or use the fallback one and store it in data
        camera = FoscamCamera(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            verbose=False,
        )

        ret, response = await hass.async_add_executor_job(camera.get_port_info)

        rtsp_port = DEFAULT_RTSP_PORT

        if ret != 0:
            rtsp_port = response.get("rtspPort") or response.get("mediaPort")

        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_RTSP_PORT: rtsp_port},
            version=2,
            unique_id=None,
        )

    LOGGER.debug("Migration to version %s successful", entry.version)

    return True
