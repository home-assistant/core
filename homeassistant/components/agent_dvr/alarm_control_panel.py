"""Support for Agent DVR Alarm Control Panels."""

from typing import override

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AgentDVRConfigEntry
from .const import DOMAIN
from .coordinator import AgentDVRDataUpdateCoordinator

CONF_HOME_MODE_NAME = "home"
CONF_AWAY_MODE_NAME = "away"
CONF_NIGHT_MODE_NAME = "night"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Agent DVR Alarm Control Panels."""
    data = entry.runtime_data
    async_add_entities(
        [AgentBaseStation(data.coordinator, data.client, data.unique_id)]
    )


class AgentBaseStation(
    CoordinatorEntity[AgentDVRDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of an Agent DVR Alarm Control Panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: AgentDVRDataUpdateCoordinator, client, unique_id: str
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{unique_id}_CP"
        # Only `identifiers` here: the hub device itself (name, manufacturer,
        # model, sw_version) is pre-created once in __init__.py's
        # async_setup_entry before any platform is set up. Repeating
        # conflicting name/manufacturer/model here would race with that,
        # since platform setup order is not guaranteed.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._active_profile: str | None = None

    @property
    @override
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current alarm state."""
        status = self.coordinator.data.get("status", {})
        armed = status.get("armed")
        if armed is None:
            return None
        if not armed:
            return AlarmControlPanelState.DISARMED

        profile = (self._active_profile or "").lower()
        if profile == CONF_HOME_MODE_NAME:
            return AlarmControlPanelState.ARMED_HOME
        if profile == CONF_NIGHT_MODE_NAME:
            return AlarmControlPanelState.ARMED_NIGHT
        return AlarmControlPanelState.ARMED_AWAY

    @override
    async def async_added_to_hass(self) -> None:
        """Fetch the initial active profile once added."""
        await super().async_added_to_hass()
        await self._refresh_active_profile()

    @override
    def _handle_coordinator_update(self) -> None:
        # Keep the active-profile mirror fresh whenever the main coordinator
        # polls getStatus, so external arm/profile changes (e.g. via the
        # Agent DVR app) are reflected here too.
        self.hass.async_create_task(self._refresh_active_profile_and_write())
        super()._handle_coordinator_update()

    async def _refresh_active_profile_and_write(self) -> None:
        await self._refresh_active_profile()
        self.async_write_ha_state()

    async def _refresh_active_profile(self) -> None:
        for profile in await self._client.get_profiles():
            if profile.get("active"):
                self._active_profile = profile.get("name")
                return
        self._active_profile = None

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._client.disarm()
        await self.coordinator.async_request_refresh()

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_AWAY_MODE_NAME)
        self._active_profile = CONF_AWAY_MODE_NAME
        await self.coordinator.async_request_refresh()

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_HOME_MODE_NAME)
        self._active_profile = CONF_HOME_MODE_NAME
        await self.coordinator.async_request_refresh()

    @override
    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_NIGHT_MODE_NAME)
        self._active_profile = CONF_NIGHT_MODE_NAME
        await self.coordinator.async_request_refresh()
