"""The yolink integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import async_timeout
from yolink.client import YoLinkClient
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP
from yolink.mqtt_client import MqttClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import ATTR_CLIENT, ATTR_COORDINATORS, ATTR_DEVICE, ATTR_MQTT_CLIENT, DOMAIN
from .coordinator import YoLinkCoordinator

SCAN_INTERVAL = timedelta(minutes=5)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up yolink from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_mgr = api.ConfigEntryAuth(
        hass, aiohttp_client.async_get_clientsession(hass), session
    )

    yolink_http_client = YoLinkClient(auth_mgr)
    yolink_mqtt_client = MqttClient(auth_mgr)

    def on_message_callback(message: tuple[str, BRDP]) -> None:
        data = message[1]
        device_id = message[0]
        if data.event is None:
            return
        event_param = data.event.split(".")
        event_type = event_param[len(event_param) - 1]
        if event_type not in (
            "Report",
            "Alert",
            "StatusChange",
            "getState",
        ):
            return
        resolved_state = data.data
        if resolved_state is None:
            return
        entry_data = hass.data[DOMAIN].get(entry.entry_id)
        if entry_data is None:
            return
        device_coordinators = entry_data.get(ATTR_COORDINATORS)
        if device_coordinators is None:
            return
        device_coordinator = device_coordinators.get(device_id)
        if device_coordinator is None:
            return
        device_coordinator.async_set_updated_data(resolved_state)

    try:
        async with async_timeout.timeout(10):
            device_response = await yolink_http_client.get_auth_devices()
            home_info = await yolink_http_client.get_general_info()
            await yolink_mqtt_client.init_home_connection(
                home_info.data["id"], on_message_callback
            )
    except YoLinkAuthFailError as yl_auth_err:
        raise ConfigEntryAuthFailed from yl_auth_err
    except (YoLinkClientError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {
        ATTR_CLIENT: yolink_http_client,
        ATTR_MQTT_CLIENT: yolink_mqtt_client,
    }
    auth_devices = device_response.data[ATTR_DEVICE]
    device_coordinators = {}
    for device_info in auth_devices:
        device = YoLinkDevice(device_info, yolink_http_client)
        device_coordinator = YoLinkCoordinator(hass, device)
        try:
            await device_coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # Not failure by fetching device state
            device_coordinator.data = {}
        device_coordinators[device.device_id] = device_coordinator
    hass.data[DOMAIN][entry.entry_id][ATTR_COORDINATORS] = device_coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def shutdown_subscription(event) -> None:
        """Shutdown mqtt message subscription."""
        await yolink_mqtt_client.shutdown_home_subscription()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_subscription)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id][
            ATTR_MQTT_CLIENT
        ].shutdown_home_subscription()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
