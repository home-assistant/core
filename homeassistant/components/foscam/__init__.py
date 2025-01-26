"""The foscam component."""

from libpyfoscam import FoscamCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

from .config_flow import DEFAULT_RTSP_PORT
from .const import CONF_RTSP_PORT, DOMAIN, LOGGER, SERVICE_PTZ, SERVICE_PTZ_PRESET
from .coordinator import FoscamCoordinator

PLATFORMS = [Platform.CAMERA, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up foscam from a config entry."""

    session = FoscamCamera(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        verbose=False,
    )
    coordinator = FoscamCoordinator(hass, session)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Migrate to correct unique IDs for switches
    await async_migrate_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.services.async_remove(domain=DOMAIN, service=SERVICE_PTZ)
            hass.services.async_remove(domain=DOMAIN, service=SERVICE_PTZ_PRESET)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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


async def async_migrate_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old entry."""

    @callback
    def _update_unique_id(
        entity_entry: RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if (
            entity_entry.domain == Platform.SWITCH
            and entity_entry.unique_id == "sleep_switch"
        ):
            entity_new_unique_id = f"{entity_entry.config_entry_id}_sleep_switch"
            return {"new_unique_id": entity_new_unique_id}

        return None

    # Migrate entities
    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)
