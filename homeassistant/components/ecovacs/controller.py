"""Controller module."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
import ssl
from typing import Any

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.const import UNDEFINED, UndefinedType
from deebot_client.device import Device
from deebot_client.exceptions import DeebotError, InvalidAuthenticationError
from deebot_client.models import DeviceInfo
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5
from deebot_client.util.continents import get_continent
from sucks import EcoVacsAPI, VacBot

from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.util.ssl import get_default_no_verify_context

from .const import (
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
)
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


class EcovacsController:
    """Ecovacs controller."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialize controller."""
        self._hass = hass
        self._devices: list[Device] = []
        self._legacy_devices: list[VacBot] = []
        rest_url = config.get(CONF_OVERRIDE_REST_URL)
        self._device_id = get_client_device_id(hass, rest_url is not None)
        country = config[CONF_COUNTRY]
        self._continent = get_continent(country)

        self._authenticator = Authenticator(
            create_rest_config(
                aiohttp_client.async_get_clientsession(self._hass),
                device_id=self._device_id,
                alpha_2_country=country,
                override_rest_url=rest_url,
            ),
            config[CONF_USERNAME],
            md5(config[CONF_PASSWORD]),
        )
        self._api_client = ApiClient(self._authenticator)

        mqtt_url = config.get(CONF_OVERRIDE_MQTT_URL)
        ssl_context: UndefinedType | ssl.SSLContext = UNDEFINED
        if not config.get(CONF_VERIFY_MQTT_CERTIFICATE, True) and mqtt_url:
            ssl_context = get_default_no_verify_context()

        self._mqtt_config_fn = partial(
            create_mqtt_config,
            device_id=self._device_id,
            country=country,
            override_mqtt_url=mqtt_url,
            ssl_context=ssl_context,
        )
        self._mqtt_client: MqttClient | None = None

        self._added_legacy_entities: set[str] = set()

    async def initialize(self) -> None:
        """Init controller."""
        try:
            devices = await self._api_client.get_devices()
            credentials = await self._authenticator.authenticate()
            for device_config in devices:
                if isinstance(device_config, DeviceInfo):
                    # MQTT device
                    device = Device(device_config, self._authenticator)
                    mqtt = await self._get_mqtt_client()
                    await device.initialize(mqtt)
                    self._devices.append(device)
                else:
                    # Legacy device
                    bot = VacBot(
                        credentials.user_id,
                        EcoVacsAPI.REALM,
                        self._device_id[0:8],
                        credentials.token,
                        device_config,
                        self._continent,
                        monitor=True,
                    )
                    self._legacy_devices.append(bot)
        except InvalidAuthenticationError as ex:
            raise ConfigEntryError("Invalid credentials") from ex
        except DeebotError as ex:
            raise ConfigEntryNotReady("Error during setup") from ex

        _LOGGER.debug("Controller initialize complete")

    async def teardown(self) -> None:
        """Disconnect controller."""
        for device in self._devices:
            await device.teardown()
        for legacy_device in self._legacy_devices:
            await self._hass.async_add_executor_job(legacy_device.disconnect)
        if self._mqtt_client is not None:
            await self._mqtt_client.disconnect()
        await self._authenticator.teardown()

    def add_legacy_entity(self, device: VacBot, component: str) -> None:
        """Add legacy entity."""
        self._added_legacy_entities.add(f"{device.vacuum['did']}_{component}")

    def legacy_entity_is_added(self, device: VacBot, component: str) -> bool:
        """Check if legacy entity is added."""
        return f"{device.vacuum['did']}_{component}" in self._added_legacy_entities

    async def _get_mqtt_client(self) -> MqttClient:
        """Return validated MQTT client."""
        if self._mqtt_client is None:
            config = await self._hass.async_add_executor_job(self._mqtt_config_fn)
            mqtt = MqttClient(config, self._authenticator)
            await mqtt.verify_config()
            self._mqtt_client = mqtt

        return self._mqtt_client

    @property
    def devices(self) -> list[Device]:
        """Return devices."""
        return self._devices

    @property
    def legacy_devices(self) -> list[VacBot]:
        """Return legacy devices."""
        return self._legacy_devices
