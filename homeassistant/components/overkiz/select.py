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

# Oven core:ModeState values (core:SupportedModes) to translatable options.
OVEN_MODES: dict[str, str] = {
    "defrost": "defrost",
    "bottomHeat": "bottom_heat",
    "bottomFan": "bottom_fan",
    "conventional": "conventional",
    "conventionalFan": "conventional_fan",
    "grillMedium": "grill_medium",
    "grillStrong": "grill_strong",
    "grillPower": "grill_power",
    "fannedGrill": "fanned_grill",
    "keepingWarm": "keeping_warm",
    "fanCooking": "fan_cooking",
    "combinedHeat": "combined_heat",
    "delicateFood": "delicate_food",
    "shabbat": "shabbat",
    "bread": "bread",
    "eco": "eco",
    "auto": "auto",
    "lowTemperature": "low_temperature",
    "catalyticCleaning": "catalytic_cleaning",
    "pyrolitic90Cleaning": "pyrolytic_90_cleaning",
    "pyrolitic105Cleaning": "pyrolytic_105_cleaning",
    "pyrolitic120Cleaning": "pyrolytic_120_cleaning",
    "pyroliticAutoCleaning": "pyrolytic_auto_cleaning",
    "guidedCooking": "guided_cooking",
    "guidedCookingMicrowave": "guided_cooking_microwave",
    "guidedDefrostingMicrowave": "guided_defrosting_microwave",
    "ecoConventional": "eco_conventional",
    "ecoFan": "eco_fan",
    "booster": "booster",
    "pyroliticExpressCleaning": "pyrolytic_express_cleaning",
    "pizza": "pizza",
    "catalyticExpressCleaning": "catalytic_express_cleaning",
    "drying": "drying",
    "guidedSteam": "guided_steam",
    "microwave": "microwave",
    "defrostingMicrowave": "defrosting_microwave",
    "keepingWarmMicrowave": "keeping_warm_microwave",
    "fanCookingMicrowave": "fan_cooking_microwave",
    "grillMicrowave": "grill_microwave",
    "grillVariableMicrowave": "grill_variable_microwave",
    "conventionalMicrowave": "conventional_microwave",
    "heatAndHoldMicrowave": "heat_and_hold_microwave",
    "steam": "steam",
    "defrostingSteam": "defrosting_steam",
    "keepingWarmSteam": "keeping_warm_steam",
    "fanSteam": "fan_steam",
    "grillFanSteam": "grill_fan_steam",
    "conventionalSteam": "conventional_steam",
    "conventionalFanSteam": "conventional_fan_steam",
    "cleaningSteam": "cleaning_steam",
    "emptyingSteam": "emptying_steam",
    "descalingSteam": "descaling_steam",
}


@dataclass(frozen=True, kw_only=True)
class OverkizSelectDescription(SelectEntityDescription):
    """Class to describe an Overkiz select entity."""

    select_option: Callable[[str, Callable[..., Awaitable[None]]], Awaitable[None]]

    # Device state holding the live option list, overriding `options`.
    options_state_name: str | None = None

    # Device state values to option keys.
    options_map: dict[str, str] | None = None

    # Restrict to these device types (UIWidget/UIClass).
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
    # Oven/DynamicOven
    OverkizSelectDescription(
        key=OverkizState.CORE_MODE,
        name="Mode",
        options=list(OVEN_MODES.values()),
        options_state_name=OverkizState.CORE_AVAILABLE_MODES,
        options_map=OVEN_MODES,
        select_option=lambda option, execute_command: execute_command(
            OverkizCommand.SET_MODE, option
        ),
        device_types=[UIClass.OVEN],
        translation_key="oven_mode",
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
        """Return the available options."""
        if self.entity_description.options_state_name and (
            state := self.device.states.get(self.entity_description.options_state_name)
        ):
            return [
                option
                for value in cast(list, state.value) or []
                if (option := self._to_option(str(value))) is not None
            ]

        return self.entity_description.options or []

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if state := self.device.states.get(self.entity_description.key):
            return self._to_option(str(state.value))

        return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if options_map := self.entity_description.options_map:
            option = next(
                value for value, mapped in options_map.items() if mapped == option
            )

        await self.entity_description.select_option(
            option, self.executor.async_execute_command
        )

    def _to_option(self, value: str) -> str | None:
        """Return the option for a device state value."""
        if (options_map := self.entity_description.options_map) is None:
            return value

        return options_map.get(value)
