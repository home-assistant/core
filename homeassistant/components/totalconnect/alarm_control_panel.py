"""Interfaces with TotalConnect alarm control panels."""

from __future__ import annotations

from total_connect_client import ArmingHelper
from total_connect_client.exceptions import BadResultCodeError, UsercodeInvalid
from total_connect_client.location import TotalConnectLocation

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TotalConnectDataUpdateCoordinator
from .entity import TotalConnectLocationEntity

SERVICE_ALARM_ARM_AWAY_INSTANT = "arm_away_instant"
SERVICE_ALARM_ARM_HOME_INSTANT = "arm_home_instant"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect alarm panels based on a config entry."""
    coordinator: TotalConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TotalConnectAlarm(
            coordinator,
            location,
            partition_id,
        )
        for location in coordinator.client.locations.values()
        for partition_id in location.partitions
    )

    # Set up services
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY_INSTANT,
        {},
        "async_alarm_arm_away_instant",
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME_INSTANT,
        {},
        "async_alarm_arm_home_instant",
    )


class TotalConnectAlarm(TotalConnectLocationEntity, AlarmControlPanelEntity):
    """Represent a TotalConnect alarm panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        location: TotalConnectLocation,
        partition_id: int,
    ) -> None:
        """Initialize the TotalConnect status."""
        super().__init__(coordinator, location)
        self._partition_id = partition_id
        self._partition = self._location.partitions[partition_id]

        """
        Set unique_id to location_id for partition 1 to avoid breaking change
        for most users with new support for partitions.
        Add _# for partition 2 and beyond.
        """
        if partition_id == 1:
            self._attr_name = None
            self._attr_unique_id = str(location.location_id)
        else:
            self._attr_translation_key = "partition"
            self._attr_translation_placeholders = {"partition_id": str(partition_id)}
            self._attr_unique_id = f"{location.location_id}_{partition_id}"

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        attr = {
            "location_id": self._location.location_id,
            "partition": self._partition_id,
            "ac_loss": self._location.ac_loss,
            "low_battery": self._location.low_battery,
            "cover_tampered": self._location.is_cover_tampered(),
            "triggered_source": None,
            "triggered_zone": None,
        }

        if self._partition_id == 1:
            attr["location_name"] = self.device.name
        else:
            attr["location_name"] = f"{self.device.name} partition {self._partition_id}"

        state: str | None = None
        if self._partition.arming_state.is_disarmed():
            state = STATE_ALARM_DISARMED
        elif self._partition.arming_state.is_armed_night():
            state = STATE_ALARM_ARMED_NIGHT
        elif self._partition.arming_state.is_armed_home():
            state = STATE_ALARM_ARMED_HOME
        elif self._partition.arming_state.is_armed_away():
            state = STATE_ALARM_ARMED_AWAY
        elif self._partition.arming_state.is_armed_custom_bypass():
            state = STATE_ALARM_ARMED_CUSTOM_BYPASS
        elif self._partition.arming_state.is_arming():
            state = STATE_ALARM_ARMING
        elif self._partition.arming_state.is_disarming():
            state = STATE_ALARM_DISARMING
        elif self._partition.arming_state.is_triggered_police():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Police/Medical"
        elif self._partition.arming_state.is_triggered_fire():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Fire/Smoke"
        elif self._partition.arming_state.is_triggered_gas():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Carbon Monoxide"

        self._attr_extra_state_attributes = attr

        return state

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self.hass.async_add_executor_job(self._disarm)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not disarm"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to disarm {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _disarm(self, code=None):
        """Disarm synchronous."""
        ArmingHelper(self._partition).disarm()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        try:
            await self.hass.async_add_executor_job(self._arm_home)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not arm home"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm home {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _arm_home(self):
        """Arm home synchronous."""
        ArmingHelper(self._partition).arm_stay()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        try:
            await self.hass.async_add_executor_job(self._arm_away)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not arm away"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm away {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _arm_away(self, code=None):
        """Arm away synchronous."""
        ArmingHelper(self._partition).arm_away()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        try:
            await self.hass.async_add_executor_job(self._arm_night)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not arm night"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm night {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _arm_night(self, code=None):
        """Arm night synchronous."""
        ArmingHelper(self._partition).arm_stay_night()

    async def async_alarm_arm_home_instant(self, code: str | None = None) -> None:
        """Send arm home instant command."""
        try:
            await self.hass.async_add_executor_job(self._arm_home_instant)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not arm home instant"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm home instant {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _arm_home_instant(self):
        """Arm home instant synchronous."""
        ArmingHelper(self._partition).arm_stay_instant()

    async def async_alarm_arm_away_instant(self, code: str | None = None) -> None:
        """Send arm away instant command."""
        try:
            await self.hass.async_add_executor_job(self._arm_away_instant)
        except UsercodeInvalid as error:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "TotalConnect usercode is invalid. Did not arm away instant"
            ) from error
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm away instant {self.device.name}."
            ) from error
        await self.coordinator.async_request_refresh()

    def _arm_away_instant(self, code=None):
        """Arm away instant synchronous."""
        ArmingHelper(self._partition).arm_away_instant()
