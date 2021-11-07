"""Elmax AlarmControlPanel platform."""

from typing import Any, Mapping, Optional

from elmax_api.exceptions import ElmaxApiError
from elmax_api.model.alarm_status import AlarmStatus
from elmax_api.model.command import AreaCommand
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    AlarmControlPanelEntity,
)
from homeassistant.components.elmax import ElmaxCoordinator, ElmaxEntity
from homeassistant.components.elmax.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.exceptions import HomeAssistantError, IntegrationError
from homeassistant.helpers.typing import HomeAssistantType, StateType


class ElmaxArea(ElmaxEntity, AlarmControlPanelEntity):
    """Elmax Area entity implementation."""

    def __init__(
        self,
        panel: PanelEntry,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ):
        """Construct the object."""
        super().__init__(panel, elmax_device, panel_version, coordinator)

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        if self.transitory_state is not None:
            return self.transitory_state

        if self._device.status == AlarmStatus.TRIGGERED:
            return STATE_ALARM_TRIGGERED
        elif self._device.status == AlarmStatus.ARMED_STANDBY:
            return STATE_ALARM_ARMED_AWAY
        elif self._device.status in (
            AlarmStatus.NOT_ARMED_NOT_TRIGGERED,
            AlarmStatus.NOT_ARMED_NOT_ARMABLE,
        ):
            return STATE_ALARM_DISARMED
        else:
            raise ValueError("Unknown Elmax Alarm status")

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_HOME

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Return extra attributes."""
        attrs = super().extra_state_attributes
        if attrs is None:
            attrs = {}
        else:
            attrs = dict(attrs)
        attrs.update(
            {
                "session_status": str(self._device.status),
                "armed_status": str(self._device.armed_status),
            }
        )
        return attrs

    @property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return False

    @property
    def code_format(self) -> Optional[str]:
        """Regex for code format or None if no code is required."""
        return FORMAT_NUMBER

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command."""
        client = self._coordinator.http_client
        try:
            await client.execute_command(
                endpoint_id=self._device.endpoint_id,
                command=AreaCommand.DISARM,
                extra_payload={"code": code},
            )
            self.transitory_state = STATE_ALARM_DISARMING
        except ElmaxApiError as e:
            if e.status_code == 403:
                raise HomeAssistantError("Invalid disarm code")
            else:
                raise

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command."""
        if self._device.status == AlarmStatus.NOT_ARMED_NOT_ARMABLE:
            raise IntegrationError(f"Cannot ARM {self.name}: check for open gates.")

        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id,
            command=AreaCommand.ARM_TOTALLY,
            extra_payload={"code": code},
        )
        self.transitory_state = STATE_ALARM_ARMING

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command."""
        # This device does not distinguish between away and home.
        # Rely on ARM away implementation instead.
        return await self.async_alarm_arm_away(code=code)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up the Elmax alarm control panel platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status = coordinator.panel_status  # type: PanelStatus
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = []
        for area in panel_status.areas:
            a = ElmaxArea(
                panel=coordinator.panel_entry,
                elmax_device=area,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            if a.unique_id not in known_devices:
                entities.append(a)

        async_add_entities(entities, True)
        known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    coordinator.async_add_listener(_discover_new_devices)

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()


# TODO unload
