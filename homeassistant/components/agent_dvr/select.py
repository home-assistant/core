"""PTZ preset select entity for Agent DVR.

Agent DVR's command.cgi has no documented raw pan/tilt/zoom-move command
over REST, only cmd=ptzpresets (list) / cmd=ptzpreset&preset=<name> (move
to a preset configured in Agent DVR itself). This entity exposes exactly
that: a dropdown of the camera's own configured PTZ presets. Continuous
directional PTZ move is implemented separately in button.py, over the
WebRTC channel (see webrtc.py).
"""

import logging
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AgentDVRConfigEntry
from .const import DEVICE_TYPE_CAMERA, DOMAIN
from .coordinator import AgentDVRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PTZ preset selects for cameras that report presets."""
    data = entry.runtime_data
    coordinator = data.coordinator
    client = data.client

    entities = []
    for oid_ot, device in coordinator.data["devices"].items():
        if device["typeID"] != DEVICE_TYPE_CAMERA:
            continue
        oid, ot_id = int(device["id"]), int(device["typeID"])
        presets = await client.get_ptz_presets(oid, ot_id)
        if not presets:
            continue
        entities.append(
            AgentDVRPTZPresetSelect(
                coordinator, client, oid_ot, presets, data.unique_id
            )
        )

    if entities:
        async_add_entities(entities)


class AgentDVRPTZPresetSelect(
    CoordinatorEntity[AgentDVRDataUpdateCoordinator], SelectEntity
):
    """Dropdown to move a PTZ camera to one of its Agent DVR presets."""

    _attr_has_entity_name = True
    _attr_translation_key = "ptz_preset"
    _attr_icon = "mdi:pan"

    def __init__(
        self,
        coordinator: AgentDVRDataUpdateCoordinator,
        client,
        oid_ot: str,
        presets: list[dict],
        server_unique_id: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._client = client
        self._oid_ot = oid_ot
        self._oid = int(coordinator.data["devices"][oid_ot]["id"])
        self._ot = int(coordinator.data["devices"][oid_ot]["typeID"])
        self._attr_options = [p["name"] for p in presets]
        self._attr_current_option = None

        camera_unique_id = f"{server_unique_id}_{self._ot}_{self._oid}"
        self._attr_unique_id = f"{camera_unique_id}_ptz_preset"
        # Same identifiers as the camera entity's device -> grouped together.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, camera_unique_id)})

    @property
    @override
    def available(self) -> bool:
        """Return True if the coordinator has data and the camera is online."""
        device = self.coordinator.data["devices"].get(self._oid_ot)
        return (
            super().available
            and device is not None
            and bool(device.get("data", {}).get("online"))
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Move the camera to the selected preset."""
        await self._client.goto_ptz_preset(self._oid, self._ot, option)
        self._attr_current_option = option
        self.async_write_ha_state()
