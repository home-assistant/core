"""Ecovacs camera platform — KVS WebRTC viewer.

Exposes a Camera entity for each modern Ecovacs robot. The entity is disabled
by default. The stream is started and stopped explicitly by the user via the
ON/OFF toggle or via HA services (camera.turn_on / camera.turn_off).
When no stream is active, the last captured frame is returned so the entity
stays visible; a black placeholder is shown only if no frame was ever received.

The KVS MQTT connection (jmq broker) is managed globally by EcovacsController
and shared across all camera entities. It is started lazily when the first
camera entity is added to HA (i.e. when the user enables it) and stopped when
the last one is removed, so no connection is opened for disabled entities.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging

from deebot_client.device import Device
from deebot_client.util.continents import get_continent

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .const import CAMERA_STREAM_STATE_SIGNAL, CONF_CAMERA_PINS
from .kvs_api import (
    generate_video_track_id,
    get_ma_gw,
    start_watch_v2,
    verify_video_pwd,
)
from .kvs_stream import KvsStreamSession

_LOGGER = logging.getLogger(__name__)

# 2x2 black JPEG placeholder shown when no stream is active and no prior frame exists.
# Generated with: av.VideoFrame.from_ndarray(np.zeros((2,2,3), uint8), 'rgb24')
# then reformatted to yuvj420p (Y=0, U=128, V=128 = true black).
_BLACK_JPEG: bytes = (
    b"\xff\xd8\xff\xfe\x00\x10Lavc62.11.100\x00\xff\xdb\x00C\x00\x08\x04\x04"
    b"\x04\x04\x04\x05\x05\x05\x05\x05\x05\x06\x06\x06\x06\x06\x06\x06\x06"
    b"\x06\x06\x06\x06\x06\x07\x07\x07\x08\x08\x08\x07\x07\x07\x06\x06\x07"
    b"\x07\x08\x08\x08\x08\t\t\t\x08\x08\x08\x08\t\t\n\n\n\x0c\x0c\x0b\x0b"
    b"\x0e\x0e\x0e\x11\x11\x14\xff\xc4\x00K\x00\x01\x01\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x01\x01\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x10\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x11\x01\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc0\x00"
    b'\x11\x08\x00\x02\x00\x02\x03\x01"\x00\x02\x11\x00\x03\x11\x00\xff\xda'
    b"\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\x9f\xc0\x01\xff\xd9"
)


@dataclass(kw_only=True, frozen=True)
class EcovacsCameraEntityDescription(CameraEntityDescription):
    """Description for an Ecovacs camera entity."""

    key: str = "camera"
    translation_key: str = "camera"
    entity_registry_enabled_default: bool = False


_CAMERA_DESCRIPTION = EcovacsCameraEntityDescription()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ecovacs camera entities."""
    controller = config_entry.runtime_data
    entities = [
        EcovacsCameraEntity(device, config_entry) for device in controller.devices
    ]
    if entities:
        async_add_entities(entities)


class EcovacsCameraEntity(Camera):
    """Camera entity for an Ecovacs robot (KVS WebRTC viewer).

    The entity is always "on" (is_on=True) so that the frontend can render
    the camera card and show the ON/OFF controls.  When no KVS session is
    active, a black placeholder JPEG is returned instead of HTTP 503.
    The stream is controlled via async_turn_on() / async_turn_off() which
    start and stop the real KVS session, tracked via _stream_started.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.ON_OFF

    entity_description: EcovacsCameraEntityDescription

    def __init__(
        self,
        device: Device,
        config_entry: EcovacsConfigEntry,
    ) -> None:
        """Initialize the camera entity."""
        super().__init__()
        self._device = device
        self._config_entry = config_entry

        did = device.device_info["did"]
        self.entity_description = _CAMERA_DESCRIPTION
        self._attr_unique_id = f"{did}_camera"
        self._attr_entity_registry_enabled_default = False

        self._stream_started: bool = False
        self._session: KvsStreamSession | None = None
        self._session_lock = asyncio.Lock()
        self._start_task: asyncio.Task[None] | None = None
        self._p2p_resp_task: asyncio.Task[None] | None = None
        self._last_jpeg: bytes | None = (
            None  # last captured frame, shown after stream stops
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (mirrors EcovacsEntity pattern)."""
        device_info = self._device.device_info
        info = DeviceInfo(
            identifiers={("ecovacs", device_info["did"])},
            manufacturer="Ecovacs",
            sw_version=self._device.fw_version,
            serial_number=device_info["name"],
            model_id=device_info["class"],
        )
        if nick := device_info.get("nick"):
            info["name"] = nick
        if model := device_info.get("deviceName"):
            info["model"] = model
        if mac := self._device.mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
        return info

    async def async_added_to_hass(self) -> None:
        """Called when added to hass: register entity and start shared MQTT if needed."""
        await super().async_added_to_hass()
        controller = self._config_entry.runtime_data
        did = self._device.device_info["did"]
        controller.register_camera_entity(did, self)
        await controller.async_acquire_kvs_mqtt()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up on removal: release shared MQTT and stop session."""
        controller = self._config_entry.runtime_data
        did = self._device.device_info["did"]
        controller.unregister_camera_entity(did)
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(asyncio.shield(self._start_task), timeout=2.0)
        await self._stop_session()
        await controller.async_release_kvs_mqtt()

    async def async_turn_on(self) -> None:
        """Start the KVS camera stream."""
        if self._stream_started:
            return
        self._stream_started = True
        self._attr_is_streaming = True
        self.async_write_ha_state()
        self._notify_state_change()
        self._start_task = self.hass.async_create_task(self._start_session_safe())

    async def async_turn_off(self) -> None:
        """Stop the KVS camera stream."""
        if not self._stream_started:
            return
        self._stream_started = False
        self._attr_is_streaming = False
        self.async_write_ha_state()
        self._notify_state_change()
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(asyncio.shield(self._start_task), timeout=2.0)
        await self._stop_session()

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the latest JPEG frame.

        - While stream is active: return the latest frame (or last captured if not yet available).
        - While stream is stopped: return the last captured frame so the entity stays visible.
        - If no frame was ever captured: return the black placeholder.
        """
        session = self._session
        if session is None:
            return self._last_jpeg or _BLACK_JPEG
        if session.is_done():
            # Session ended unexpectedly — stop cleanly
            self._stream_started = False
            self._attr_is_streaming = False
            self.async_write_ha_state()
            self._notify_state_change()
            self.hass.async_create_task(self._stop_session())
            return self._last_jpeg or _BLACK_JPEG
        frame = session.latest_jpeg
        if frame:
            self._last_jpeg = frame
        return frame or self._last_jpeg or _BLACK_JPEG

    # ── Session lifecycle ─────────────────────────────────────────────────────

    async def _start_session_safe(self) -> None:
        """Start a KVS session, handling failures gracefully."""
        async with self._session_lock:
            if self._session is not None and not self._session.is_done():
                return
            try:
                await self._start_session()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Camera session failed to start: %s", err)
                self._stream_started = False
                self._attr_is_streaming = False
                self.async_write_ha_state()
                self._notify_state_change()

    async def _start_session(self) -> None:
        """Initialize and start a new KVS WebRTC session."""
        controller = self._config_entry.runtime_data
        country = self._config_entry.data.get(CONF_COUNTRY, "ww")
        continent = get_continent(country)
        ma_gw = get_ma_gw(continent)

        # Get credentials
        try:
            creds = await controller.authenticator.authenticate()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Camera: authentication failed: %s", err)
            self._stream_started = False
            self._attr_is_streaming = False
            self.async_write_ha_state()
            self._notify_state_change()
            return

        token = creds.token
        user_id = creds.user_id
        user_resource = controller.client_device_id
        did = self._device.device_info["did"]
        mid = self._device.device_info["class"]
        res = self._device.device_info["resource"]

        # Resolve PIN
        pins: dict[str, str] = self._config_entry.options.get(CONF_CAMERA_PINS, {})
        pin_hash = pins.get(did, "")  # empty string = no PIN

        http_session = aiohttp_client.async_get_clientsession(self.hass)

        # Verify PIN if provided
        if pin_hash:
            result = await verify_video_pwd(
                http_session,
                token=token,
                user_id=user_id,
                did=did,
                pin_hash=pin_hash,
                country=country,
                ma_gw=ma_gw,
            )
            if result.get("ret") != "ok":
                _LOGGER.warning(
                    "Camera PIN verification failed for %s: %s", did, result
                )
                self._stream_started = False
                self._attr_is_streaming = False
                self.async_write_ha_state()
                self._notify_state_change()
                return

        # Start KVS session
        video_track_id = generate_video_track_id()
        watch_result = await start_watch_v2(
            http_session,
            token=token,
            user_id=user_id,
            did=did,
            mid=mid,
            res=res,
            pin_hash=pin_hash,
            video_track_id=video_track_id,
            country=country,
            ma_gw=ma_gw,
        )

        if watch_result.get("ret") != "ok":
            _LOGGER.warning(
                "Camera start_watch_v2 failed for %s: %s", did, watch_result
            )
            self._stream_started = False
            self._attr_is_streaming = False
            self.async_write_ha_state()
            self._notify_state_change()
            return

        kvs_creds = watch_result.get("credentials", {})
        region = watch_result.get("region", "")
        channel_name = watch_result.get("channel", "")
        client_id = watch_result.get("client_id", "")
        session_id = watch_result.get("session", "")

        # Register P2P handler on the global KVS MQTT listener
        kvs_mqtt = controller.kvs_mqtt_listener
        if kvs_mqtt is None:
            _LOGGER.warning(
                "Camera %s: KVS MQTT listener not available, cannot start stream", did
            )
            self._stream_started = False
            self._attr_is_streaming = False
            self.async_write_ha_state()
            self._notify_state_change()
            return

        def _on_p2p_req(topic: str, payload: dict) -> None:
            # Cancel any in-flight response task before creating a new one
            if self._p2p_resp_task is not None and not self._p2p_resp_task.done():
                self._p2p_resp_task.cancel()
            self._p2p_resp_task = self.hass.async_create_task(
                kvs_mqtt.send_p2p_data_resp(
                    topic,
                    user_id=user_id,
                    user_resource=user_resource,
                )
            )

        controller.register_kvs_p2p_handler(did, _on_p2p_req)

        self._session = KvsStreamSession(
            hass=self.hass,
            http_session=http_session,
            token=token,
            user_id=user_id,
            user_resource=user_resource,
            did=did,
            mid=mid,
            res=res,
            kvs_creds=kvs_creds,
            region=region,
            channel_name=channel_name,
            client_id=client_id,
            session_id=session_id,
            video_track_id=video_track_id,
            mqtt_listener=kvs_mqtt,
            country=country,
            ma_gw=ma_gw,
        )
        await self._session.start()
        _LOGGER.info("KVS camera session started for %s", did)

    async def _stop_session(self) -> None:
        """Stop the current KVS session and unregister the P2P handler."""
        if self._p2p_resp_task is not None and not self._p2p_resp_task.done():
            self._p2p_resp_task.cancel()
        self._p2p_resp_task = None

        session = self._session
        self._session = None

        # Unregister DID-specific P2P handler from the global listener
        controller = self._config_entry.runtime_data
        did = self._device.device_info["did"]
        controller.unregister_kvs_p2p_handler(did)

        if session is not None:
            try:
                await session.stop()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error stopping KVS session: %s", err)

    def _notify_state_change(self) -> None:
        """Fire a dispatcher signal so companion switch entities can update their state."""
        did = self._device.device_info["did"]
        async_dispatcher_send(
            self.hass,
            CAMERA_STREAM_STATE_SIGNAL.format(did=did),
            self._stream_started,
        )
