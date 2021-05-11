"""The qnap component."""
from datetime import timedelta
import logging

from qnapstats import QNAPStats

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS

UPDATE_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the qnap environment."""
    hass.data.setdefault(DOMAIN, {})

    # Import configuration from sensor platform
    config_platform = config_per_platform(config, "sensor")
    for p_type, p_config in config_platform:
        if p_type != DOMAIN:
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=p_config,
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""
    host = config_entry.data[CONF_HOST]
    protocol = "https" if config_entry.data.get(CONF_SSL) else "http"
    api = QNAPStats(
        host=f"{protocol}://{host}",
        port=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        verify_ssl=config_entry.data.get(CONF_VERIFY_SSL),
        timeout=DEFAULT_TIMEOUT,
    )

    async def async_update_data():
        datas = {}
        datas["system_stats"] = await hass.async_add_executor_job(api.get_system_stats)
        datas["system_health"] = await hass.async_add_executor_job(
            api.get_system_health
        )
        datas["smart_drive_health"] = await hass.async_add_executor_job(
            api.get_smart_disk_health
        )
        datas["volumes"] = await hass.async_add_executor_job(api.get_volumes)
        datas["bandwidth"] = await hass.async_add_executor_job(api.get_bandwidth)
        return datas

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
