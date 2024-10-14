"""Elmax sensor platform."""

from __future__ import annotations

from elmax_api.exceptions import ElmaxApiError
from elmax_api.model.alarm_status import AlarmArmStatus, AlarmStatus
from elmax_api.model.command import AreaCommand
from elmax_api.model.panel import PanelStatus

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, InvalidStateError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ElmaxCoordinator
from .entity import ElmaxEntity


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
    _pending_state: AlarmControlPanelState | None = None

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if self._attr_alarm_state == AlarmStatus.NOT_ARMED_NOT_ARMABLE:
            raise InvalidStateError(
                f"Cannot arm {self.name}: please check for open windows/doors first"
            )

        self._pending_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()

        try:
            await self.coordinator.http_client.execute_command(
                endpoint_id=self._device.endpoint_id,
                command=AreaCommand.ARM_TOTALLY,
                extra_payload={"code": code},
            )
        except ElmaxApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="alarm_operation_failed_generic",
                translation_placeholders={"operation": "arm"},
            ) from err
        finally:
            await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        # Elmax alarm panels do always require a code to be passed for disarm operations
        if code is None or code == "":
            raise ValueError("Please input the disarm code.")

        self._pending_state = AlarmControlPanelState.DISARMING
        self.async_write_ha_state()

        try:
            await self.coordinator.http_client.execute_command(
                endpoint_id=self._device.endpoint_id,
                command=AreaCommand.DISARM,
                extra_payload={"code": code},
            )
        except ElmaxApiError as err:
            if err.status_code == 403:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="invalid_disarm_code"
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="alarm_operation_failed_generic",
                translation_placeholders={"operation": "disarm"},
            ) from err
        finally:
            await self.coordinator.async_refresh()

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the entity."""
        if self._pending_state is not None:
            return self._pending_state
        if (
            state := self.coordinator.get_area_state(self._device.endpoint_id)
        ) is not None:
            if state.status == AlarmStatus.TRIGGERED:
                return ALARM_STATE_TO_HA.get(AlarmStatus.TRIGGERED)
            return ALARM_STATE_TO_HA.get(state.armed_status)
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Just reset the local pending_state so that it no longer overrides the one from coordinator.
        self._pending_state = None
        super()._handle_coordinator_update()


ALARM_STATE_TO_HA = {
    AlarmArmStatus.ARMED_TOTALLY: AlarmControlPanelState.ARMED_AWAY,
    AlarmArmStatus.ARMED_P1_P2: AlarmControlPanelState.ARMED_AWAY,
    AlarmArmStatus.ARMED_P2: AlarmControlPanelState.ARMED_AWAY,
    AlarmArmStatus.ARMED_P1: AlarmControlPanelState.ARMED_AWAY,
    AlarmArmStatus.NOT_ARMED: AlarmControlPanelState.DISARMED,
    AlarmStatus.TRIGGERED: AlarmControlPanelState.TRIGGERED,
}
