"""The HuaweiSmartLogger3000 integration."""
from __future__ import annotations

import logging

from huawei_smart_logger.huawei_smart_logger import HuaweiSmartLogger3000API

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES
from .coordinator import HuaweiSmartLogger3000DataCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = MIN_TIME_BETWEEN_UPDATES


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HuaweiSmartLogger3000 from a config entry."""

    _LOGGER.debug("In init.py async_setup_entry")
    api = HuaweiSmartLogger3000API(
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_HOST],
    )

    coordinator = HuaweiSmartLogger3000DataCoordinator(
        hass=hass, config_entry=config_entry, api=api
    )

    async def _request_refresh(event: Event) -> None:
        """Request a refresh."""
        await coordinator.async_request_refresh()

    if hass.state == CoreState.running:
        await coordinator.async_config_entry_first_refresh()
    else:
        # Running a speed test during startup can prevent
        # integrations from being able to setup because it
        # can saturate the network interface.
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _request_refresh)

    # this is to test if startup works only
    data_dict = await api.fetch_data()
    if len(data_dict) == 0:
        _LOGGER.error("Data_dict is empty")

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    #  for sensor in data_dict:
    #     hass.states.async_set(sensor, data_dict[sensor])
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data.pop(DOMAIN)
    return unload_ok
