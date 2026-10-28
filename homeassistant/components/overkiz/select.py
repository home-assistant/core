"""Support for Overkiz select."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState, UIClass
from pyoverkiz.enums.ui import UIWidget

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OverkizDataConfigEntry
from .const import IGNORED_OVERKIZ_DEVICES
from .entity import OverkizExecutableEntity


@dataclass(frozen=True, kw_only=True)
class OverkizSelectDescription(SelectEntityDescription):
    """Class to describe an Overkiz select entity."""

    select_option: Callable[[str, Callable[..., Awaitable[None]]], Awaitable[None]]

    # When set, the option list is read live from this device state (e.g. the
    # oven advertises its supported modes in core:AvailableModesState) instead
    # of the static description options.
    options_state_name: str | None = None

    # Restrict this entity to the listed device types (UIWidget/UIClass).
    # When omitted, the select applies to any device exposing the state.
    device_types: list[UIWidget | UIClass] | None = None


def _select_option_open_closed_pedestrian(
    option: str, execute_command: Callable[..., Awaitable[None]]
) -> Awaitable[None]:
    """Change the selected option for Open/Closed/Pedestrian."""
    return execute_command(
        {
            OverkizCommandParam.CLOSED: OverkizCommand.CLOSE,
            OverkizCommandParam.OPEN: OverkizCommand.OPEN,
            OverkizCommandParam.PEDESTRIAN: OverkizCommand.SET_PEDESTRIAN_POSITION,
        }[OverkizCommandParam(option)]
    )


def _select_option_open_closed_partial(
    option: str, execute_command: Callable[..., Awaitable[None]]
) -> Awaitable[None]:
    """Change the selected option for Open/Closed/Partial."""
    return execute_command(
        {
            OverkizCommandParam.CLOSED: OverkizCommand.CLOSE,
            OverkizCommandParam.OPEN: OverkizCommand.OPEN,
            OverkizCommandParam.PARTIAL: OverkizCommand.PARTIAL_POSITION,
        }[OverkizCommandParam(option)]
    )


def _select_option_memorized_simple_volume(
    option: str, execute_command: Callable[..., Awaitable[None]]
) -> Awaitable[None]:
    """Change the selected option for Memorized Simple Volume."""
    return execute_command(OverkizCommand.SET_MEMORIZED_SIMPLE_VOLUME, option)


def _select_option_active_zone(
    option: str, execute_command: Callable[..., Awaitable[None]]
) -> Awaitable[None]:
    """Change the selected option for Active Zone(s)."""
    # Turn alarm off when empty zone is selected
    if option == "":
        return execute_command(OverkizCommand.ALARM_OFF)

    return execute_command(OverkizCommand.ALARM_ZONE_ON, option)


SELECT_DESCRIPTIONS: list[OverkizSelectDescription] = [
    OverkizSelectDescription(
        key=OverkizState.CORE_OPEN_CLOSED_PEDESTRIAN,
        name="Position",
        options=[
            OverkizCommandParam.OPEN,
            OverkizCommandParam.PEDESTRIAN,
            OverkizCommandParam.CLOSED,
        ],
        select_option=_select_option_open_closed_pedestrian,
        translation_key="open_closed_pedestrian",
    ),
    OverkizSelectDescription(
        key=OverkizState.CORE_OPEN_CLOSED_PARTIAL,
        name="Position",
        options=[
            OverkizCommandParam.OPEN,
            OverkizCommandParam.PARTIAL,
            OverkizCommandParam.CLOSED,
        ],
        select_option=_select_option_open_closed_partial,
        translation_key="open_closed_partial",
    ),
    OverkizSelectDescription(
        key=OverkizState.IO_MEMORIZED_SIMPLE_VOLUME,
        name="Memorized simple volume",
        options=[OverkizCommandParam.STANDARD, OverkizCommandParam.HIGHEST],
        select_option=_select_option_memorized_simple_volume,
        entity_category=EntityCategory.CONFIG,
        translation_key="memorized_simple_volume",
    ),
    # SomfyHeatingTemperatureInterface
    OverkizSelectDescription(
        key=OverkizState.OVP_HEATING_TEMPERATURE_INTERFACE_OPERATING_MODE,
        name="Operating mode",
        options=[OverkizCommandParam.HEATING, OverkizCommandParam.COOLING],
        select_option=lambda option, execute_command: execute_command(
            OverkizCommand.SET_OPERATING_MODE, option
        ),
        entity_category=EntityCategory.CONFIG,
        translation_key="operating_mode",
    ),
    # StatefulAlarmController
    OverkizSelectDescription(
        key=OverkizState.CORE_ACTIVE_ZONES,
        name="Active zones",
        options=["", "A", "B", "C", "A,B", "B,C", "A,C", "A,B,C"],
        select_option=_select_option_active_zone,
        translation_key="active_zones",
    ),
    # Oven (ogp:Oven) - cooking mode. Options are read live from the oven's
    # core:AvailableModesState, so only modes the appliance supports are shown.
    OverkizSelectDescription(
        key=OverkizState.CORE_MODE,
        name="Mode",
        options_state_name=OverkizState.CORE_AVAILABLE_MODES,
        select_option=lambda option, execute_command: execute_command(
            OverkizCommand.SET_MODE, option
        ),
        device_types=[UIClass.OVEN],
    ),
]

SUPPORTED_STATES = {description.key: description for description in SELECT_DESCRIPTIONS}


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz select from a config entry."""
    data = entry.runtime_data
    entities: list[OverkizSelect] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        entities.extend(
            OverkizSelect(
                device.device_url,
                data.coordinator,
                description,
            )
            for state in device.definition.states
            if (description := SUPPORTED_STATES.get(state))
            and (
                description.device_types is None
                or device.widget in description.device_types
                or device.ui_class in description.device_types
            )
        )

    async_add_entities(entities)


class OverkizSelect(OverkizExecutableEntity, SelectEntity):
    """Representation of an Overkiz Select entity."""

    entity_description: OverkizSelectDescription

    @property
    @override
    def options(self) -> list[str]:
        """Return the available options.

        Read live from a device state when the description declares one,
        otherwise fall back to the static options from the description.
        """
        if self.entity_description.options_state_name and (
            state := self.device.states.get(self.entity_description.options_state_name)
        ):
            return [str(option) for option in cast(list, state.value) or []]

        return self.entity_description.options or []

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if state := self.device.states.get(self.entity_description.key):
            return str(state.value)

        return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_option(
            option, self.executor.async_execute_command
        )
