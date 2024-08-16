"""The AWS Data integration."""

from __future__ import annotations

<<<<<<< HEAD
=======
from datetime import timedelta
from typing import Any

>>>>>>> 833ac3afab (Setup Coordinates)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

<<<<<<< HEAD
from .const import _LOGGER, DOMAIN, USER_INPUT_DATA, USER_INPUT_REGIONS

# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = []
=======
from .const import (
    CE_DEF_INTERVAL,
    CONST_COORD_EC2,
    EC2_DEF_INTERVAL,
    S3_DEF_INTERVAL,
    SERVICE_CE,
    SERVICE_EC2,
    SERVICE_S3,
    USER_INPUT_DATA,
    USER_INPUT_REGIONS,
    USER_INPUT_SERVICES,
)
from .coordinator import (
    AwsDataCEServicesCoordinator,
    AwsDataEC2ServicesCoordinator,
    AwsDataS3ServicesCoordinator,
)

# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = [Platform.SENSOR]
>>>>>>> 833ac3afab (Setup Coordinates)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AWS Data from a config entry."""

<<<<<<< HEAD
    _LOGGER.warning(
        "Setup: %s", entry.data[DOMAIN][USER_INPUT_DATA][USER_INPUT_REGIONS]
    )
=======
    user_data = dict(entry.data)
    selected_regions = user_data[USER_INPUT_DATA][USER_INPUT_REGIONS]
    services = user_data[USER_INPUT_DATA][USER_INPUT_SERVICES]

    store_coord: dict[str, Any] = {}
    if SERVICE_EC2 in services:
        store_coord[CONST_COORD_EC2] = ec2_coordinator = AwsDataEC2ServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(seconds=EC2_DEF_INTERVAL),
        )
        await ec2_coordinator.async_config_entry_first_refresh()

    if SERVICE_S3 in services:
        store_coord[SERVICE_S3] = s3_coordinator = AwsDataS3ServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(seconds=S3_DEF_INTERVAL),
        )
        await s3_coordinator.async_config_entry_first_refresh()

    if SERVICE_CE in services:
        store_coord[SERVICE_CE] = ce_coordinator = AwsDataCEServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(seconds=CE_DEF_INTERVAL),
        )
        await ce_coordinator.async_config_entry_first_refresh()
    # hass.config_entries.async_update_entry(entry=entry,data=user_data)
    entry.runtime_data = {"coord": store_coord}
>>>>>>> 833ac3afab (Setup Coordinates)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
<<<<<<< HEAD
=======

    entry.runtime_data = {}
>>>>>>> 833ac3afab (Setup Coordinates)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
