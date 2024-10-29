"""Support for LG ThinQ Connect device."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from thinqconnect import ThinQApi, ThinQAPIException
from thinqconnect.integration import async_get_ha_bridge_list

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_CONNECT_CLIENT_ID, MQTT_SUBSCRIPTION_INTERVAL
from .coordinator import DeviceDataUpdateCoordinator, async_setup_device_coordinator
from .mqtt import ThinQMQTT


@dataclass(kw_only=True)
class ThinqData:
    """A class that holds runtime data."""

    coordinators: dict[str, DeviceDataUpdateCoordinator] = field(default_factory=dict)
    mqtt_client: ThinQMQTT | None = None


type ThinqConfigEntry = ConfigEntry[ThinqData]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Set up an entry."""
    entry.runtime_data = ThinqData()

    access_token = entry.data[CONF_ACCESS_TOKEN]
    client_id = entry.data[CONF_CONNECT_CLIENT_ID]
    country_code = entry.data[CONF_COUNTRY]

    thinq_api = ThinQApi(
        session=async_get_clientsession(hass),
        access_token=access_token,
        country_code=country_code,
        client_id=client_id,
    )

    # Setup coordinators and register devices.
    await async_setup_coordinators(hass, entry, thinq_api)

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up MQTT connection.
    await async_setup_mqtt(hass, entry, thinq_api, client_id)

    # Clean up devices they are no longer in use.
    async_cleanup_device_registry(hass, entry)

    return True


async def async_setup_coordinators(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    thinq_api: ThinQApi,
) -> None:
    """Set up coordinators and register devices."""
    # Get a list of ha bridge.
    try:
        bridge_list = await async_get_ha_bridge_list(thinq_api)
    except ThinQAPIException as exc:
        raise ConfigEntryNotReady(exc.message) from exc

    if not bridge_list:
        return

    # Setup coordinator per device.
    task_list = [
        hass.async_create_task(async_setup_device_coordinator(hass, bridge))
        for bridge in bridge_list
    ]
    task_result = await asyncio.gather(*task_list)
    for coordinator in task_result:
        entry.runtime_data.coordinators[coordinator.unique_id] = coordinator


@callback
def async_cleanup_device_registry(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Clean up device registry."""
    new_device_unique_ids = [
        coordinator.unique_id
        for coordinator in entry.runtime_data.coordinators.values()
    ]
    device_registry = dr.async_get(hass)
    existing_entries = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )

    # Remove devices that are no longer exist.
    for old_entry in existing_entries:
        old_unique_id = next(iter(old_entry.identifiers))[1]
        if old_unique_id not in new_device_unique_ids:
            device_registry.async_remove_device(old_entry.id)
            _LOGGER.debug("Remove device_registry: device_id=%s", old_entry.id)


async def async_setup_mqtt(
    hass: HomeAssistant, entry: ThinqConfigEntry, thinq_api: ThinQApi, client_id: str
) -> None:
    """Set up MQTT connection."""
    mqtt_client = ThinQMQTT(hass, thinq_api, client_id, entry.runtime_data.coordinators)
    entry.runtime_data.mqtt_client = mqtt_client

    # Try to connect.
    result = await mqtt_client.async_connect()
    if not result:
        _LOGGER.error("Failed to set up mqtt connection")
        return

    # Ready to subscribe.
    await mqtt_client.async_start_subscribes()

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            mqtt_client.async_refresh_subscribe,
            MQTT_SUBSCRIPTION_INTERVAL,
            cancel_on_shutdown=True,
        )
    )
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, mqtt_client.async_disconnect
        )
    )


async def async_unload_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Unload the entry."""
    if entry.runtime_data.mqtt_client:
        await entry.runtime_data.mqtt_client.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
