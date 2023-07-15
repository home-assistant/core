"""Support for Ezviz alarm."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyezviz import PyEzvizError
from pyezviz.constants import DefenseModeType

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 0


@dataclass
class EzvizAlarmControlPanelEntityDescriptionMixin:
    """Mixin values for EZVIZ Alarm control panel entities."""

    ezviz_alarm_states: list


@dataclass
class EzvizAlarmControlPanelEntityDescription(
    AlarmControlPanelEntityDescription, EzvizAlarmControlPanelEntityDescriptionMixin
):
    """Describe a EZVIZ Alarm control panel entity."""


ALARM_TYPE = EzvizAlarmControlPanelEntityDescription(
    key="ezviz_alarm",
    translation_key="ezviz_alarm",
    ezviz_alarm_states=[
        None,
        STATE_ALARM_DISARMED,
        STATE_ALARM_ARMED_AWAY,
        STATE_ALARM_ARMED_NIGHT,
    ],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz alarm control panel."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities([EzvizAlarm(coordinator, entry.entry_id)])


class EzvizAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a Ezviz alarm control panel."""

    coordinator: EzvizDataUpdateCoordinator
    entity_description: EzvizAlarmControlPanelEntityDescription
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False

    def __init__(self, coordinator: EzvizDataUpdateCoordinator, entry_id: str) -> None:
        """Initialize alarm control panel entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{ALARM_TYPE.key}"
        self.entity_description = ALARM_TYPE
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, "EZVIZ Alarm")},
            "name": "EZVIZ Alarm",
            "model": "EZVIZ Alarm",
            "manufacturer": MANUFACTURER,
        }
        self._ezviz_alarm_state_number: str = "0"
        self._attr_state = None

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        self.hass.async_add_executor_job(self.update)

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            if self.coordinator.ezviz_client.api_set_defence_mode(
                DefenseModeType.HOME_MODE.value
            ):
                self._attr_state = STATE_ALARM_DISARMED
                self.async_write_ha_state()

        except PyEzvizError as err:
            raise HomeAssistantError("Cannot disarm EZVIZ alarm") from err

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        try:
            if self.coordinator.ezviz_client.api_set_defence_mode(
                DefenseModeType.AWAY_MODE.value
            ):
                self._attr_state = STATE_ALARM_ARMED_AWAY
                self.async_write_ha_state()

        except PyEzvizError as err:
            raise HomeAssistantError("Cannot arm EZVIZ alarm") from err

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        try:
            if self.coordinator.ezviz_client.api_set_defence_mode(
                DefenseModeType.SLEEP_MODE.value
            ):
                self._attr_state = STATE_ALARM_ARMED_NIGHT
                self.async_write_ha_state()

        except PyEzvizError as err:
            raise HomeAssistantError("Cannot arm EZVIZ alarm") from err

    def update(self) -> None:
        """Fetch data from EZVIZ."""
        _LOGGER.debug("Updating %s", self.name)
        try:
            self._ezviz_alarm_state_number = (
                self.coordinator.ezviz_client.get_group_defence_mode()
            )
            _LOGGER.debug(self._ezviz_alarm_state_number)
            self._attr_state = ALARM_TYPE.ezviz_alarm_states[
                int(self._ezviz_alarm_state_number)
            ]

            self.async_write_ha_state()

        except PyEzvizError as error:
            raise HomeAssistantError(
                f"Could not fetch EZVIZ alarm status: {error}"
            ) from error
