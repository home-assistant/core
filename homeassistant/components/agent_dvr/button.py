"""PTZ directional buttons for Agent DVR.

Continuous PTZ move/stop has no REST endpoint either — like recordings, it
only works over the WebRTC data channel (`ptzcommand&field=ptz&value=
ispydir_<N>`). Direction codes were reverse-engineered from the client's
joystick/VR control code and verified live against an ONVIF PTZ camera
with before/after snapshot comparisons for pan/tilt; zoom directions were
confirmed by reading the VR controller's zoom-button handler rather than
by testing zoom live. See webrtc.py for the full protocol notes.

Each button press is a short pulse: move, wait, stop — there is no
press-and-hold concept in Home Assistant's button entity, so this is the
closest practical equivalent to a joystick nudge. Presses are run through
the shared AgentDVRWebRTCPool (see webrtc.py) so repeated presses reuse an
already-open connection instead of paying a fresh ~1-2s WebRTC handshake
every time — that handshake latency, not the move itself, is the main
reason raw PTZ control feels sluggish without pooling.
"""

import asyncio
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AgentDVRConfigEntry, AgentDVRData
from .const import DEVICE_TYPE_CAMERA, DOMAIN
from .webrtc import AgentDVRWebRTCError, AgentDVRWebRTCSession

# (translation_key, icon, ispydir code)
DIRECTIONS = [
    ("ptz_left", "mdi:arrow-left-bold", AgentDVRWebRTCSession.PTZ_LEFT),
    ("ptz_right", "mdi:arrow-right-bold", AgentDVRWebRTCSession.PTZ_RIGHT),
    ("ptz_up", "mdi:arrow-up-bold", AgentDVRWebRTCSession.PTZ_UP),
    ("ptz_down", "mdi:arrow-down-bold", AgentDVRWebRTCSession.PTZ_DOWN),
    ("ptz_zoom_in", "mdi:magnify-plus", AgentDVRWebRTCSession.PTZ_ZOOM_IN),
    ("ptz_zoom_out", "mdi:magnify-minus", AgentDVRWebRTCSession.PTZ_ZOOM_OUT),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PTZ direction buttons for cameras that report PTZ presets."""
    data = entry.runtime_data
    coordinator = data.coordinator
    client = data.client

    entities: list[AgentDVRPTZButton] = []
    for device in coordinator.data["devices"].values():
        if device["typeID"] != DEVICE_TYPE_CAMERA:
            continue
        oid, ot_id = int(device["id"]), int(device["typeID"])
        presets = await client.get_ptz_presets(oid, ot_id)
        if not presets:
            continue
        camera_unique_id = f"{data.unique_id}_{ot_id}_{oid}"
        for translation_key, icon, direction in DIRECTIONS:
            entities.append(
                AgentDVRPTZButton(
                    data, oid, ot_id, camera_unique_id, translation_key, icon, direction
                )
            )

    if entities:
        async_add_entities(entities)


class AgentDVRPTZButton(ButtonEntity):
    """One PTZ direction: pressing it pulses a continuous move, then stops."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: AgentDVRData,
        oid: int,
        ot_id: int,
        camera_unique_id: str,
        translation_key: str,
        icon: str,
        direction: str,
    ) -> None:
        """Initialize the button."""
        self._data = data
        self._oid = oid
        self._ot = ot_id
        self._direction = direction
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"{camera_unique_id}_{translation_key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, camera_unique_id)})

    @override
    async def async_press(self) -> None:
        """Pulse the camera in this direction, then stop it."""

        async def _pulse(session: AgentDVRWebRTCSession) -> None:
            await session.ptz_move(self._oid, self._ot, self._direction)
            await asyncio.sleep(self._data.ptz_pulse_seconds)
            await session.ptz_stop(self._oid, self._ot)

        try:
            await self._data.webrtc_pool.run(_pulse)
        except AgentDVRWebRTCError as err:
            raise HomeAssistantError(f"PTZ move failed: {err}") from err
