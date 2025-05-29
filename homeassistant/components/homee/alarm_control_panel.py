"""The Homee alarm control panel platform."""

from dataclasses import dataclass

from pyHomee.const import AttributeChangedBy, AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, HomeeConfigEntry
from .entity import HomeeEntity
from .helpers import get_name_for_enum

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HomeeAlarmControlPanelEntityDescription(AlarmControlPanelEntityDescription):
    """A class that describes Homee alarm control panel entities."""

    code_arm_required: bool = False
    state_list: list[AlarmControlPanelState]


ALARM_DESCRIPTIONS = {
    AttributeType.HOMEE_MODE: HomeeAlarmControlPanelEntityDescription(
        key="homee_mode",
        code_arm_required=False,
        state_list=[
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_VACATION,
        ],
    )
}


def get_supported_features(
    state_list: list[AlarmControlPanelState],
) -> AlarmControlPanelEntityFeature:
    """Return supported features based on the state list."""
    supported_features = AlarmControlPanelEntityFeature(0)
    if AlarmControlPanelState.ARMED_HOME in state_list:
        supported_features |= AlarmControlPanelEntityFeature.ARM_HOME
    if AlarmControlPanelState.ARMED_AWAY in state_list:
        supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY
    if AlarmControlPanelState.ARMED_NIGHT in state_list:
        supported_features |= AlarmControlPanelEntityFeature.ARM_NIGHT
    if AlarmControlPanelState.ARMED_VACATION in state_list:
        supported_features |= AlarmControlPanelEntityFeature.ARM_VACATION
    return supported_features


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the alarm control panel component."""

    async_add_entities(
        HomeeAlarmPanel(attribute, config_entry, ALARM_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in ALARM_DESCRIPTIONS and attribute.editable
    )


class HomeeAlarmPanel(HomeeEntity, AlarmControlPanelEntity):
    """Representation of a Homee alarm control panel."""

    entity_description: HomeeAlarmControlPanelEntityDescription

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeAlarmControlPanelEntityDescription,
    ) -> None:
        """Initialize a Homee alarm control panel entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_code_arm_required = description.code_arm_required
        self._attr_supported_features = get_supported_features(description.state_list)
        self._attr_translation_key = description.key

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return current state."""
        return self.entity_description.state_list[int(self._attribute.current_value)]

    @property
    def changed_by(self) -> str:
        """Return by whom or what the entity was last changed."""
        changed_by_name = get_name_for_enum(
            AttributeChangedBy, self._attribute.changed_by
        )
        return f"{changed_by_name} - {self._attribute.changed_by_id}"

    async def _async_set_alarm_state(self, state: AlarmControlPanelState) -> None:
        """Set the alarm state."""
        if state in self.entity_description.state_list:
            await self.async_set_homee_value(
                self.entity_description.state_list.index(state)
            )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        # Since disarm is always present in the UI, we raise an error.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="disarm_not_supported",
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_set_alarm_state(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._async_set_alarm_state(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_set_alarm_state(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        await self._async_set_alarm_state(AlarmControlPanelState.ARMED_VACATION)
