"""Controller module."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator
from deebot_client.device import Device
from deebot_client.exceptions import DeebotError, InvalidAuthenticationError
from deebot_client.models import Configuration
from deebot_client.mqtt_client import MqttClient, MqttConfiguration
from deebot_client.util import md5

from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICES,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


class EcovacsController:
    """Ecovacs controller."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialize controller."""
        self._hass_config: Mapping[str, Any] = config
        self._hass: HomeAssistant = hass
        self._devices: list[Device] = []
        verify_ssl = config.get(CONF_VERIFY_SSL, True)
        device_id = get_client_device_id(hass, config[CONF_MODE])

        ecovacs_config = Configuration(
            aiohttp_client.async_get_clientsession(self._hass, verify_ssl=verify_ssl),
            device_id=device_id,
            country=config[CONF_COUNTRY],
            verify_ssl=verify_ssl,
        )

        self._authenticator = Authenticator(
            ecovacs_config,
            config[CONF_USERNAME],
            md5(config[CONF_PASSWORD]),
        )
        self._api_client = ApiClient(self._authenticator)

        mqtt_config = MqttConfiguration(config=ecovacs_config)
        self._mqtt: MqttClient = MqttClient(mqtt_config, self._authenticator)

    @property
    def devices(self) -> list[Device]:
        """Return devices."""
        return self._devices

    async def initialize(self) -> None:
        """Init controller."""
        try:
            devices = await self._api_client.get_devices()
            for device in devices:
                name = device.api_device_info["name"]
                if name in self._hass_config[CONF_DEVICES]:
                    bot = Device(device, self._authenticator)
                    _LOGGER.debug("New device found: %s", name)
                    await bot.initialize(self._mqtt)
                    self._devices.append(bot)
        except InvalidAuthenticationError as ex:
            raise ConfigEntryAuthFailed from ex
        except DeebotError as ex:
            msg = "Error during setup"
            _LOGGER.exception(msg)
            raise ConfigEntryNotReady(msg) from ex

        _LOGGER.debug("Controller initialize complete")

    async def teardown(self) -> None:
        """Disconnect controller."""
        for device in self._devices:
            await device.teardown()
        await self._mqtt.disconnect()
        await self._authenticator.teardown()
