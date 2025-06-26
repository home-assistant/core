"""Support for Olarm Alarm Control Panels."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OlarmConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Olarm Alarm Control Panel platform."""
    coordinator = config_entry.runtime_data

    # cycle through areas and create alarm control panels
    panels: list[OlarmAlarmControlPanel] = []
    if coordinator.device_profile is not None and coordinator.device_state is not None:
        for area_index, area_state in enumerate(coordinator.device_state.get("areas")):
            # Get area label with fallback to area number if not available
            areas_labels = coordinator.device_profile.get("areasLabels", [])
            area_label = (
                areas_labels[area_index]
                if area_index < len(areas_labels)
                else f"Area {area_index + 1}"
            )

            panels.append(
                OlarmAlarmControlPanel(
                    coordinator,
                    config_entry.data["device_id"],
                    area_index,
                    area_state,
                    area_label,
                )
            )

    async_add_entities(panels)


class OlarmAlarmControlPanel(AlarmControlPanelEntity):
    """Define an Olarm Alarm Control Panel."""

    def __init__(
        self, coordinator, device_id, area_index, area_state, area_label
    ) -> None:
        """Init the class."""

        # save reference to coordinator
        self._coordinator = coordinator

        # set attributes
        self._attr_alarm_state = AlarmControlPanelState.DISARMED
        self._attr_code_arm_required = False
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.TRIGGER
        )
        self._attr_has_entity_name = True
        self._attr_name = f"Area {area_index + 1:02} - {area_label}"
        self._attr_unique_id = f"{device_id}.area.{area_index}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.device_name,
            manufacturer="Olarm",
        )

        # custom attributes
        self.device_id = device_id
        self.area_index = area_index
        self.area_state = area_state
        self.area_label = area_label
        self._unsubscribe_dispatcher: Callable[[], None] | None = None

        # handle areas_state if disarm, stay, sleep, alarm etc..
        if self.area_state in ("disarm", "notready"):
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif self.area_state == "stay":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        elif self.area_state == "arm":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        elif self.area_state == "sleep":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        elif self.area_state in ("alarm", "emergency", "fire", "medical"):
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED

        _LOGGER.debug(
            "AlarmControlPanel: init %s -> %s",
            self._attr_name,
            self._attr_alarm_state,
        )

    async def async_added_to_hass(self) -> None:
        """Register the signal listener when the entity is added."""
        await super().async_added_to_hass()
        self._unsubscribe_dispatcher = async_dispatcher_connect(
            self.hass, "olarm_mqtt_update", self._handle_mqtt_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from dispatcher when entity is removed."""
        if self._unsubscribe_dispatcher:
            self._unsubscribe_dispatcher()
        await super().async_will_remove_from_hass()

    def _handle_mqtt_update(self, device_id, device_state, device_links, device_io):
        """Handle state updates from MQTT messages."""

        # check if the device_id is the same as the device_id
        if device_id != self.device_id or device_state is None:
            return

        # update area state
        areas = device_state.get("areas")
        if areas is not None and self.area_index < len(areas):
            self.area_state = areas[self.area_index]
        else:
            return

        # handle areas_state if disarm, stay, sleep, alarm etc..
        if self.area_state in ("disarm", "notready"):
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif self.area_state == "stay":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        elif self.area_state == "arm":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        elif self.area_state == "sleep":
            self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        elif self.area_state in ("alarm", "emergency", "fire", "medical"):
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED

        self.schedule_update_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Handle the 'Disarm' button click."""

        # send command via API
        await self._coordinator.send_device_area_cmd(
            self.device_id, "disarm", self.area_index
        )

        _LOGGER.debug("Disarming alarm area %s", self.area_index)
        self._attr_alarm_state = AlarmControlPanelState.PENDING
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Handle the 'Arm Away' button click."""

        # send command via API
        await self._coordinator.send_device_area_cmd(
            self.device_id, "arm", self.area_index
        )

        _LOGGER.debug("Arming alarm area %s", self.area_index)
        self._attr_alarm_state = AlarmControlPanelState.PENDING
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Handle the 'Arm Home' button click."""

        # send command via API
        await self._coordinator.send_device_area_cmd(
            self.device_id, "stay", self.area_index
        )

        # change state to pending
        _LOGGER.debug("Stay Arming alarm area %s", self.area_index)
        self._attr_alarm_state = AlarmControlPanelState.PENDING
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Handle the 'Arm Home' button click."""

        # send command via API
        await self._coordinator.send_device_area_cmd(
            self.device_id, "sleep", self.area_index
        )

        # change state to pending
        _LOGGER.debug("Sleep Arming alarm area %s", self.area_index)
        self._attr_alarm_state = AlarmControlPanelState.PENDING
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """The name of the area from the Alarm Panel."""
        assert self._attr_name is not None
        return self._attr_name

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the alarm control panel."""
        if self._attr_alarm_state is None:
            return AlarmControlPanelState.DISARMED
        return self._attr_alarm_state
