# pylint: disable=hass-component-root-import
"""Alarm Control panel module for Olarm."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    CodeFormat,
    const,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ALARM_CODE,
    CONF_DEVICE_FIRMWARE,
    CONF_OLARM_DEVICES,
    DOMAIN,
    LOGGER,
    OLARM_STATE_TO_HA,
    STATE_ALARM_ARMING,
    VERSION,
)
from .coordinator import OlarmCoordinator
from .exceptions import CodeTypeError, ListIndexError


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Olarm alarm control panel from a config entry."""

    entities = []

    for device in hass.data[DOMAIN]["devices"]:
        if device["deviceName"] not in entry.data[CONF_OLARM_DEVICES]:
            continue

        LOGGER.info("Setting up Alarm Panels for device (%s)", device["deviceName"])

        # Getting the instance of the DataCoordinator to update the data from Olarm.
        coordinator: OlarmCoordinator = hass.data[DOMAIN][device["deviceId"]]

        for sensor in coordinator.panel_state:
            LOGGER.info(
                "Setting up area (%s) for device (%s)",
                sensor["name"],
                device["deviceName"],
            )
            alarm_panel = OlarmAlarm(
                coordinator=coordinator,
                sensor_name=sensor["name"],
                state=sensor["state"],
                area=sensor["area_number"],
            )

            entities.append(alarm_panel)

            LOGGER.info(
                "Set up area (%s) for device (%s)",
                sensor["name"],
                device["deviceName"],
            )

    async_add_entities(entities)
    LOGGER.info("Added Olarm Alarm Control Panels for all devices")


class OlarmAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Represents an alarm control panel entity in Home Assistant for an Olarm security zone. It defines the panel's state and attributes, and provides methods for updating them."""

    coordinator: OlarmCoordinator
    _trigger_pgm: Any = None
    _changed_by: str | None = None
    _last_changed: Any | None = None
    _state: str | None = None
    area: int = 1
    _area_trigger: str | None = None
    _last_action: str | None = None
    _post_data: dict | None = None

    def __init__(self, coordinator, sensor_name, state, area) -> None:
        """Initialize the Olarm Alarm Control Panel."""
        LOGGER.info(
            "Initializing Olarm Alarm Control Panel for area (%s) device (%s)",
            sensor_name,
            coordinator.olarm_device_name,
        )
        super().__init__(coordinator)
        self._state = OLARM_STATE_TO_HA.get(state)
        self.sensor_name = sensor_name
        self.area = area
        self.format = None

        if self.coordinator.entry.data[CONF_ALARM_CODE] is not None:
            try:
                int(self.coordinator.entry.data[CONF_ALARM_CODE])
                self.format = CodeFormat.NUMBER

            except CodeTypeError:
                self.format = CodeFormat.TEXT

        for sensor in self.coordinator.pgm_data:
            # Creating a sensor for each zone on the alarm panel.
            if "Radio Alarm" in sensor["name"]:
                self._trigger_pgm = sensor
                break

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.sensor_name + " (" + self.coordinator.olarm_device_name + ")"

    @property
    def code_format(self) -> CodeFormat | None:
        """The format of the code used to authenticate alarm actions."""
        if self.format is None:
            return None

        return self.format

    @property
    def code_arm_required(self) -> bool:
        """Whether a code is needed to authenticate alarm actions."""
        if self.format is None:
            return False

        return True

    @property
    def unique_id(self) -> str:
        """The unique id for this entity sothat it can be managed from the ui."""
        return f"{self.coordinator.olarm_device_id}_" + "_".join(
            self.sensor_name.lower().split(" ")
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this entity."""
        return DeviceInfo(
            manufacturer="Raine Pretorius",
            name=f"Olarm Sensors ({self.coordinator.olarm_device_name})",
            model=self.coordinator.olarm_device_make,
            identifiers={(DOMAIN, self.coordinator.olarm_device_id)},
            sw_version=VERSION,
            hw_version=self.coordinator.entry.data[CONF_DEVICE_FIRMWARE],
        )

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self._state

    @property
    def supported_features(self) -> const.AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        if self.coordinator.olarm_device_make.lower() == "nemtek":
            return const.AlarmControlPanelEntityFeature.ARM_AWAY

        if self._trigger_pgm is None:
            return (
                const.AlarmControlPanelEntityFeature.ARM_AWAY
                | const.AlarmControlPanelEntityFeature.ARM_HOME
                | const.AlarmControlPanelEntityFeature.ARM_NIGHT
            )

        return (
            const.AlarmControlPanelEntityFeature.ARM_AWAY
            | const.AlarmControlPanelEntityFeature.ARM_HOME
            | const.AlarmControlPanelEntityFeature.ARM_NIGHT
            | const.AlarmControlPanelEntityFeature.TRIGGER
        )

    @property
    def supported_functions(self) -> list[str]:
        """Return the list of supported features."""
        if (
            self.coordinator.olarm_device_make.lower() == "nemtek"
            or self.coordinator.olarm_device_make.lower() == "jva"
        ):
            return ["Arm Away", "Disarm"]

        if self._trigger_pgm is not None:
            return ["Arm Away", "Arm Home", "Arm Night", "Trigger"]

        return ["Arm Away", "Arm Home", "Arm Night"]

    @property
    def available(self) -> bool:
        """Whether the entity is available. IE the coordinator updates successfully."""
        return (
            self.coordinator.last_update > datetime.now() - timedelta(minutes=2)
            and self.coordinator.device_online
        )

    @property
    def last_changed(self) -> str | None:
        """Return the last change triggered by."""
        return self.coordinator.area_changes[self.area - 1]["actionCreated"]

    @property
    def should_poll(self) -> bool:
        """Disable polling. Integration will notify Home Assistant on sensor value update."""
        return False

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "last_changed": self.coordinator.area_changes[self.area - 1][
                "actionCreated"
            ],
            "changed_by": self.coordinator.area_changes[self.area - 1]["userFullname"],
            "area_trigger": self._area_trigger,
            "last_action": self.coordinator.area_changes[self.area - 1]["actionCmd"],
            "code_format": self.code_format,
            "area_name": self.sensor_name,
            "area_number": self.area,
            "supported_functions": ", ".join(self.supported_functions),
        }

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send the disarm command to the api."""
        if self.check_code(code):
            LOGGER.info(
                "Area '%s' on Olarm device (%s) has been disarmed",
                self.sensor_name,
                self.coordinator.olarm_device_name,
            )
            await self.coordinator.api.disarm_area(self.area)
            await self.coordinator.async_update_panel_data()
            return None

        LOGGER.error(
            "Invalid code given to disarm area '%s' for Olarm device (%s)",
            self.sensor_name,
            self.coordinator.olarm_device_name,
        )
        return None

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send the stay command to the api."""
        if self.check_code(code):
            self._state = STATE_ALARM_ARMING
            LOGGER.info(
                "Area '%s' on Olarm device (%s) has been set to armed_home (stay)",
                self.sensor_name,
                self.coordinator.olarm_device_name,
            )
            await self.coordinator.api.stay_area(self.area)
            await self.coordinator.async_update_panel_data()
            return None

        LOGGER.error(
            "Invalid code given to set area '%s' to armed home (stay) for Olarm device (%s)",
            self.sensor_name,
            self.coordinator.olarm_device_name,
        )
        return None

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send the arm command to the api."""
        if self.check_code(code):
            self._state = STATE_ALARM_ARMING
            LOGGER.info(
                "Area '%s' on Olarm device (%s) has been set to armed_away (armed)",
                self.sensor_name,
                self.coordinator.olarm_device_name,
            )
            await self.coordinator.api.arm_area(self.area)
            await self.coordinator.async_update_panel_data()
            return None

        LOGGER.error(
            "Invalid code given to set area '%s' to armed_away (Arm) for Olarm device (%s)",
            self.sensor_name,
            self.coordinator.olarm_device_name,
        )
        return None

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send the sleep command to the api."""
        if self.check_code(code):
            self._state = STATE_ALARM_ARMING
            LOGGER.info(
                "Area '%s' on Olarm device (%s) has been set to armed_night (sleep)",
                self.sensor_name,
                self.coordinator.olarm_device_name,
            )
            await self.coordinator.api.sleep_area(self.area)
            await self.coordinator.async_update_panel_data()
            return None

        LOGGER.error(
            "Invalid code given to set area '%s' to armed_night (sleep) for Olarm device (%s)",
            self.sensor_name,
            self.coordinator.olarm_device_name,
        )
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_update(self) -> None:
        """Update the state of the alarm panel from the coordinator."""
        if datetime.now() - self.coordinator.last_update > timedelta(
            seconds=(1.5 * self.coordinator.entry.data[CONF_SCAN_INTERVAL])
        ):
            # Only update the state from the api if it has been more than 1.5 times the scan interval since the last update.
            await self.coordinator.async_update_panel_data()

        # Setting the state.
        try:
            self._state = OLARM_STATE_TO_HA.get(
                self.coordinator.panel_state[self.area - 1]["state"]
            )
        except ListIndexError:
            LOGGER.error("Could not set alarm panel state for %s", self.sensor_name)

        # Setting the area triggers.
        try:
            self._area_trigger = self.coordinator.area_triggers[self.area - 1]
        except ListIndexError:
            LOGGER.error("Could not set area triggers for %s", self.sensor_name)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        if self._trigger_pgm is None:
            raise NotImplementedError()

        self._post_data = {
            "actionCmd": "pgm-close",
            "actionNum": self._trigger_pgm["pgm_number"],
        }

        LOGGER.info("Triggering alarm for %s", self.coordinator.olarm_device_name)
        await self.coordinator.api.send_action(self._post_data)

        await asyncio.sleep(45)
        LOGGER.info("Triggered alarm for %s", self.coordinator.olarm_device_name)

        self._post_data = {
            "actionCmd": "pgm-open",
            "actionNum": self._trigger_pgm["pgm_number"],
        }

        await self.coordinator.api.send_action(self._post_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the state of the alarm panel from the coordinator."""
        # Setting the state.
        try:
            self._state = OLARM_STATE_TO_HA.get(
                self.coordinator.panel_state[self.area - 1]["state"]
            )
        except ListIndexError:
            LOGGER.error("Could not set alarm panel state for %s", self.sensor_name)

        # Setting the area triggers.
        try:
            self._area_trigger = self.coordinator.area_triggers[self.area - 1]
        except ListIndexError:
            LOGGER.error("Could not set area triggers for %s", self.sensor_name)

        super()._handle_coordinator_update()

    def check_code(self, entered_code=None) -> bool:
        """Check the entered code against the setup code."""
        try:
            if (
                entered_code is None
                and self.coordinator.entry.data[CONF_ALARM_CODE] is None
            ):
                return True

            if self.code_format == "number":
                try:
                    checkcode = int(entered_code)
                    return checkcode == int(
                        self.coordinator.entry.data[CONF_ALARM_CODE]
                    )

                except CodeTypeError:
                    return False

            if self.code_format == "text":
                return entered_code == str(self.coordinator.entry.data[CONF_ALARM_CODE])

            return False

        except CodeTypeError:
            return False
