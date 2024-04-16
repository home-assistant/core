"""Elmax sensor platform."""

from __future__ import annotations

from elmax_api.model.alarm_status import AlarmArmStatus, AlarmStatus
from elmax_api.model.command import AreaCommand
from elmax_api.model.panel import PanelStatus

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import InvalidStateError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElmaxCoordinator
from .common import ElmaxEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elmax area platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status: PanelStatus = coordinator.data
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = [
            ElmaxArea(
                elmax_device=area,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            for area in panel_status.areas
            if area.endpoint_id not in known_devices
        ]

        if entities:
            async_add_entities(entities)
            known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    config_entry.async_on_unload(coordinator.async_add_listener(_discover_new_devices))

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()


class ElmaxArea(ElmaxEntity, AlarmControlPanelEntity):
    """Elmax Area entity implementation."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = False
    _attr_has_entity_name = True
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if self._attr_state == AlarmStatus.NOT_ARMED_NOT_ARMABLE:
            raise InvalidStateError(
                f"Cannot arm {self.name}: please check for open windows/doors first"
            )

        await self.coordinator.http_client.execute_command(
            endpoint_id=self._device.endpoint_id,
            command=AreaCommand.ARM_TOTALLY,
            extra_payload={"code": code},
        )
        await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        # Elmax alarm panels do always require a code to be passed for disarm operations
        if code is None or code == "":
            raise ValueError("Please input the disarm code.")
        await self.coordinator.http_client.execute_command(
            endpoint_id=self._device.endpoint_id,
            command=AreaCommand.DISARM,
            extra_payload={"code": code},
        )
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_state = ALARM_STATE_TO_HA.get(
            self.coordinator.get_area_state(self._device.endpoint_id).armed_status
        )
        super()._handle_coordinator_update()


ALARM_STATE_TO_HA = {
    AlarmArmStatus.ARMED_TOTALLY: STATE_ALARM_ARMED_AWAY,
    AlarmArmStatus.ARMED_P1_P2: STATE_ALARM_ARMED_AWAY,
    AlarmArmStatus.ARMED_P2: STATE_ALARM_ARMED_AWAY,
    AlarmArmStatus.ARMED_P1: STATE_ALARM_ARMED_AWAY,
    AlarmArmStatus.NOT_ARMED: STATE_ALARM_DISARMED,
}
