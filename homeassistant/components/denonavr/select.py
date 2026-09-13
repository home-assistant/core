"""Support for Denon AVR Audyssey select entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from denonavr import DenonAVR

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DenonavrConfigEntry
from .const import (
    AUTO_STANDBY_OPTIONS,
    CONF_SERIAL_NUMBER,
    DIMMER_OPTIONS,
    DOMAIN,
    ECO_MODE_OPTIONS,
)
from .coordinator import DenonAvrDataUpdateCoordinator
from .entity import DenonAvrPendingValueEntity

# Denon's HTTP/Telnet interface doesn't handle concurrent requests well
# (media_player.py sets this too). Only covers calls targeting multiple
# entities at once - see entity.py's shared receiver lock for repeats
# on one entity, or calls split across this file and switch.py.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DenonAvrSelectEntityDescription(SelectEntityDescription):
    """Describes a Denon AVR select entity."""

    current_option_fn: Callable[[DenonAVR], str | None]
    select_option_fn: Callable[[DenonAVR, str], Coroutine[Any, Any, None]]
    options_fn: Callable[[DenonAVR], list[str]]
    # Whether the setting can currently be changed (e.g. Reference Level
    # Offset requires Dynamic EQ to be on).
    available_fn: Callable[[DenonAVR], bool] = lambda receiver: True
    # Which coordinator drives this entity's polling and post-action
    # confirmation. Audyssey values need their own coordinator since
    # its recurring interval is conditional on "Update Audyssey
    # settings" (see __init__.py); everything else shares the general
    # status coordinator, matching media_player.py's existing interval.
    uses_audyssey_coordinator: bool = False


SELECT_TYPES: tuple[DenonAvrSelectEntityDescription, ...] = (
    DenonAvrSelectEntityDescription(
        key="reference_level_offset",
        translation_key="reference_level_offset",
        name="Reference level offset",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.reference_level_offset,
        options_fn=lambda receiver: receiver.reference_level_offset_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_reflevoffset(
            option
        ),
        available_fn=lambda receiver: bool(receiver.dynamic_eq),
        uses_audyssey_coordinator=True,
    ),
    DenonAvrSelectEntityDescription(
        key="dynamic_volume",
        translation_key="dynamic_volume",
        name="Dynamic volume",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.dynamic_volume,
        options_fn=lambda receiver: receiver.dynamic_volume_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_dynamicvol(option),
        uses_audyssey_coordinator=True,
    ),
    DenonAvrSelectEntityDescription(
        key="multi_eq",
        translation_key="multi_eq",
        name="Multi-EQ",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.multi_eq,
        options_fn=lambda receiver: receiver.multi_eq_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_multieq(option),
        uses_audyssey_coordinator=True,
    ),
    DenonAvrSelectEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        name="Eco mode",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.eco_mode,
        options_fn=lambda receiver: list(ECO_MODE_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_eco_mode(option),
    ),
    DenonAvrSelectEntityDescription(
        key="dimmer",
        translation_key="dimmer",
        name="Dimmer",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.dimmer,
        options_fn=lambda receiver: list(DIMMER_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_dimmer(option),
    ),
    DenonAvrSelectEntityDescription(
        key="auto_standby",
        translation_key="auto_standby",
        name="Auto standby",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.auto_standby,
        options_fn=lambda receiver: list(AUTO_STANDBY_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_auto_standby(option),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR select entities from a config entry."""
    data = config_entry.runtime_data

    if (
        config_entry.data.get(CONF_SERIAL_NUMBER) is not None
        and config_entry.unique_id is not None
    ):
        unique_id_base = config_entry.unique_id
    else:
        unique_id_base = config_entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
    )

    def _coordinator_for(
        description: DenonAvrSelectEntityDescription,
    ) -> DenonAvrDataUpdateCoordinator:
        return (
            data.audyssey_coordinator
            if description.uses_audyssey_coordinator
            else data.coordinator
        )

    async_add_entities(
        DenonAvrSelect(
            _coordinator_for(description), description, unique_id_base, device_info
        )
        for description in SELECT_TYPES
    )


class DenonAvrSelect(DenonAvrPendingValueEntity[str], SelectEntity):
    """Representation of a Denon AVR select entity."""

    entity_description: DenonAvrSelectEntityDescription

    def __init__(
        self,
        coordinator: DenonAvrDataUpdateCoordinator,
        description: DenonAvrSelectEntityDescription,
        unique_id_base: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator, f"{unique_id_base}-{description.key}", device_info
        )
        self.entity_description = description

    @override
    def _read_value(self) -> str | None:
        """Return the receiver's own confirmed value."""
        return self.entity_description.current_option_fn(self._receiver)

    @property
    @override
    def available(self) -> bool:
        """Return True if the receiver reports a value and it can be changed.

        Also False whenever this entity's coordinator's last refresh
        failed - otherwise a receiver that stops responding would keep
        showing its last cached value as if still current, indefinitely.
        """
        if not super().available or self._current_value is None:
            return False
        return self.entity_description.available_fn(self._receiver)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current_value

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self.entity_description.options_fn(self._receiver)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._async_apply_change(
            send=lambda: self.entity_description.select_option_fn(
                self._receiver, option
            ),
            value=option,
            error_label=self.entity_description.key,
        )
