"""Controller module."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from functools import partial
import logging
import ssl
from typing import Any

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.const import UNDEFINED, UndefinedType
from deebot_client.device import Device
from deebot_client.exceptions import DeebotError, InvalidAuthenticationError
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
from .kvs_mqtt import KvsMqttListener
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

        # Global KVS MQTT listener shared by all camera entities.
        # Started lazily when the first camera entity is enabled (async_acquire_kvs_mqtt)
        # and stopped when the last one is removed (async_release_kvs_mqtt).
        self._kvs_mqtt_listener: KvsMqttListener | None = None
        self._kvs_p2p_handlers: dict[str, Callable[[str, dict], None]] = {}
        self._kvs_mqtt_ref_count: int = 0
        self._kvs_mqtt_lock: asyncio.Lock = asyncio.Lock()

        # Camera entity registry: did -> EcovacsCameraEntity (populated on entity setup)
        self._camera_entities: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Init controller."""
        try:
            devices = await self._api_client.get_devices()
            credentials = await self._authenticator.authenticate()

            if devices.mqtt:
                mqtt = await self._get_mqtt_client()
                mqtt_devices = [
                    Device(info, self._authenticator) for info in devices.mqtt
                ]
                async with asyncio.TaskGroup() as tg:

                    async def _init(device: Device) -> None:
                        """Initialize MQTT device."""
                        await device.initialize(mqtt)
                        self._devices.append(device)

                    for device in mqtt_devices:
                        tg.create_task(_init(device))

            for device_config in devices.xmpp:
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
            for device_config in devices.not_supported:
                _LOGGER.warning(
                    (
                        'Device "%s" not supported. More information at '
                        "https://github.com/DeebotUniverse/client.py/issues/612: %s"
                    ),
                    device_config["deviceName"],
                    device_config,
                )

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
        if self._kvs_mqtt_listener is not None:
            await self._kvs_mqtt_listener.stop()
        await self._authenticator.teardown()

    def _dispatch_kvs_p2p_req(self, topic: str, payload: dict) -> None:
        """Route an incoming KVS P2P request to the correct camera entity handler."""
        parts = topic.split("/")
        # topic format: iot/p2p/{cmd}/{from_id}/{from_class}/{from_res}/...
        if len(parts) >= 4:
            from_did = parts[3]
            handler = self._kvs_p2p_handlers.get(from_did)
            if handler:
                handler(topic, payload)

    def register_kvs_p2p_handler(
        self, did: str, handler: Callable[[str, dict], None]
    ) -> None:
        """Register a per-robot P2P message handler for the global KVS MQTT listener."""
        self._kvs_p2p_handlers[did] = handler

    def unregister_kvs_p2p_handler(self, did: str) -> None:
        """Remove the P2P handler for the given robot DID."""
        self._kvs_p2p_handlers.pop(did, None)

    async def async_acquire_kvs_mqtt(self) -> None:
        """Start the shared KVS MQTT listener if this is the first camera entity.

        ref_count is incremented ONLY after a successful start, so callers can
        always pair every acquire with a release without risking a negative counter.
        """
        async with self._kvs_mqtt_lock:
            if self._kvs_mqtt_listener is None:
                try:
                    credentials = await self._authenticator.authenticate()
                    self._kvs_mqtt_listener = KvsMqttListener(
                        authenticator=self._authenticator,
                        user_id=credentials.user_id,
                        user_resource=self._device_id,
                        on_p2p_req=self._dispatch_kvs_p2p_req,
                        continent=self._continent,
                    )
                    await self._kvs_mqtt_listener.start()
                except Exception as err:  # noqa: BLE001
                    self._kvs_mqtt_listener = None
                    _LOGGER.warning("Failed to start KVS MQTT listener: %s", err)
                    return  # do NOT increment ref_count — no pairing release needed
            self._kvs_mqtt_ref_count += 1
            _LOGGER.debug(
                "KVS MQTT listener acquired (ref_count=%d)", self._kvs_mqtt_ref_count
            )

    async def async_release_kvs_mqtt(self) -> None:
        """Stop the shared KVS MQTT listener when the last camera entity is removed."""
        async with self._kvs_mqtt_lock:
            if self._kvs_mqtt_ref_count > 0:
                self._kvs_mqtt_ref_count -= 1
            if self._kvs_mqtt_ref_count == 0 and self._kvs_mqtt_listener is not None:
                await self._kvs_mqtt_listener.stop()
                self._kvs_mqtt_listener = None
                _LOGGER.debug("KVS MQTT listener stopped (no active camera entities)")

    def register_camera_entity(self, did: str, entity: Any) -> None:
        """Register a camera entity so the stream switch can call it."""
        self._camera_entities[did] = entity

    def unregister_camera_entity(self, did: str) -> None:
        """Remove the camera entity registration."""
        self._camera_entities.pop(did, None)

    def get_camera_entity(self, did: str) -> Any | None:
        """Return the camera entity for the given robot DID, or None."""
        return self._camera_entities.get(did)

    @property
    def kvs_mqtt_listener(self) -> KvsMqttListener | None:
        """Return the global KVS MQTT listener (None if not yet initialized)."""
        return self._kvs_mqtt_listener

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
    def authenticator(self) -> Authenticator:
        """Return the authenticator."""
        return self._authenticator

    @property
    def client_device_id(self) -> str:
        """Return the client device ID used as user_resource in MQTT."""
        return self._device_id

    @property
    def devices(self) -> list[Device]:
        """Return devices."""
        return self._devices

    @property
    def legacy_devices(self) -> list[VacBot]:
        """Return legacy devices."""
        return self._legacy_devices
