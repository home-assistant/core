"""The text platform for APsystems local API integration."""

from typing import override

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ApSystemsConfigEntry, Lake6Coordinator, Lake6RuntimeData
from .entity import Lake6Entity
from .lake6.const import (
    LAKE6_MODE_STATE_TIME_OF_USE,
    LAKE6_TOU_TEXT_MAX_LENGTH,
    LAKE6_TOU_TEXT_MAX_RULES,
)
from .lake6.tou import async_write_tou_plan, parse_plan, render_plan

PARALLEL_UPDATES = 1


def _power_dropped_issue_id(device_id: str) -> str:
    """Return the issue id used to report dropped power on `self` rows."""
    return f"tou_power_dropped_{device_id}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text platform.

    EZ1 has no text entities and the platform is only forwarded for Lake_6
    entries; the guard keeps this a no-op if that ever changes.
    """
    if not isinstance(config_entry.runtime_data, Lake6RuntimeData):
        return
    add_entities([Lake6TouPlanText(config_entry.runtime_data.coordinator)])


class Lake6TouPlanText(Lake6Entity, TextEntity):
    """The whole time-of-use schedule in one line.

    Home Assistant has no editable table control, so the schedule is carried by
    a single text box: every rule is one `;` separated chunk of five `|`
    separated fields. `tou.parse_plan` is the authority on that grammar; this
    entity only translates its ValueError into a ServiceValidationError.

    It deliberately carries no `entity_category`: the device page renders the
    entities without a category in Controls first, so the schedule opens at the
    top instead of being buried under Configuration.
    """

    _attr_translation_key = "tou_plan"
    _attr_native_max = LAKE6_TOU_TEXT_MAX_LENGTH

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the schedule text box."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_tou_plan"

    @property
    @override
    def native_value(self) -> str:
        """Return the current schedule rendered as text."""
        return render_plan(self.coordinator.data.modes.tou_rules) or ""

    @property
    @override
    def available(self) -> bool:
        """Expose the schedule only while it can be shown losslessly.

        `time_cfg` has no effect outside time-of-use mode. It is also hidden
        when the device holds rules this text cannot express, or more rules than
        the 255 character state limit fits: submitting a shortened plan would
        silently delete the rest on the device. An empty schedule stays
        editable so the first rule can still be typed in.
        """
        if not super().available:
            return False
        if self.coordinator.data.modes.operating_mode != LAKE6_MODE_STATE_TIME_OF_USE:
            return False
        rules = self.coordinator.data.modes.tou_rules
        if len(rules) > LAKE6_TOU_TEXT_MAX_RULES:
            return False
        return render_plan(rules) is not None

    @override
    async def async_set_value(self, value: str) -> None:
        """Replace the whole schedule after parsing every rule.

        A power value on a `self` row is dropped instead of rejected: the
        schedule is still valid, the user just filled a field the device never
        reads. A repair issue reports it, since the box will now show `-`.
        """
        try:
            rows = parse_plan(value)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="tou_invalid_plan",
                translation_placeholders={"error": str(err)},
            ) from err
        await async_write_tou_plan(self.coordinator, rows)
        ignored = [index for index, row in enumerate(rows, 1) if row.power_ignored]
        issue_id = _power_dropped_issue_id(self.device_id)
        if ignored:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="tou_power_dropped",
                translation_placeholders={
                    "rules": ", ".join(str(index) for index in ignored)
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
