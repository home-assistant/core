"""Select platform for choosing a Poolside heater's heating/cooling method."""

from dataclasses import dataclass
from enum import StrEnum
from typing import override

from aiopoolside import PoolsideClient, PoolsideControl
from aiopoolside.const import (
    COOLING_MODE_FIELD,
    COOLING_MODES_SUPPORTED_FIELD,
    HEATING_MODE_FIELD,
    HEATING_MODES_SUPPORTED_FIELD,
    ControlType,
    CoolingMode,
    HeatingMode,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .entity import PoolsideEntity, confirmed_json


@dataclass(frozen=True, kw_only=True)
class PoolsideModeSelectDescription(SelectEntityDescription):
    """Describes one axis of a TEMPERATURE control's mode choices."""

    supported_field: str
    desired_field: str
    wire_modes: type[StrEnum]


MODE_SELECTS = (
    PoolsideModeSelectDescription(
        key="heating_mode",
        translation_key="heating_mode",
        supported_field=HEATING_MODES_SUPPORTED_FIELD,
        desired_field=HEATING_MODE_FIELD,
        wire_modes=HeatingMode,
    ),
    PoolsideModeSelectDescription(
        key="cooling_mode",
        translation_key="cooling_mode",
        supported_field=COOLING_MODES_SUPPORTED_FIELD,
        desired_field=COOLING_MODE_FIELD,
        wire_modes=CoolingMode,
    ),
)


def _reported_options(
    client: PoolsideClient,
    control: PoolsideControl,
    description: PoolsideModeSelectDescription,
) -> list[str]:
    """Return the mode options the equipment reports for this axis, as slugs."""
    raw_modes = confirmed_json(client, control, description.supported_field)
    if not isinstance(raw_modes, list):
        return []
    options: list[str] = []
    for raw_mode in raw_modes:
        try:
            options.append(description.wire_modes(raw_mode).value.lower())
        except ValueError:
            continue
    return options


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up heating/cooling mode selects for TEMPERATURE controls.

    Each select is added the first time its supported-mode list is reported
    non-empty - normally straight from the control layout, but the lists can
    also change via status pushes, so late appearances are handled too.
    Equipment whose list never shows up (e.g. no chiller installed) simply
    never grows the corresponding select.
    """
    data = entry.runtime_data
    client = data.client
    heaters = [
        control
        for control in data.controls
        if control.control_type is ControlType.TEMPERATURE
    ]
    added: set[str] = set()

    @callback
    def _async_add_reported_selects() -> None:
        new_entities: list[PoolsideModeSelect] = []
        for control in heaters:
            for description in MODE_SELECTS:
                added_key = f"{control.uuid}_{description.key}"
                if added_key in added or not _reported_options(
                    client, control, description
                ):
                    continue
                added.add(added_key)
                new_entities.append(PoolsideModeSelect(client, control, description))
        if new_entities:
            async_add_entities(new_entities)

    _async_add_reported_selects()
    for control in heaters:
        for key in {control.status_key, control.uuid, *control.member_uuids}:
            entry.async_on_unload(
                client.subscribe_status(key, _async_add_reported_selects)
            )


class PoolsideModeSelect(PoolsideEntity, SelectEntity):
    """The heating or cooling method a TEMPERATURE control should use.

    The choices are confirmed equipment capabilities (HeatingModesSupported/
    CoolingModesSupported); the selection itself is optimistic-only, like
    SetPoint and ControlMode.
    """

    entity_description: PoolsideModeSelectDescription
    _use_translated_name = True

    def __init__(
        self,
        client: PoolsideClient,
        control: PoolsideControl,
        description: PoolsideModeSelectDescription,
    ) -> None:
        """Set up the select for one mode axis of a TEMPERATURE control."""
        self.entity_description = description
        super().__init__(client, control)
        self._attr_unique_id = (
            f"{client.controller_uuid}_{control.uuid}_{description.key}"
        )
        self._attr_translation_placeholders = {"control_name": control.name}

    @property
    @override
    def options(self) -> list[str]:
        """Return the mode choices the equipment currently reports."""
        return _reported_options(self._client, self._control, self.entity_description)

    @property
    @override
    def available(self) -> bool:
        """Return False while the equipment reports no choices for this axis."""
        return super().available and bool(self.options)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the last-selected mode, if it is still a valid choice."""
        value = self._desired(self.entity_description.desired_field)
        if value is None:
            return None
        option = str(value).lower()
        return option if option in self.options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the chosen mode as the control's desired state."""
        await self._async_write_state(
            **{self.entity_description.desired_field: option.upper()}
        )
