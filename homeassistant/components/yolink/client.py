"""Client of YoLink API."""

import asyncio
import logging
from typing import Any, Dict, List
import uuid

from aiohttp.client import ClientResponse

from homeassistant.components.yolink.device import YoLinkDevice
from homeassistant.core import HomeAssistant, callback

from .api import AuthenticationManager
from .const import (
    YOLINK_API_GATE,
    YOLINK_API_MQTT_BROKER,
    YOLINK_API_MQTT_BROKER_POER,
    YoLinkAPIError,
)
from .model import BRDP

_LOGGER = logging.getLogger(__name__)


class YoLinkHttpClient:
    """YoLink API Client."""

    def __init__(self, auth: AuthenticationManager):
        """Initialize the YoLink API."""
        self._auth_mgr = auth

    async def request(
        self,
        method: str,
        url: str,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> ClientResponse:
        """Proxy Request and add Auth/CV headers."""
        headers = kwargs.pop("headers", {})
        params = kwargs.pop("params", None)
        data = kwargs.pop("data", None)

        # Extra, user supplied values
        extra_headers = kwargs.pop("extra_headers", None)
        extra_params = kwargs.pop("extra_params", None)
        extra_data = kwargs.pop("extra_data", None)
        if include_auth:
            # Ensure tokens valid
            await self._auth_mgr.check_and_refresh_token()
            # Set auth header
            headers["Authorization"] = self._auth_mgr.httpAuthHeader()
        # Extend with optionally supplied values
        if extra_headers:
            headers.update(extra_headers)
        if extra_params:
            # query parameters
            params = params or {}
            params.update(extra_params)
        if extra_data:
            # form encoded post data
            data = data or {}
            data.update(extra_data)
        return await self._auth_mgr.httpClientSession.request(
            method, url, **kwargs, headers=headers, params=params, data=data, timeout=8
        )

    async def get(self, url: str, **kwargs: Any) -> ClientResponse:
        """Call YoLink API with GET."""
        return await self.request("GET", url, True, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> ClientResponse:
        """Call YoLink API with POST."""
        return await self.request("POST", url, True, **kwargs)

    async def callYoLinkAPI(self, bsdp: Dict, **kwargs: Any) -> BRDP:
        """Call YoLink API with BSDP."""
        resp = await self.post(YOLINK_API_GATE, json=bsdp, **kwargs)
        resp.raise_for_status()
        _body = await resp.text()
        brdp = BRDP.parse_raw(_body)
        try:
            brdp.raise_for_status()
        except YoLinkAPIError as err:
            # if err.code == "010103":
            #     await self._auth_mgr.check_and_refresh_token

            raise err
        return brdp

    async def getDeviceList(self, **kwargs: Any) -> BRDP:
        """Call YoLink API -> Home.getDeviceList."""
        return await self.callYoLinkAPI({"method": "Home.getDeviceList"}, **kwargs)

    async def getGeneralInfo(self, **kwargs: Any) -> BRDP:
        """Call YoLink API -> Home.getGeneralInfo."""
        return await self.callYoLinkAPI({"method": "Home.getGeneralInfo"}, **kwargs)


class HomeEventSubscription:
    """YoLink Home Subscription."""

    def __init__(self, homeId: str):
        """Init Home Subscription."""
        self.homeId = homeId
        self.platformDeviceSubscription: Dict[str, List[YoLinkDevice]] = {}

    def attachPlatformDevices(self, platform: str, devices: List[YoLinkDevice]):
        """Relate YoLink devices to this subscription."""
        self.platformDeviceSubscription[platform] = devices
        return None

    def onDeviceMessage(self, device_id: str, msg: BRDP):
        """Call when message from device received."""
        for platform, devices in self.platformDeviceSubscription.items():
            for device in devices:
                if device.device_id == device_id:
                    device.push_data(msg)
        return None


class MQTTSubscription:
    """MQTT Subscription."""

    def __init__(self, *topics):
        """Init MQTT Subscription."""
        self.sub_topics = topics
        self.sub_topic_success = {}

    def on_subscribe_success(self, topic):
        """On MQTT Sub Success."""
        self.sub_topic_success[topic] = True

    def on_disconnected(self):
        """On MQTT Disconnected."""
        self.sub_topic_success = {}

    def subscribe(self):
        """Return topics need to subscribe."""
        ret = []
        for topic in self.sub_topics:
            if not (
                topic in self.sub_topic_success
                and self.sub_topic_success[topic] is True
            ):
                ret.append(topic)
        return ret

    def on_message(self, topic: str, msg: str):
        """Implement callback for MQTTClient.on_message."""
        pass


class HomeEventMQTTSubscription(HomeEventSubscription, MQTTSubscription):
    """MQTT implement of YoLink Home Subscription."""

    def __init__(self, homeId: str):
        """Init MQTT Home Subscription."""

        HomeEventSubscription.__init__(self, homeId)
        self.device_report_topic = f"yl-home/{self.homeId}/+/report"
        MQTTSubscription.__init__(self, self.device_report_topic)

    def on_message(self, topic: str, msg: str):
        """On Receive MQTT Message."""
        keys = topic.split("/")
        if len(keys) == 4 and keys[3] == "report":
            self.onDeviceMessage(keys[2], BRDP.parse_raw(msg))
        return None


class YoLinkMQTTClient:
    """YoLink API Client."""

    def __init__(self, auth: AuthenticationManager, hass: HomeAssistant):
        """Initialize the YoLink API."""
        self._auth_mgr: AuthenticationManager = auth
        self._subscriptions: List[MQTTSubscription] = []
        self.hass = hass
        self.init_client()

    def subscribeHome(self, subscription: MQTTSubscription) -> bool:
        """Relate home subscription to MQTT client."""
        self._subscriptions.append(subscription)
        return True

    def init_client(self):
        """Initialize paho mqtt client."""
        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        from paho.mqtt import client as mqtt

        client_id = mqtt.base62(uuid.uuid4().int, padding=22)
        self._mqttc = mqtt.Client(client_id, protocol=mqtt.MQTTv31)

        # Enable logging
        self._mqttc.enable_logger()
        self._mqttc.on_connect = self._mqtt_on_connect
        self._mqttc.on_disconnect = self._mqtt_disconnect
        self._mqttc.on_message = self._mqtt_on_message
        # self._mqttc.on_publish = self._mqtt_on_callback
        self._mqttc.on_subscribe = self._mqtt_on_subscribe
        # self._mqttc.on_unsubscribe = self._mqtt_on_callback

    async def async_connect(self) -> None:
        """Connect to the host. Does not process messages yet."""
        # pylint: disable=import-outside-toplevel
        await self._auth_mgr.check_and_refresh_token()

        import paho.mqtt.client as mqtt

        self._mqttc.username_pw_set(self._auth_mgr.accessToken, "")
        result = None
        try:
            result = await self.hass.async_add_executor_job(
                self._mqttc.connect,
                YOLINK_API_MQTT_BROKER,
                YOLINK_API_MQTT_BROKER_POER,
                600,
            )
        except OSError as err:
            _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)

        if result is not None and result != 0:
            _LOGGER.error(
                "Failed to connect to MQTT server: %s", mqtt.error_string(result)
            )

        self._mqttc.loop_start()

    async def async_disconnect(self):
        """Stop the MQTT client."""

        def stop():
            """Stop the MQTT client."""
            # Do not disconnect, we want the broker to always publish will
            self._mqttc.loop_stop()

        await self.hass.async_add_executor_job(stop)

    def _mqtt_on_connect(self, _mqttc, _userdata, _flags, result_code: int) -> None:
        """On connect callback.

        Resubscribe to all topics we were subscribed to and publish birth
        message.
        """

        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        if result_code != mqtt.CONNACK_ACCEPTED:
            _LOGGER.error(
                "Unable to connect to the MQTT broker: %s",
                mqtt.connack_string(result_code),
            )
            return

        self.connected = True
        # dispatcher_send(self.hass, MQTT_CONNECTED)
        _LOGGER.info(
            "Connected to MQTT server %s:%s (%s)",
            YOLINK_API_MQTT_BROKER,
            YOLINK_API_MQTT_BROKER_POER,
            result_code,
        )

        # Group subscriptions to only re-subscribe once for each topic.
        for sub in self._subscriptions:
            for topic in sub.subscribe():
                self.hass.add_job(self._async_perform_subscription, topic, 0)

    def _mqtt_disconnect(self, _mqttc, _userdata, _rc):
        """Mqtt on disconnect."""
        try:
            access_token = asyncio.run_coroutine_threadsafe(
                self._auth_mgr.check_and_refresh_token(), self.hass.loop
            ).result()
            _mqttc.username_pw_set(access_token, "")
        except Exception as e:
            print(e)

    async def _async_perform_subscription(self, topic: str, qos: int) -> None:
        """Perform a paho-mqtt subscription."""
        self._mqttc.subscribe(topic, qos)

    def _mqtt_on_subscribe(self, _mqttc, userdata, mid, granted_qos):
        for sub in self._subscriptions:
            print(mid)
            # sub.on_subscribe_success()
        # print(properties)
        # for sub in self._subscriptions:
        # sub.on_subscribe_success(topic)

    def _mqtt_on_message(self, _mqttc, _userdata, msg) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    @callback
    async def _mqtt_handle_message(self, msg) -> None:
        _LOGGER.debug(
            "Received message on %s%s: %s",
            msg.topic,
            " (retained)" if msg.retain else "",
            msg.payload[0:8192],
        )

        for sub in self._subscriptions:
            sub.on_message(msg.topic, msg.payload.decode("UTF-8"))
