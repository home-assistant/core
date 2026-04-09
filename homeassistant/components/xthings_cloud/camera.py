"""Camera platform for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    StreamType,
    WebRTCAnswer,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, LOGGER
from .coordinator import XthingsCloudCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera platform."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        XthingsCloudCamera(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data.get("type") == "camera"
    ]
    async_add_entities(entities)


class XthingsCloudCamera(CoordinatorEntity[XthingsCloudCoordinator], Camera):
    """Xthings Cloud camera entity with WebRTC support."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_data.get("name", "Xthings Camera"),
            manufacturer="Xthings",
            model=device_data.get("model", "Unknown"),
            sw_version=device_data.get("version"),
        )
        self._cached_image: bytes | None = None
        self._cached_snapshot_url: str | None = None
        self._kvs_sessions: dict[str, Any] = {}
        self._pending_candidates: dict[str, list[tuple[str, str | None, int | None]]] = {}

    @property
    def device_data(self) -> dict[str, Any]:
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return {}

    @property
    def is_on(self) -> bool:
        return self.device_data.get("online", False)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.device_data.get("online", False)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera snapshot image."""
        snapshot_url = self.device_data.get("status", {}).get("snapshot_url")
        if not snapshot_url:
            return self._cached_image
        if snapshot_url == self._cached_snapshot_url and self._cached_image:
            return self._cached_image
        image = await self._async_fetch_image(snapshot_url)
        if image:
            self._cached_image = image
            self._cached_snapshot_url = snapshot_url
        return self._cached_image

    def _handle_coordinator_update(self) -> None:
        """Check for new snapshot on coordinator update."""
        snapshot_url = self.device_data.get("status", {}).get("snapshot_url")
        if snapshot_url and snapshot_url != self._cached_snapshot_url:
            self.hass.async_create_task(self._async_update_snapshot(snapshot_url))
        super()._handle_coordinator_update()

    async def _async_update_snapshot(self, snapshot_url: str) -> None:
        image = await self._async_fetch_image(snapshot_url)
        if image:
            self._cached_image = image
            self._cached_snapshot_url = snapshot_url
            self.async_write_ha_state()

    async def _async_fetch_image(self, url: str) -> bytes | None:
        try:
            resp = await self.coordinator.client._session.get(url)
            if resp.status == 200:
                return await resp.read()
        except Exception:  # noqa: BLE001
            LOGGER.debug("Failed to get camera snapshot: %s", self._device_id)
        return None

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle WebRTC offer via KVS signaling for SDP exchange."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        from webrtc_models import RTCIceCandidateInit
        from .kvs_signaling import KvsSignalingClient

        try:
            kvs_data = await self.coordinator.client.async_get_camera_webrtc(self._device_id)
            region = kvs_data.get("region")
            channel_arn = kvs_data.get("channel_arn")
            viewer = kvs_data.get("viewer")

            if not all([region, channel_arn, viewer]):
                send_message(WebRTCError(code="kvs_error", message="Invalid KVS credentials"))
                return

            session = async_get_clientsession(self.hass)
            kvs_client = KvsSignalingClient(
                session=session, region=region,
                channel_arn=channel_arn, credentials=viewer,
            )
            self._kvs_sessions[session_id] = kvs_client

            answer_sdp = await kvs_client.async_get_answer_sdp(offer_sdp, send_message)

            # Send cached ICE candidates
            for cand in self._pending_candidates.pop(session_id, []):
                await kvs_client.async_send_ice_candidate(*cand)

            if answer_sdp:
                send_message(WebRTCAnswer(answer=answer_sdp))
            else:
                send_message(WebRTCError(code="kvs_error", message="No answer SDP from KVS"))

        except Exception as err:  # noqa: BLE001
            LOGGER.error("KVS WebRTC failed: %s", err)
            send_message(WebRTCError(code="kvs_error", message=str(err)))

    async def async_on_webrtc_candidate(self, session_id: str, candidate: Any) -> None:
        """Forward ICE candidate to KVS signaling channel."""
        kvs_client = self._kvs_sessions.get(session_id)
        if kvs_client:
            await kvs_client.async_send_ice_candidate(
                candidate=candidate.candidate,
                sdp_mid=candidate.sdp_mid,
                sdp_mline_index=candidate.sdp_m_line_index,
            )
        else:
            # Cache candidate until signaling connection is established
            self._pending_candidates.setdefault(session_id, []).append(
                (candidate.candidate, candidate.sdp_mid, candidate.sdp_m_line_index)
            )
            LOGGER.debug("KVS: Cached ICE candidate for session %s", session_id)

    def close_webrtc_session(self, session_id: str) -> None:
        """Close WebRTC session and clean up KVS signaling."""
        self._pending_candidates.pop(session_id, None)
        kvs_client = self._kvs_sessions.pop(session_id, None)
        if kvs_client:
            self.hass.async_create_task(kvs_client.async_close())
