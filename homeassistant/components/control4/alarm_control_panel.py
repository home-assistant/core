"""Platform for Control4 Alarm Control Panel."""
import asyncio
from datetime import timedelta
import json
import logging

from pyControl4.alarm import C4SecurityPanel
from pyControl4.error_handling import C4Exception
import voluptuous

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4Entity, get_items_of_category
from .const import (
    CONF_ALARM_AWAY_MODE,
    CONF_ALARM_CUSTOM_BYPASS_MODE,
    CONF_ALARM_HOME_MODE,
    CONF_ALARM_NIGHT_MODE,
    CONF_DIRECTOR,
    CONTROL4_ENTITY_TYPE,
    DOMAIN,
)
from .director_utils import director_update_data_multi_variable

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "security"

CONTROL4_ARMED_AWAY_VAR = "AWAY_STATE"
CONTROL4_ARMED_HOME_VAR = "HOME_STATE"
CONTROL4_DISARMED_VAR = "DISARMED_STATE"
CONTROL4_ALARM_STATE_VAR = "ALARM_STATE"
CONTROL4_DISPLAY_TEXT_VAR = "DISPLAY_TEXT"
CONTROL4_TROUBLE_TEXT_VAR = "TROUBLE_TEXT"
CONTROL4_PARTITION_STATE_VAR = "PARTITION_STATE"
CONTROL4_DELAY_TIME_REMAINING_VAR = "DELAY_TIME_REMAINING"
CONTROL4_OPEN_ZONE_COUNT_VAR = "OPEN_ZONE_COUNT"
CONTROL4_ALARM_TYPE_VAR = "ALARM_TYPE"
CONTROL4_ARMED_TYPE_VAR = "ARMED_TYPE"
CONTROL4_LAST_EMERGENCY_VAR = "LAST_EMERGENCY"
CONTROL4_LAST_ARM_FAILURE_VAR = "LAST_ARM_FAILED"

CONTROL4_EXIT_DELAY_STATE = "EXIT_DELAY"
CONTROL4_ENTRY_DELAY_STATE = "ENTRY_DELAY"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Control4 alarm control panels from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    scan_interval = entry_data[CONF_SCAN_INTERVAL]
    _LOGGER.debug(
        "Scan interval = %s",
        scan_interval,
    )

    # Register alarm_control_panel specific service
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        "send_alarm_keystrokes",
        {voluptuous.Required("keystrokes"): cv.string},
        "send_alarm_keystrokes",
    )

    async def async_update_data():
        """Fetch data from Control4 director for alarm control panels."""
        variables = ","
        variables = variables.join(
            [
                CONTROL4_ARMED_AWAY_VAR,
                CONTROL4_ARMED_HOME_VAR,
                CONTROL4_DISARMED_VAR,
                CONTROL4_ALARM_STATE_VAR,
                CONTROL4_DISPLAY_TEXT_VAR,
                CONTROL4_TROUBLE_TEXT_VAR,
                CONTROL4_PARTITION_STATE_VAR,
                CONTROL4_DELAY_TIME_REMAINING_VAR,
                CONTROL4_OPEN_ZONE_COUNT_VAR,
                CONTROL4_ALARM_TYPE_VAR,
                CONTROL4_ARMED_TYPE_VAR,
                CONTROL4_LAST_EMERGENCY_VAR,
                CONTROL4_LAST_ARM_FAILURE_VAR,
            ]
        )
        try:
            return await director_update_data_multi_variable(hass, entry, variables)
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="alarm_control_panel",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    director = entry_data[CONF_DIRECTOR]
    for item in items_of_category:
        if (
            item["type"] == CONTROL4_ENTITY_TYPE
            and item["control"] == CONTROL4_CATEGORY
        ):
            item_name = item["name"]
            item_id = item["id"]
            item_parent_id = item["parentId"]
            item_coordinator = coordinator

            item_setup_info = await director.getItemSetup(item_id)
            item_setup_info = json.loads(item_setup_info)
            item_enabled = item_setup_info["setup"]["enabled"]

            item_manufacturer = None
            item_device_name = None
            item_model = None

            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item["manufacturer"]
                    item_device_name = parent_item["name"]
                    item_model = parent_item["model"]
                    break
            async_add_entities(
                [
                    Control4AlarmControlPanel(
                        entry_data,
                        entry,
                        item_coordinator,
                        item_name,
                        item_id,
                        item_device_name,
                        item_manufacturer,
                        item_model,
                        item_parent_id,
                        item_enabled,
                    )
                ],
                True,
            )


class Control4AlarmControlPanel(Control4Entity, AlarmControlPanelEntity):
    """Control4 alarm control panel entity."""

    def __init__(
        self,
        entry_data: dict,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        idx: int,
        device_name: str,
        device_manufacturer: str,
        device_model: str,
        device_id: int,
        is_enabled: bool,
    ):
        """Initialize Control4 light entity."""
        super().__init__(
            entry_data,
            entry,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )
        self._is_enabled = is_enabled

    def create_api_object(self):
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one, without needing to re-init the entire entity.
        """
        return C4SecurityPanel(self.entry_data[CONF_DIRECTOR], self._idx)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._is_enabled

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return FORMAT_NUMBER

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self.entry_data[CONF_ALARM_AWAY_MODE] is not None:
            flags |= SUPPORT_ALARM_ARM_AWAY
        if self.entry_data[CONF_ALARM_HOME_MODE] is not None:
            flags |= SUPPORT_ALARM_ARM_HOME
        if self.entry_data[CONF_ALARM_NIGHT_MODE] is not None:
            flags |= SUPPORT_ALARM_ARM_NIGHT
        if self.entry_data[CONF_ALARM_CUSTOM_BYPASS_MODE] is not None:
            flags |= SUPPORT_ALARM_ARM_CUSTOM_BYPASS
        return flags

    @property
    def state(self):
        """Return the state of the device."""
        partition_state = self.coordinator.data[self._idx][CONTROL4_PARTITION_STATE_VAR]
        if partition_state == CONTROL4_EXIT_DELAY_STATE:
            return STATE_ALARM_ARMING
        if partition_state == CONTROL4_ENTRY_DELAY_STATE:
            return STATE_ALARM_PENDING

        alarm_state = bool(self.coordinator.data[self._idx][CONTROL4_ALARM_STATE_VAR])
        if alarm_state:
            return STATE_ALARM_TRIGGERED

        disarmed = self.coordinator.data[self._idx][CONTROL4_DISARMED_VAR]
        armed_home = self.coordinator.data[self._idx][CONTROL4_ARMED_HOME_VAR]
        armed_away = self.coordinator.data[self._idx][CONTROL4_ARMED_AWAY_VAR]
        if disarmed == 1:
            return STATE_ALARM_DISARMED
        if armed_home == 1:
            return STATE_ALARM_ARMED_HOME
        if armed_away == 1:
            return STATE_ALARM_ARMED_AWAY

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        all_vars = [
            CONTROL4_DISPLAY_TEXT_VAR,
            CONTROL4_TROUBLE_TEXT_VAR,
            CONTROL4_PARTITION_STATE_VAR,
            CONTROL4_DELAY_TIME_REMAINING_VAR,
            CONTROL4_OPEN_ZONE_COUNT_VAR,
            CONTROL4_ALARM_STATE_VAR,
            CONTROL4_ALARM_TYPE_VAR,
            CONTROL4_ARMED_TYPE_VAR,
            CONTROL4_LAST_EMERGENCY_VAR,
            CONTROL4_LAST_ARM_FAILURE_VAR,
        ]
        for var in all_vars:
            state_attr[var.lower()] = self.coordinator.data[self._idx][var]
        state_attr[CONTROL4_ALARM_STATE_VAR.lower()] = bool(
            self.coordinator.data[self._idx][CONTROL4_ALARM_STATE_VAR]
        )
        return state_attr

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        c4_alarm = self.create_api_object()
        await c4_alarm.setArm(code, self.entry_data[CONF_ALARM_AWAY_MODE])

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        c4_alarm = self.create_api_object()
        await c4_alarm.setArm(code, self.entry_data[CONF_ALARM_HOME_MODE])

    async def async_alarm_arm_night(self, code=None):
        """Send arm home command."""
        c4_alarm = self.create_api_object()
        await c4_alarm.setArm(code, self.entry_data[CONF_ALARM_NIGHT_MODE])

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm home command."""
        c4_alarm = self.create_api_object()
        await c4_alarm.setArm(code, self.entry_data[CONF_ALARM_CUSTOM_BYPASS_MODE])

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        c4_alarm = self.create_api_object()
        await c4_alarm.setDisarm(code)

    async def send_alarm_keystrokes(self, keystrokes):
        """Send custom keystrokes."""
        c4_alarm = self.create_api_object()
        for key in keystrokes:
            await c4_alarm.sendKeyPress(key)
#            await asyncio.sleep(5)
