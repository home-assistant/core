"""Support for Denon AVR Audyssey select entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from denonavr import DenonAVR
from denonavr.const import MAIN_ZONE
from denonavr.exceptions import DenonAvrError

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
from .entity import DenonAvrPendingValueEntity

_LOGGER = logging.getLogger(__name__)

# Denon's HTTP/Telnet interface doesn't handle concurrent requests well
# (media_player.py sets this too). Only covers calls targeting multiple
# entities at once - see DenonAvrSelect._action_lock for single-entity
# repeats.
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
    # Called after a successful select_option_fn to refresh the
    # receiver's cached value immediately, rather than waiting on this
    # entity's own poll cycle. Unconditional - gating this on the
    # "Update Audyssey settings" option meant those entities never
    # visibly reflected a change made through them.
    refresh_fn: Callable[[DenonAVR], Coroutine[Any, Any, None]] | None = None


SELECT_TYPES: tuple[DenonAvrSelectEntityDescription, ...] = (
    DenonAvrSelectEntityDescription(
        key="reference_level_offset",
        translation_key="reference_level_offset",
        name="Reference level offset",
        icon="mdi:tune-vertical",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.reference_level_offset,
        options_fn=lambda receiver: receiver.reference_level_offset_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_reflevoffset(
            option
        ),
        available_fn=lambda receiver: bool(receiver.dynamic_eq),
        refresh_fn=lambda receiver: receiver.async_update_audyssey(),
    ),
    DenonAvrSelectEntityDescription(
        key="dynamic_volume",
        translation_key="dynamic_volume",
        name="Dynamic volume",
        icon="mdi:volume-vibrate",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.dynamic_volume,
        options_fn=lambda receiver: receiver.dynamic_volume_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_dynamicvol(option),
        refresh_fn=lambda receiver: receiver.async_update_audyssey(),
    ),
    DenonAvrSelectEntityDescription(
        key="multi_eq",
        translation_key="multi_eq",
        name="Multi-EQ",
        icon="mdi:equalizer",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.multi_eq,
        options_fn=lambda receiver: receiver.multi_eq_setting_list,
        select_option_fn=lambda receiver, option: receiver.async_set_multieq(option),
        refresh_fn=lambda receiver: receiver.async_update_audyssey(),
    ),
    DenonAvrSelectEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        name="Eco mode",
        icon="mdi:leaf",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.eco_mode,
        options_fn=lambda receiver: list(ECO_MODE_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_eco_mode(option),
        # No lightweight public refresh exists for this group; the
        # general update is the only properly encapsulated option.
        refresh_fn=lambda receiver: receiver.async_update(),
    ),
    DenonAvrSelectEntityDescription(
        key="dimmer",
        translation_key="dimmer",
        name="Dimmer",
        icon="mdi:brightness-6",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.dimmer,
        options_fn=lambda receiver: list(DIMMER_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_dimmer(option),
        refresh_fn=lambda receiver: receiver.async_update(),
    ),
    DenonAvrSelectEntityDescription(
        key="auto_standby",
        translation_key="auto_standby",
        name="Auto standby",
        icon="mdi:timer-outline",
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda receiver: receiver.auto_standby,
        options_fn=lambda receiver: list(AUTO_STANDBY_OPTIONS),
        select_option_fn=lambda receiver, option: receiver.async_auto_standby(option),
        refresh_fn=lambda receiver: receiver.async_update(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR select entities from a config entry."""
    receiver = config_entry.runtime_data

    # Audyssey/Multi-EQ settings apply to the whole receiver, not per
    # zone, so these entities are only created once, tied to Main Zone.
    main_receiver = receiver.zones[MAIN_ZONE]

    if config_entry.data.get(CONF_SERIAL_NUMBER) is not None:
        unique_id_base = config_entry.unique_id
    else:
        unique_id_base = config_entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
    )

    # Audyssey values are never fetched by the regular poll loop unless
    # Telnet delivers a push update - fetch once so these entities don't
    # start out (and stay) unavailable.
    try:
        await main_receiver.async_update_audyssey()
    except DenonAvrError as err:
        _LOGGER.debug(
            "Could not fetch initial Audyssey status for %s: %s",
            main_receiver.name,
            err,
        )

    async_add_entities(
        DenonAvrSelect(main_receiver, description, unique_id_base, device_info)
        for description in SELECT_TYPES
    )


class DenonAvrSelect(DenonAvrPendingValueEntity[str], SelectEntity):
    """Representation of a Denon AVR select entity."""

    entity_description: DenonAvrSelectEntityDescription

    def __init__(
        self,
        receiver: DenonAVR,
        description: DenonAvrSelectEntityDescription,
        unique_id_base: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(receiver, f"{unique_id_base}-{description.key}", device_info)
        self.entity_description = description

    def _read_value(self) -> str | None:
        """Return the receiver's own confirmed value."""
        return self.entity_description.current_option_fn(self._receiver)

    @property
    def available(self) -> bool:
        """Return True if the receiver reports a value and it can be changed."""
        if self._current_value is None:
            return False
        return self.entity_description.available_fn(self._receiver)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current_value

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self.entity_description.options_fn(self._receiver)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        refresh_fn = self.entity_description.refresh_fn
        await self._async_apply_change(
            send=lambda: self.entity_description.select_option_fn(
                self._receiver, option
            ),
            refresh=(lambda: refresh_fn(self._receiver)) if refresh_fn else None,
            value=option,
            error_label=self.entity_description.key,
        )
