"""The qnap component."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from qnapstats import QNAPStats

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMPONENTS,
    CONF_DRIVES,
    CONF_NICS,
    CONF_VOLUMES,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

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
    if not config_entry.options:
        options = {
            CONF_VERIFY_SSL: config_entry.data.get(CONF_VERIFY_SSL, True),
            CONF_SSL: config_entry.data.get(CONF_SSL, False),
            CONF_TIMEOUT: config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_MONITORED_CONDITIONS: config_entry.data.get(CONF_MONITORED_CONDITIONS),
            CONF_NICS: cv.ensure_list_csv(config_entry.data.get(CONF_NICS)),
            CONF_DRIVES: cv.ensure_list_csv(config_entry.data.get(CONF_DRIVES)),
            CONF_VOLUMES: cv.ensure_list_csv(config_entry.data.get(CONF_VOLUMES)),
        }
        hass.config_entries.async_update_entry(config_entry, options=options)

    host = config_entry.data[CONF_HOST]
    protocol = "https" if config_entry.options.get(CONF_SSL) else "http"
    api = QNAPStats(
        host=f"{protocol}://{host}",
        port=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        verify_ssl=config_entry.options.get(CONF_VERIFY_SSL),
        timeout=config_entry.options.get(CONF_TIMEOUT),
    )
    try:
        system_info = await hass.async_add_executor_job(api.get_system_stats)
    except:  # noqa: E722 pylint: disable=bare-except
        _LOGGER.error("Failed to fetch QNAP stats from the NAS (%s)" % host)
        return False

    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
        manufacturer="Qnap",
        name=system_info.get("system", {}).get("name", host),
        model=system_info.get("system", {}).get("model"),
        sw_version=system_info.get("firmware", {}).get("version"),
    )

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                datas = {}
                datas["system_stats"] = await hass.async_add_executor_job(
                    api.get_system_stats
                )
                datas["system_health"] = await hass.async_add_executor_job(
                    api.get_system_health
                )
                datas["smart_drive_health"] = await hass.async_add_executor_job(
                    api.get_smart_disk_health
                )
                datas["volumes"] = await hass.async_add_executor_job(api.get_volumes)
                datas["bandwidth"] = await hass.async_add_executor_job(
                    api.get_bandwidth
                )
                return datas
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN] = coordinator

    for component in COMPONENTS:
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
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )
    return unload_ok
