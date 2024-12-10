"""Module to communicate with the Venus OS MQTT Broker."""

import asyncio
from datetime import datetime, timedelta
import json
import logging

from gmqtt import Client as gmqttClient
from gmqtt.mqtt.handler import MQTTConnectError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from ._topicmap import topic_map
from .const import TOPIC_INSTALLATION_ID
from .data_classes import ParsedTopic, TopicDescriptor
from .victronvenus_base import VictronVenusDeviceBase, VictronVenusHubBase
from .victronvenus_device import VictronDevice


class VictronVenusHub(VictronVenusHubBase):
    """Class to communicate with the Venus OS hub."""

    _installationid_event: asyncio.Event

    def __init__(
        self,
        hass: HomeAssistant,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        serial: str | None,
        use_ssl: bool,
        installationid: str | None = None,
        modelName: str | None = None,
    ) -> None:
        """Initialize."""

        super().__init__(hass)
        self.modelName = modelName
        self.host = host
        self.username = username
        self.password = password
        self.serial = serial
        self.use_ssl = use_ssl
        self._client: gmqttClient | None = None
        self.port = port
        self.installationid = installationid
        self.logger = logging.getLogger(__name__)
        self.devices: dict[str, VictronDevice] = {}
        self.first_refresh = asyncio.Event()

    async def connect(self) -> None:
        """Connect to the hub."""
        self._client = gmqttClient("homeassistant")
        if self.username not in {None, ""}:
            self._client.set_auth_credentials(self.username, self.password)
        await self._client.connect(host=self.host, port=self.port, ssl=self.use_ssl)

    async def disconnect(self) -> None:
        """Disconnect from the hub."""
        if self._client is None:
            return
        if self._client.is_connected:
            await self._client.disconnect()
        self._client = None

    async def initiate_keep_alive(self) -> None:
        """Schedule a keep-alive async function to run every 30 seconds."""
        if self.installationid is None:
            self.installationid = await self._read_installation_id()
        await self._keep_alive(datetime.now())  # trigger immediate refresh
        async_track_time_interval(
            self.hass, self._keep_alive, timedelta(seconds=55)
        )  # venus stops publishing after 60 seconds.

    async def _keep_alive(self, now: datetime) -> None:
        keepalive_topic = f"R/{self.installationid}/keepalive"
        if self._client is not None:
            if self._client.is_connected:
                self._client.publish(keepalive_topic, b"1")

    async def _on_installationid_message(
        self, client: gmqttClient, topic: str, payload: bytes, qos: int, retain: bool
    ) -> None:
        """Handle an incoming message from the hub."""

        topic_parts = topic.split("/")

        if len(topic_parts) != 5:
            return
        # "N/+/system/0/Serial"
        if (
            topic_parts[2] == "system"
            and topic_parts[3] == "0"
            and topic_parts[4] == "Serial"
        ):
            payload_json = json.loads(payload.decode())
            self.installationid = payload_json.get("value")
            self._installationid_event.set()

    async def _read_installation_id(self) -> str:
        """Read the installation id for the Victron installation. Depends on no other subscriptions being active."""

        if self._client is None:
            raise ProgrammingError("Client is not initialized")
        if not self._client.is_connected:
            raise NotConnected("Client is not connected")
        self._client.on_message = self._on_installationid_message
        self._installationid_event = asyncio.Event()
        self._client.subscribe(TOPIC_INSTALLATION_ID)
        await self._installationid_event.wait()
        self._client.unsubscribe(TOPIC_INSTALLATION_ID)
        return str(self.installationid)

    async def verify_connection_details(self) -> str:
        """Verify the username and password."""

        try:
            await self.connect()
            return await self._read_installation_id()
        except MQTTConnectError as e:
            if "135" in str(e):
                raise InvalidAuth from e
            raise CannotConnect from e
        finally:
            await self.disconnect()

    async def setup_subscriptions(self) -> None:
        """Subscribe to list of topics."""

        if self._client is None:
            raise ProgrammingError("Client is not initialized")
        if not self._client.is_connected:
            raise NotConnected("Client is not connected")

        self._client.on_message = self._on_message

        for topic in topic_map:
            self._client.subscribe(topic)

        self._client.subscribe("N/+/full_publish_completed")

    async def wait_for_first_refresh(self) -> None:
        """Wait for the first full refresh to complete, as per the "full_publish_completed" MQTT message."""
        await self.first_refresh.wait()

    def _create_device_unique_id(
        self, installation_id: str, device_type: str, device_id: str
    ) -> str:
        return f"{installation_id}_{device_type}_{device_id}"

    def _get_or_create_device(
        self, parsed_topic: ParsedTopic, desc: TopicDescriptor
    ) -> "VictronDevice":
        unique_id = self._create_device_unique_id(
            parsed_topic.installation_id,
            parsed_topic.device_type,
            parsed_topic.device_id,
        )
        device = self.devices.get(unique_id)
        if device is None:
            device = VictronDevice(
                self,
                unique_id,
                desc,
                parsed_topic.installation_id,
                parsed_topic.device_type,
                parsed_topic.device_id,
            )
            self.devices[unique_id] = device
            if parsed_topic.device_type == "system":
                if self.modelName is not None:
                    device.set_root_device_name(self.modelName)
                else:
                    device.set_root_device_name("Victron Venus")

        return device

    async def _on_message(
        self, client: gmqttClient, topic: str, payload: bytes, qos: int, retain: bool
    ) -> None:
        """Handle an incoming message from the hub."""

        if "full_publish_completed" in topic:
            client.unsubscribe("N/+/full_publish_completed")
            self.first_refresh.set()
            return

        parsed_topic = ParsedTopic.from_topic(topic)
        if parsed_topic is None:
            return

        if parsed_topic.device_type != "system" and parsed_topic.device_id == "0":
            return

        desc = topic_map.get(parsed_topic.wildcards_with_device_type)
        if desc is None:
            desc = topic_map.get(parsed_topic.wildcards_without_device_type)

        if desc is None:
            return

        device = self._get_or_create_device(parsed_topic, desc)

        await device.handle_message(parsed_topic, desc, payload.decode())

    @property
    def victron_devices(self) -> list[VictronVenusDeviceBase]:
        "Return a list of devices attached to the hub."
        return list(self.devices.values())


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ProgrammingError(HomeAssistantError):
    """Error to indicate that we are in a state that should never be reached."""


class NotConnected(HomeAssistantError):
    """Error to indicate that we expected to be connected at this stage but is not."""
