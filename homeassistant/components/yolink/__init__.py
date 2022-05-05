"""The yolink integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout
import voluptuous as vol
from yolink.client import YoLinkClient
from yolink.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP
from yolink.mqtt_client import MqttClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api, config_flow
from .const import (
    ATTR_CLIENT,
    ATTR_COORDINATOR,
    ATTR_DEVICE,
    ATTR_DEVICE_STATE,
    ATTR_MQTT_CLIENT,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.SENSOR]


class YoLinkCoordinator(DataUpdateCoordinator[dict]):
    """YoLink DataUpdateCoordinator."""

    def __init__(
        self, hass: HomeAssistant, yl_client: YoLinkClient, yl_mqtt_client: MqttClient
    ) -> None:
        """Init YoLink DataUpdateCoordinator.

        fetch state every 30 minutes base on yolink device heartbeat interval
        data is None before the first successful update, but we need to use data at first update
        """
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=30)
        )
        self._client = yl_client
        self._mqtt_client = yl_mqtt_client
        self.yl_devices: list[YoLinkDevice] = []
        self.data = {}

    def on_message_callback(self, message: tuple[str, BRDP]):
        """On message callback."""
        data = message[1]
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
        self.data[message[0]] = resolved_state
        self.async_set_updated_data(self.data)

    async def init_coordinator(self):
        """Init coordinator."""
        try:
            async with async_timeout.timeout(10):
                home_info = await self._client.get_general_info()
                await self._mqtt_client.init_home_connection(
                    home_info.data["id"], self.on_message_callback
                )
            async with async_timeout.timeout(10):
                device_response = await self._client.get_auth_devices()

        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err

        except (YoLinkClientError, asyncio.TimeoutError) as err:
            raise ConfigEntryNotReady from err

        yl_devices: list[YoLinkDevice] = []

        for device_info in device_response.data[ATTR_DEVICE]:
            yl_devices.append(YoLinkDevice(device_info, self._client))

        self.yl_devices = yl_devices

    async def fetch_device_state(self, device: YoLinkDevice):
        """Fetch Device State."""
        try:
            async with async_timeout.timeout(10):
                device_state_resp = await device.fetch_state_with_api()
                if ATTR_DEVICE_STATE in device_state_resp.data:
                    self.data[device.device_id] = device_state_resp.data[
                        ATTR_DEVICE_STATE
                    ]
        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err
        except YoLinkClientError as yl_client_err:
            raise UpdateFailed(
                f"Error communicating with API: {yl_client_err}"
            ) from yl_client_err

    async def _async_update_data(self) -> dict:
        fetch_tasks = []
        for yl_device in self.yl_devices:
            fetch_tasks.append(self.fetch_device_state(yl_device))
        if fetch_tasks:
            await asyncio.gather(*fetch_tasks)
        return self.data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the yolink component."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up yolink from a config entry."""
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
    coordinator = YoLinkCoordinator(hass, yolink_http_client, yolink_mqtt_client)
    await coordinator.init_coordinator()
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as ex:
        _LOGGER.error("Fetch initial data fail: %s", ex)

    hass.data[DOMAIN][entry.entry_id] = {
        ATTR_CLIENT: yolink_http_client,
        ATTR_MQTT_CLIENT: yolink_mqtt_client,
        ATTR_COORDINATOR: coordinator,
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
