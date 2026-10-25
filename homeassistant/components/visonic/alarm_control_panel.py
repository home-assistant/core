"""Create a connection to a Visonic PowerMax or PowerMaster (Alarm Control Panel)."""

from typing import override

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ARM_CODE_AUTO,
    DOMAIN,
    TEXT_CLIENT_VERSION,
    TEXT_DISCONNECTION_COUNT,
    TRANSLATE_EXCEPTION_DISARM_CODE_NOT_ENTERED,
)
from .entity import AlarmBaseLogic
from .utils import to_bool
from .visonic_data_types import VisonicConfigEntry
from .visonic_entity_types import AlarmPanelData
from .visonic_types import AlarmPanelCommand, DeviceType

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VisonicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the alarm control panel."""

    @callback
    def async_add_alarm(alarm_data: AlarmPanelData) -> None:
        """Add Visonic Alarm Panel."""
        alarm = VisonicAlarm(
            entry=entry,
            identifier=alarm_data.identifier,
        )
        async_add_entities([alarm], True)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}",
            async_add_alarm,
        )
    )


class VisonicAlarm(AlarmBaseLogic, AlarmControlPanelEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Representation of a Visonic alarm control panel."""

    # This class only contains specific functions for the alarm entity, common alarm/sensor functions are in AlarmBaseLogic
    #    The method resolution order is important here, the init in AlarmBaseLogic will overwrite variable set in the init of AlarmControlPanelEntity
    #       i.e. the __init__ of AlarmControlPanelEntity will run first and then the __init__ of AlarmBaseLogic, updating settings as needed

    _attr_has_entity_name = True

    _unrecorded_attributes = frozenset(
        {
            TEXT_DISCONNECTION_COUNT,
            TEXT_CLIENT_VERSION,
        }
    )

    # Respond to the user commands

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if self.code_format is not None and code is None:
            # Code required but user has selected the green tick without entering a string
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=TRANSLATE_EXCEPTION_DISARM_CODE_NOT_ENTERED,
                translation_placeholders={
                    "entity": self.name if isinstance(self.name, str) else "Undefined"
                },
            )
        # Send Disarm Command to the panel
        status = await self.coordinator.send_command(AlarmPanelCommand.DISARM, code)
        # Process the status
        self.coordinator.process_command_result(status)

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        command = (
            AlarmPanelCommand.ARM_HOME_INSTANT
            if self.isarmhomeinstant
            else AlarmPanelCommand.ARM_HOME
        )
        # Send Arm Home (Instant) Command to the panel
        status = await self.coordinator.send_command(command, code)
        # Process the status
        self.coordinator.process_command_result(status)

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        command = (
            AlarmPanelCommand.ARM_AWAY_INSTANT
            if self.isarmawayinstant
            else AlarmPanelCommand.ARM_AWAY
        )
        # Send Arm Away (Instant) Command to the panel
        status = await self.coordinator.send_command(command, code)
        # Process the status
        self.coordinator.process_command_result(status)

    # Implement the abstract class
    #   Update local variables accordingly, self.async_write_ha_state() is called outside
    @override
    def update_local(self, entry: VisonicConfigEntry) -> None:
        """Update Panel Settings for Alarms (called automatically by base logic)."""

        # Update HA attributes from PanelStateData
        self._attr_extra_state_attributes = self.panel_state_data.attributes
        self._attr_alarm_state = self.panel_state_data.alarm_state
        self._attr_available = self.panel_state_data.connected

        if self.panel_state_data.connected:
            is_cloud = entry.data[CONF_TYPE] == DeviceType.CLOUD
            # Cloud and PowerLink commands can use a stored panel code.
            self._attr_code_arm_required = (
                not is_cloud
                and not self.panel_state_data.achieved_powerlink
                and not to_bool(entry.options.get(CONF_ARM_CODE_AUTO, False))
            )
            if is_cloud:
                # No need to use keypad, the user entered the user code as part of configuration
                self._attr_code_format = None
            else:
                # Normal Panel Entity
                self._attr_code_format = (
                    None
                    if self.panel_state_data.achieved_powerlink
                    else CodeFormat.NUMBER
                )

            sf = AlarmControlPanelEntityFeature.ARM_AWAY  # add this unconditionally
            sf |= AlarmControlPanelEntityFeature.ARM_HOME if self.isarmhome else 0
            self._attr_supported_features = sf

        else:
            self._attr_supported_features = AlarmControlPanelEntityFeature(0)
            self._attr_code_format = CodeFormat.NUMBER

    # The following functions are copied from the alarm control panel to change cached_property to property,
    #   if the user changes the config flow options then these can change

    @property
    @override
    def code_format(self) -> CodeFormat | None:
        """Code format or None if no code is required."""
        return self._attr_code_format

    @property
    @override
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._attr_code_arm_required

    @property
    @override
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
