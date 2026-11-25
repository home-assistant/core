"""The select platform for APsystems local API integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    ApSystemsConfigEntry,
    Lake6Coordinator,
    Lake6Data,
    Lake6RuntimeData,
)
from .entity import Lake6Entity
from .lake6.const import (
    LAKE6_MANUAL_MODES,
    LAKE6_MODE_ATTR_TO_FIELD,
    LAKE6_MODE_STATE_AI,
    LAKE6_OPERATING_MODE_FROM_STATE,
    LAKE6_OPERATING_MODE_TO_STATE,
)


@dataclass(frozen=True, kw_only=True)
class Lake6SelectEntityDescription(SelectEntityDescription):
    """Describes a Lake_6 writable enum."""

    options: list[str]
    value_fn: Callable[[Lake6Data], str | None]


OPERATING_MODE = Lake6SelectEntityDescription(
    key="operating_mode",
    translation_key="operating_mode",
    # ai has to stay in the options: it is the only way current_option can match
    # a device that already runs in AI mode. Without it the frontend shows a
    # blank value and switching away from AI has nothing to compare against.
    options=list(LAKE6_OPERATING_MODE_TO_STATE.values()),
    value_fn=lambda d: d.modes.operating_mode,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform.

    EZ1 has no select entities and the platform is only forwarded for Lake_6
    entries; the guard keeps this a no-op if that ever changes.
    """
    if not isinstance(config_entry.runtime_data, Lake6RuntimeData):
        return
    coordinator = config_entry.runtime_data.coordinator
    add_entities(
        [
            Lake6SelectEntity(coordinator, OPERATING_MODE),
            Lake6ManualModeSelect(coordinator),
        ]
    )


class Lake6SelectEntity(Lake6Entity, SelectEntity):
    """The operating mode selector."""

    entity_description: Lake6SelectEntityDescription

    def __init__(
        self,
        coordinator: Lake6Coordinator,
        entity_description: Lake6SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.device_id}_{entity_description.key}"
        self._attr_options = entity_description.options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the mode reported by `/modes`."""
        return self.entity_description.value_fn(self.coordinator.data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the mode, refusing to enter AI mode."""
        # Re-selecting the current AI value is blocked as well, without a special
        # case, so the result never looks partially successful.
        if option == LAKE6_MODE_STATE_AI:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="ai_mode_set_in_app",
            )
        field = LAKE6_MODE_ATTR_TO_FIELD["operating_mode"]
        await self.coordinator.async_set_modes(
            **{field: LAKE6_OPERATING_MODE_FROM_STATE[option]}
        )


class Lake6ManualModeSelect(Lake6Entity, SelectEntity):
    """Mode of the immediate one-time manual control.

    This select and the two manual-control numbers form a single request split
    into three boxes: nothing is sent until the dispatch button is pressed, so
    picking a mode here only stages it. Standby always sends `power "0"` (§4.7),
    which is why the power entity is unavailable in that mode.

    Priority is the device's highest: while the run lasts it overrides the
    long-term mode and then restores it, so this is not a setting to mirror.
    """

    _attr_translation_key = "manual_control_mode"
    _attr_options = list(LAKE6_MANUAL_MODES)

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the manual control mode selector."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_manual_control_mode"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the staged mode, which is not a `control-panels` field."""
        return self.coordinator.manual_control.mode

    @override
    async def async_select_option(self, option: str) -> None:
        """Stage the mode; the dispatch button is what sends it."""
        await self.coordinator.async_set_manual_control(mode=option)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the device side, so a rejected run stays visible.

        The device answers a well-formed POST even when it ignores the request,
        and it clears `MI1` on its own once the run ends; these two keys are the
        only place where that difference shows up in the UI.
        """
        panel = self.coordinator.data.control_panel
        return {
            "device_running": panel.active,
            "device_windows": [
                f"{window.start:%Y-%m-%d %H:%M}~{window.end:%Y-%m-%d %H:%M}"
                f" {window.power} W"
                for window in panel.windows
            ],
        }
