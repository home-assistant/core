"""Controller module."""

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from functools import partial
import logging
import ssl

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.const import UNDEFINED, UndefinedType
from deebot_client.device import Device
from deebot_client.events import FirmwareEvent, NetworkInfoEvent
from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
)
from deebot_client.models import AccountCredentials
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5
from deebot_client.util.continents import get_continent
from sucks import EcoVacsAPI, VacBot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.util.ssl import get_default_no_verify_context

from .const import (
    CONF_ACCOUNT_CREDENTIALS,
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EcovacsController:
    """Ecovacs controller."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize controller."""
        self._hass = hass
        self._entry = entry
        config = entry.data
        self._devices: list[Device] = []
        self._legacy_devices: list[VacBot] = []
        self._unsubscribe_device_events: list[Callable[[], None]] = []
        rest_url = config.get(CONF_OVERRIDE_REST_URL)
        self._device_id = config[CONF_DEVICE_ID]
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
            # Renewing with the stored account credentials avoids the password
            # login, which keeps asking some accounts for device verification
            account_credentials=(
                AccountCredentials(**account)
                if (account := config.get(CONF_ACCOUNT_CREDENTIALS))
                else None
            ),
        )
        self._unsubscribe_account_credentials = (
            self._authenticator.subscribe_account_credentials(
                self._async_store_account_credentials
            )
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

            if devices.mqtt:
                mqtt = await self._get_mqtt_client()
                mqtt_devices = [
                    Device(info, self._authenticator) for info in devices.mqtt
                ]
                async with asyncio.TaskGroup() as tg:

                    async def _init(device: Device) -> None:
                        """Initialize MQTT device."""
                        await device.initialize(mqtt)
                        self._subscribe_device_info_events(device)
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

        except DeviceVerificationRequiredError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_verification_required",
            ) from ex
        except InvalidAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from ex
        except DeebotError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_error",
            ) from ex

        _LOGGER.debug("Controller initialize complete")

    async def _async_store_account_credentials(
        self, account: AccountCredentials
    ) -> None:
        """Store new account credentials in the config entry."""
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_ACCOUNT_CREDENTIALS: asdict(account)},
        )

    def _subscribe_device_info_events(self, device: Device) -> None:
        """Update the device registry when the firmware or MAC is reported."""
        identifier = (DOMAIN, device.device_info["did"])
        device_registry = dr.async_get(self._hass)

        def device_entry() -> dr.DeviceEntry | None:
            return device_registry.async_get_device_by_identifier(
                identifier, self._entry.entry_id
            )

        async def on_firmware(event: FirmwareEvent) -> None:
            if entry := device_entry():
                device_registry.async_update_device(entry.id, sw_version=event.version)

        async def on_network(event: NetworkInfoEvent) -> None:
            if event.mac and (entry := device_entry()):
                device_registry.async_update_device(
                    entry.id,
                    new_connections={(dr.CONNECTION_NETWORK_MAC, event.mac)},
                )

        self._unsubscribe_device_events.extend(
            (
                device.events.subscribe(FirmwareEvent, on_firmware),
                device.events.subscribe(NetworkInfoEvent, on_network),
            )
        )

    async def teardown(self) -> None:
        """Disconnect controller."""
        self._unsubscribe_account_credentials()
        for unsubscribe in self._unsubscribe_device_events:
            unsubscribe()
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
