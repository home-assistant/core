"""The foscam component."""
import asyncio

from libpyfoscam import FoscamCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_migrate_entries

from .config_flow import DEFAULT_RTSP_PORT
from .const import CONF_RTSP_PORT, DOMAIN, LOGGER, SERVICE_PTZ, SERVICE_PTZ_PRESET

PLATFORMS = ["camera"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the foscam component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up foscam from a config entry."""
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    hass.data[DOMAIN][entry.entry_id] = entry.data

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.services.async_remove(domain=DOMAIN, service=SERVICE_PTZ)
            hass.services.async_remove(domain=DOMAIN, service=SERVICE_PTZ_PRESET)

    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Change unique id
        @callback
        def update_unique_id(entry):
            return {"new_unique_id": config_entry.entry_id}

        await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

        config_entry.unique_id = None

        # Get RTSP port from the camera or use the fallback one and store it in data
        camera = FoscamCamera(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            verbose=False,
        )

        ret, response = await hass.async_add_executor_job(camera.get_port_info)

        rtsp_port = DEFAULT_RTSP_PORT

        if ret != 0:
            rtsp_port = response.get("rtspPort") or response.get("mediaPort")

        config_entry.data = {**config_entry.data, CONF_RTSP_PORT: rtsp_port}

        # Change entry version
        config_entry.version = 2

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
