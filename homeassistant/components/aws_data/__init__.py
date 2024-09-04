"""The AWS Data integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CE_DEF_INTERVAL,
    CONST_ACCOUNT,
    CONST_CE_SELECT,
    CONST_FILTER,
    CONST_INTERVAL,
    CONST_SECONDS,
    CONST_SERVICE_ID,
    CONST_SERVICE_NAME,
    CONST_SERVICE_REASON,
    DOMAIN,
    DOMAIN_DATA,
    EC2_DEF_INTERVAL,
    S3_DEF_INTERVAL,
    SERVICE_CE,
    SERVICE_EC2,
    SERVICE_S3,
    U_REGIONS,
    U_SERVICES,
    USER_INPUT,
)
from .coordinator import (
    AwsDataCEServicesCoordinator,
    AwsDataEC2ServicesCoordinator,
    AwsDataS3ServicesCoordinator,
)

# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = [Platform.SENSOR]


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONST_SERVICE_NAME): cv.string,
        vol.Required(CONST_ACCOUNT): cv.string,
        vol.Required(CONST_SERVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONST_SERVICE_REASON, default="Exclude"): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONST_FILTER): vol.All(cv.ensure_list, [SERVICE_SCHEMA]),
                vol.Optional(CONST_INTERVAL): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONST_SERVICE_NAME): cv.string,
                                vol.Required(CONST_SECONDS): int,
                            }
                        )
                    ],
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AWS Data Filter."""
    conf = config[DOMAIN]
    if conf == hass.data.get(DOMAIN_DATA, None):
        return True

    hass.data[DOMAIN_DATA] = conf
    entries = hass.config_entries.async_entries(DOMAIN)
    for entr in entries:
        hass.config_entries.async_update_entry(entry=entr, data=entr.data)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AWS Data from a config entry."""

    user_data = dict(entry.data)
    selected_regions = user_data[USER_INPUT][U_REGIONS]
    services = user_data[USER_INPUT][U_SERVICES]
    store_coord: dict[str, Any] = {}

    intervals = {}
    domain_data = hass.data.get(DOMAIN_DATA, {})
    for data in domain_data.get(CONST_INTERVAL, []):
        intervals[data[CONST_SERVICE_NAME]] = {CONST_SECONDS: data[CONST_SECONDS]}

    if SERVICE_EC2 in services:
        ec2_interval = intervals.get(SERVICE_EC2, {})
        store_coord[SERVICE_EC2] = ec2_coordinator = AwsDataEC2ServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(
                seconds=ec2_interval.get(CONST_SECONDS, EC2_DEF_INTERVAL)
            ),
        )
        await ec2_coordinator.async_config_entry_first_refresh()

    if SERVICE_S3 in services:
        s3_interval = intervals.get(SERVICE_S3, {})
        store_coord[SERVICE_S3] = s3_coordinator = AwsDataS3ServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(
                seconds=s3_interval.get(CONST_SECONDS, S3_DEF_INTERVAL)
            ),
        )
        await s3_coordinator.async_config_entry_first_refresh()

    if user_data[USER_INPUT][CONST_CE_SELECT]:
        ce_interval = intervals.get(SERVICE_S3, {})
        store_coord[SERVICE_CE] = ce_coordinator = AwsDataCEServicesCoordinator(
            hass,
            entry=entry,
            regions=selected_regions,
            services=services,
            update_interval=timedelta(
                seconds=ce_interval.get(CONST_SECONDS, CE_DEF_INTERVAL)
            ),
        )
        await ce_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = {"coord": store_coord}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    entry.runtime_data = {}
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
