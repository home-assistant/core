"""Camera platform for Xthings Cloud."""

import asyncio
from collections import OrderedDict
from typing import Any

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import XthingsCloudCoordinator

# Bound WebRTC caches to avoid unbounded memory growth from delayed candidates.
MAX_PENDING_ICE_CANDIDATES = 50
MAX_CLOSED_WEBRTC_SESSIONS = 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up camera platform."""
    coordinator: XthingsCloudCoordinator = entry.runtime_data
    entities = [
        XthingsCloudCamera(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data.get("type") == "camera"
    ]
    async_add_entities(entities)


class XthingsCloudCamera(CoordinatorEntity[XthingsCloudCoordinator], Camera):
    """Xthings Cloud camera entity."""

    _attr_has_entity_name = True
    _attr_name = None

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
            name=device_data.get("name", "Xthings Camera"),
            manufacturer="Xthings",
            model=device_data.get("model", "Unknown"),
            sw_version=device_data.get("version"),
        )
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._cached_image: bytes | None = None
        self._cached_snapshot_url: str | None = None
        self._snapshot_task: asyncio.Task[None] | None = None
        self._kvs_sessions: dict[str, KvsSignalingClient] = {}
        self._pending_candidates: dict[str, list[RTCIceCandidateInit]] = {}
        self._closed_sessions: OrderedDict[str, None] = OrderedDict()

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return {}

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self.device_data.get("online", False)

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        return self.coordinator.last_update_success and self.device_data.get(
            "online", False
        )

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
            if self._snapshot_task and not self._snapshot_task.done():
                self._snapshot_task.cancel()
            self._snapshot_task = self.hass.async_create_task(
                self._async_update_snapshot(snapshot_url)
            )
        super()._handle_coordinator_update()

    async def _async_update_snapshot(self, snapshot_url: str) -> None:
        image = await self._async_fetch_image(snapshot_url)
        if image:
            self._cached_image = image
            self._cached_snapshot_url = snapshot_url
            self.async_write_ha_state()

    async def _async_fetch_image(self, url: str) -> bytes | None:
        try:
            return await self.coordinator.client.async_get_snapshot(url)
        except XthingsCloudApiError as err:
            LOGGER.debug("Failed to fetch camera snapshot from %s: %s", url, err)
        return None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up tasks and sessions when entity is removed."""
        if self._snapshot_task and not self._snapshot_task.done():
            self._snapshot_task.cancel()

        for session_id in list(self._kvs_sessions):
            self.close_webrtc_session(session_id)

        self._pending_candidates.clear()
        await super().async_will_remove_from_hass()

    # --- WebRTC support (HA 2024.1+ only) ---

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle WebRTC offer via KVS signaling."""
        if session_id in self._kvs_sessions:
            self.close_webrtc_session(session_id)
        self._closed_sessions.pop(session_id, None)

        try:
            kvs_data = await self.coordinator.client.async_get_camera_webrtc(
                self._device_id
            )
            region = kvs_data.get("region")
            channel_arn = kvs_data.get("channel_arn")
            viewer = kvs_data.get("viewer")

            if not all([region, channel_arn, isinstance(viewer, dict)]):
                send_message(
                    WebRTCError(code="kvs_error", message="Invalid KVS credentials")
                )
                return

            if not all(
                key in viewer
                for key in ("AccessKeyId", "SecretAccessKey", "SessionToken")
            ):
                send_message(
                    WebRTCError(
                        code="kvs_error",
                        message="Missing required AWS credentials in viewer data",
                    )
                )
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
                try:
                    send_message(
                        WebRTCCandidate(
                            candidate=RTCIceCandidateInit(
                                candidate=cand.get("candidate", ""),
                                sdp_mid=cand.get("sdpMid"),
                                sdp_m_line_index=cand.get("sdpMLineIndex"),
                            )
                        )
                    )
                except (ValueError, TypeError) as err:
                    LOGGER.debug(
                        "Failed to convert ICE candidate: %s, candidate data: %s",
                        err,
                        cand,
                    )

            answer_sdp = await kvs_client.async_get_answer_sdp(
                offer_sdp,
                on_ice_candidate=_on_ice,
            )

            pending_candidates = self._pending_candidates.get(session_id, [])
            for cand in pending_candidates:
                try:
                    await kvs_client.async_send_ice_candidate(
                        candidate=cand.candidate,
                        sdp_mid=cand.sdp_mid,
                        sdp_m_line_index=cand.sdp_m_line_index,
                    )
                except Exception as err:  # noqa: BLE001
                    LOGGER.warning("Failed to send cached ICE candidate: %s", err)

            # Clear candidates only after attempting to send them all
            self._pending_candidates.pop(session_id, None)

            if answer_sdp:
                send_message(WebRTCAnswer(answer=answer_sdp))
            else:
                send_message(
                    WebRTCError(code="kvs_error", message="No answer SDP from KVS")
                )
                self.close_webrtc_session(session_id)

        except Exception as err:  # noqa: BLE001
            LOGGER.exception("KVS WebRTC failed: %s", err)
            send_message(
                WebRTCError(code="kvs_error", message="WebRTC negotiation failed")
            )
            self.close_webrtc_session(session_id)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Forward ICE candidate to KVS signaling channel."""
        if session_id in self._closed_sessions:
            LOGGER.debug(
                "KVS: Ignoring ICE candidate for closed session %s", session_id
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
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("Failed to send ICE candidate: %s", err)
                self.close_webrtc_session(session_id)
        else:
            candidates = self._pending_candidates.setdefault(session_id, [])
            if len(candidates) < MAX_PENDING_ICE_CANDIDATES:
                candidates.append(candidate)
                LOGGER.debug("KVS: Cached ICE candidate for session %s", session_id)
            else:
                LOGGER.warning(
                    "KVS: Dropped ICE candidate, cache limit reached for session %s",
                    session_id,
                )

    def close_webrtc_session(self, session_id: str) -> None:
        """Close WebRTC session and clean up KVS signaling."""
        self._pending_candidates.pop(session_id, None)
        kvs_client = self._kvs_sessions.pop(session_id, None)

        # Track closed sessions to prevent late candidates from leaking memory
        self._closed_sessions.pop(session_id, None)
        self._closed_sessions[session_id] = None
        # Prevent closed sessions set from growing indefinitely
        if len(self._closed_sessions) > MAX_CLOSED_WEBRTC_SESSIONS:
            self._closed_sessions.popitem(last=False)

        if kvs_client:
            self.hass.async_create_task(kvs_client.async_close())
