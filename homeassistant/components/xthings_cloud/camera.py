"""Camera platform for Xthings Cloud."""

from typing import Any

from aiohttp import ClientError
from ha_xthings_cloud import KvsSignalingClient, XthingsCloudApiError
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import XthingsCloudConfigEntry, XthingsCloudCoordinator

KVS_EXCEPTIONS = (
    XthingsCloudApiError,
    ClientError,
    TimeoutError,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XthingsCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up camera platform."""
    coordinator = entry.runtime_data
    entities = [
        XthingsCloudCamera(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data["type"] == "camera"
    ]
    async_add_entities(entities)


class XthingsCloudCamera(CoordinatorEntity[XthingsCloudCoordinator], Camera):
    """Xthings Cloud camera entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the camera."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_data["name"],
            manufacturer="Xthings",
            model=device_data["model"],
            sw_version=device_data.get("version"),
        )
        self._cached_image: bytes | None = None
        self._cached_snapshot_url: str | None = None
        self._kvs_sessions: dict[str, KvsSignalingClient] = {}
        self._pending_candidates: dict[str, list[RTCIceCandidateInit]] = {}
        self._open_sessions: set[str] = set()

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return {}

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return True

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        return (
            super().available
            and self._device_id in self.coordinator.data
            and self.device_data["online"]
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera snapshot image."""
        snapshot_url = self.device_data.get("status", {}).get("snapshot_url")
        if not snapshot_url:
            return None
        if snapshot_url == self._cached_snapshot_url and self._cached_image:
            return self._cached_image
        image = await self._async_fetch_image(snapshot_url)
        if image:
            self._cached_image = image
            self._cached_snapshot_url = snapshot_url
        return image

    async def _async_fetch_image(self, url: str) -> bytes | None:
        """Fetch a snapshot image from the given URL, returning None on failure."""
        try:
            return await self.coordinator.client.async_get_snapshot(url)
        except XthingsCloudApiError as err:
            LOGGER.debug("Failed to fetch camera snapshot from %s: %s", url, err)
        return None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up tasks and sessions when entity is removed."""
        for session_id in list(self._kvs_sessions):
            await self.async_close_webrtc_session(session_id)

        self._pending_candidates.clear()
        await super().async_will_remove_from_hass()

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle WebRTC offer via KVS signaling."""
        if session_id in self._kvs_sessions:
            await self.async_close_webrtc_session(session_id)
        self._open_sessions.add(session_id)

        try:
            kvs_data = await self.coordinator.client.async_get_camera_webrtc(
                self._device_id
            )
            region = kvs_data.get("region")
            channel_arn = kvs_data.get("channel_arn")
            viewer = kvs_data.get("viewer")

            if not region or not channel_arn or not isinstance(viewer, dict):
                send_message(
                    WebRTCError(code="kvs_error", message="Invalid KVS credentials")
                )
                await self.async_close_webrtc_session(session_id)
                return

            if any(
                key not in viewer
                for key in ("AccessKeyId", "SecretAccessKey", "SessionToken")
            ):
                send_message(
                    WebRTCError(
                        code="kvs_error",
                        message="Missing required AWS credentials in viewer data",
                    )
                )
                await self.async_close_webrtc_session(session_id)
                return

            session = async_get_clientsession(self.hass)
            kvs_client = KvsSignalingClient(
                session=session,
                region=region,
                channel_arn=channel_arn,
                credentials=viewer,
            )
            self._kvs_sessions[session_id] = kvs_client

            # Bridge: convert dict ICE candidates to HA WebRTCCandidate objects
            def _on_ice(cand: dict) -> None:
                candidate = cand.get("candidate")
                if not isinstance(candidate, str) or not candidate:
                    LOGGER.debug("Skipping ICE candidate without candidate value")
                    return

                sdp_m_line_index = cand.get("sdpMLineIndex")
                if sdp_m_line_index is not None and (
                    not isinstance(sdp_m_line_index, int) or sdp_m_line_index < 0
                ):
                    LOGGER.debug("Skipping ICE candidate with invalid sdpMLineIndex")
                    return

                send_message(
                    WebRTCCandidate(
                        candidate=RTCIceCandidateInit(
                            candidate=candidate,
                            sdp_mid=cand.get("sdpMid"),
                            sdp_m_line_index=sdp_m_line_index,
                        )
                    )
                )

            answer_sdp = await kvs_client.async_get_answer_sdp(
                offer_sdp,
                on_ice_candidate=_on_ice,
            )

            if not answer_sdp:
                send_message(
                    WebRTCError(code="kvs_error", message="No answer SDP from KVS")
                )
                await self.async_close_webrtc_session(session_id)
                return

            pending_candidates = self._pending_candidates.get(session_id, [])
            for cand in pending_candidates:
                try:
                    await kvs_client.async_send_ice_candidate(
                        candidate=cand.candidate,
                        sdp_mid=cand.sdp_mid,
                        sdp_m_line_index=cand.sdp_m_line_index,
                    )
                except KVS_EXCEPTIONS as err:
                    LOGGER.warning("Failed to send cached ICE candidate: %s", err)

            # Clear candidates only after attempting to send them all
            self._pending_candidates.pop(session_id, None)

            send_message(WebRTCAnswer(answer=answer_sdp))

        except KVS_EXCEPTIONS as err:
            LOGGER.exception("KVS WebRTC failed: %s", err)
            send_message(
                WebRTCError(code="kvs_error", message="WebRTC negotiation failed")
            )
            await self.async_close_webrtc_session(session_id)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Forward ICE candidate to KVS signaling channel."""
        if session_id not in self._open_sessions:
            LOGGER.debug(
                "KVS: Ignoring ICE candidate for unknown session %s", session_id
            )
            return

        kvs_client = self._kvs_sessions.get(session_id)
        if kvs_client:
            try:
                await kvs_client.async_send_ice_candidate(
                    candidate=candidate.candidate,
                    sdp_mid=candidate.sdp_mid,
                    sdp_m_line_index=candidate.sdp_m_line_index,
                )
            except KVS_EXCEPTIONS as err:
                LOGGER.warning("Failed to send ICE candidate: %s", err)
                await self.async_close_webrtc_session(session_id)
        else:
            candidates = self._pending_candidates.setdefault(session_id, [])
            candidates.append(candidate)
            LOGGER.debug("KVS: Cached ICE candidate for session %s", session_id)

    def _remove_webrtc_session(self, session_id: str) -> KvsSignalingClient | None:
        """Remove WebRTC session state and return the KVS client."""
        self._open_sessions.discard(session_id)
        self._pending_candidates.pop(session_id, None)
        return self._kvs_sessions.pop(session_id, None)

    def close_webrtc_session(self, session_id: str) -> None:
        """Close WebRTC session and clean up KVS signaling."""
        kvs_client = self._remove_webrtc_session(session_id)
        if kvs_client:
            self.hass.async_create_task(self._async_close_kvs_client(kvs_client))

    async def async_close_webrtc_session(self, session_id: str) -> None:
        """Close WebRTC session and await KVS signaling cleanup."""
        kvs_client = self._remove_webrtc_session(session_id)
        if kvs_client:
            await self._async_close_kvs_client(kvs_client)

    async def _async_close_kvs_client(self, kvs_client: KvsSignalingClient) -> None:
        """Close a KVS signaling client and log close failures."""
        try:
            await kvs_client.async_close()
        except KVS_EXCEPTIONS as err:
            LOGGER.warning("Failed to close KVS WebRTC session: %s", err)
