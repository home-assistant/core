"""The qnap component."""
from datetime import timedelta
import logging

from qnapstats import QNAPStats
from requests.exceptions import ConnectTimeout

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_per_platform, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_NAME, DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS

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
    protocol = "https" if config_entry.options.get(CONF_SSL) else "http"
    api = QNAPStats(
        host=f"{protocol}://{host}",
        port=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        verify_ssl=config_entry.options.get(CONF_VERIFY_SSL),
        timeout=DEFAULT_TIMEOUT,
    )
    try:
        system_info = await hass.async_add_executor_job(api.get_system_stats)
    except ConnectTimeout as error:
        raise ConfigEntryNotReady from error

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
        manufacturer=DEFAULT_NAME,
        name=system_info["system"]["name"],
        model=system_info["system"]["model"],
        sw_version=system_info["firmware"]["version"],
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
    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    if not config_entry.update_listeners:
        config_entry.add_update_listener(async_update_options)

    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
