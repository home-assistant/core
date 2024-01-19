"""Controller module."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator
from deebot_client.device import Device
from deebot_client.exceptions import DeebotError, InvalidAuthenticationError
from deebot_client.models import Configuration, DeviceInfo
from deebot_client.mqtt_client import MqttClient, MqttConfiguration
from deebot_client.util import md5
from sucks import EcoVacsAPI, VacBot

from homeassistant.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


class EcovacsController:
    """Ecovacs controller."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialize controller."""
        self._hass = hass
        self.devices: list[Device] = []
        self.legacy_devices: list[VacBot] = []
        verify_ssl = config.get(CONF_VERIFY_SSL, True)
        device_id = get_client_device_id()

        self._config = Configuration(
            aiohttp_client.async_get_clientsession(self._hass, verify_ssl=verify_ssl),
            device_id=device_id,
            country=config[CONF_COUNTRY],
            verify_ssl=verify_ssl,
        )

        self._authenticator = Authenticator(
            self._config,
            config[CONF_USERNAME],
            md5(config[CONF_PASSWORD]),
        )
        self._api_client = ApiClient(self._authenticator)

        mqtt_config = MqttConfiguration(config=self._config)
        self._mqtt = MqttClient(mqtt_config, self._authenticator)

    async def initialize(self) -> None:
        """Init controller."""
        try:
            devices = await self._api_client.get_devices()
            credentials = await self._authenticator.authenticate()
            for device_config in devices:
                if isinstance(device_config, DeviceInfo):
                    device = Device(device_config, self._authenticator)
                    await device.initialize(self._mqtt)
                    self.devices.append(device)
                else:
                    # Legacy device
                    bot = VacBot(
                        credentials.user_id,
                        EcoVacsAPI.REALM,
                        self._config.device_id[0:8],
                        credentials.token,
                        device_config,
                        self._config.continent,
                        monitor=True,
                    )
                    self.legacy_devices.append(bot)
        except InvalidAuthenticationError as ex:
            raise ConfigEntryError("Invalid credentials") from ex
        except DeebotError as ex:
            raise ConfigEntryNotReady("Error during setup") from ex

        _LOGGER.debug("Controller initialize complete")

    async def teardown(self) -> None:
        """Disconnect controller."""
        for device in self.devices:
            await device.teardown()
        for legacy_device in self.legacy_devices:
            await self._hass.async_add_executor_job(legacy_device.disconnect)
        await self._mqtt.disconnect()
        await self._authenticator.teardown()
