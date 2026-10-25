"""Support for the tone controls of a Monoprice 6 zone home audio controller."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pymonoprice import Monoprice, ZoneStatus

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry, MonopriceRuntimeData
from .const import DOMAIN, SIGNAL_ZONE_UPDATED

PARALLEL_UPDATES = 1

# The amplifier counts from 0, with these values in the middle
TONE_CENTER = 7
BALANCE_CENTER = 10


@dataclass(frozen=True, kw_only=True)
class MonopriceNumberEntityDescription(NumberEntityDescription):
    """Describes a Monoprice zone number entity."""

    value_fn: Callable[[ZoneStatus], int]
    set_fn: Callable[[Monoprice, int, int], None]


NUMBERS: tuple[MonopriceNumberEntityDescription, ...] = (
    MonopriceNumberEntityDescription(
        key="bass",
        translation_key="bass",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_min_value=-TONE_CENTER,
        native_max_value=TONE_CENTER,
        native_step=1,
        value_fn=lambda status: status.bass - TONE_CENTER,
        set_fn=lambda client, zone, value: client.set_bass(zone, value + TONE_CENTER),
    ),
    MonopriceNumberEntityDescription(
        key="treble",
        translation_key="treble",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_min_value=-TONE_CENTER,
        native_max_value=TONE_CENTER,
        native_step=1,
        value_fn=lambda status: status.treble - TONE_CENTER,
        set_fn=lambda client, zone, value: client.set_treble(zone, value + TONE_CENTER),
    ),
    MonopriceNumberEntityDescription(
        key="balance",
        translation_key="balance",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_min_value=-BALANCE_CENTER,
        native_max_value=BALANCE_CENTER,
        native_step=1,
        value_fn=lambda status: status.balance - BALANCE_CENTER,
        set_fn=lambda client, zone, value: client.set_balance(
            zone, value + BALANCE_CENTER
        ),
    ),
)


@callback
def _is_player_enabled(
    entity_registry: er.EntityRegistry, entry_id: str, zone_id: int
) -> bool:
    """Return if the media player of the zone is registered and enabled."""
    player_id = entity_registry.async_get_entity_id(
        MEDIA_PLAYER_DOMAIN, DOMAIN, f"{entry_id}_{zone_id}"
    )
    return player_id is not None and not entity_registry.entities[player_id].disabled


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier number platform."""
    entity_registry = er.async_get(hass)

    entities: list[MonopriceZoneNumber] = []
    for i in range(1, 4):
        for j in range(1, 7):
            zone_id = (i * 10) + j
            if not _is_player_enabled(entity_registry, config_entry.entry_id, zone_id):
                continue
            entities.extend(
                MonopriceZoneNumber(
                    config_entry.runtime_data,
                    config_entry.entry_id,
                    zone_id,
                    description,
                )
                for description in NUMBERS
            )

    async_add_entities(entities)


class MonopriceZoneNumber(NumberEntity):
    """Bass, treble or balance control of a Monoprice amplifier zone."""

    entity_description: MonopriceNumberEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_available = False

    def __init__(
        self,
        runtime_data: MonopriceRuntimeData,
        namespace: str,
        zone_id: int,
        description: MonopriceNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._runtime_data = runtime_data
        self._zone_id = zone_id
        self._signal = SIGNAL_ZONE_UPDATED.format(namespace, zone_id)
        self._attr_unique_id = f"{namespace}_{zone_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{namespace}_{zone_id}")}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the zone updates of the media player."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_zone_update)
        )
        self._update_from_status()

    @callback
    def _update_from_status(self) -> None:
        """Take the power and value from the latest zone status."""
        if (status := self._runtime_data.zone_status.get(self._zone_id)) is None:
            return
        # The amplifier does not apply tone changes to a zone that is off
        self._attr_available = status.power
        self._attr_native_value = self.entity_description.value_fn(status)

    @callback
    def _handle_zone_update(self) -> None:
        """Handle a new status of the zone."""
        self._update_from_status()
        self.async_write_ha_state()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value on the amplifier."""
        await self.hass.async_add_executor_job(
            self.entity_description.set_fn,
            self._runtime_data.client,
            self._zone_id,
            round(value),
        )
        self._attr_native_value = round(value)
        self.async_write_ha_state()
