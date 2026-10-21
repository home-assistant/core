"""Time platform for the NeoPool integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import time as dt_time
from typing import Any, Literal, override

from neopool_modbus.registers import is_valid_relay_gpio

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_LIGHT,
)
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolDebouncedWriteEntity

# The platform coalesces rapid writes per entity via a debounce timer. Each
# start/stop entity flushes its own endpoint independently, so a platform
# semaphore would only add latency between independent UI interactions.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NeoPoolTimeEntityDescription(TimeEntityDescription):
    """NeoPool time entity description."""

    timer_block: str
    timer_field: Literal["start", "stop"]
    supported_fn: Callable[[dict[str, Any], Mapping[str, Any]], bool] | None = None
    translation_placeholders: dict[str, str] | None = None


def _option_supported(
    opt_flag: str,
) -> Callable[[dict[str, Any], Mapping[str, Any]], bool]:
    """Return a supported_fn gating an entity on the given option flag."""
    return lambda _data, opts: bool(opts.get(opt_flag))


def _light_supported(data: dict[str, Any], opts: Mapping[str, Any]) -> bool:
    """Gate the light timer on its option and a valid lighting GPIO.

    The coordinator skips the relay_light block when the GPIO is invalid.
    """
    return bool(opts.get(CONF_USE_LIGHT)) and is_valid_relay_gpio(
        data.get("MBF_PAR_LIGHTING_GPIO", 0) or 0
    )


# Filtration timers exist on every device; aux and light timers gate on options.
_TIMER_BLOCKS: tuple[tuple[str, str | None, bool], ...] = (
    ("filtration1", None, True),
    ("filtration2", None, False),
    ("filtration3", None, False),
    ("relay_aux1", CONF_USE_AUX1, True),
    ("relay_aux1b", CONF_USE_AUX1, False),
    ("relay_aux2", CONF_USE_AUX2, True),
    ("relay_aux2b", CONF_USE_AUX2, False),
    ("relay_aux3", CONF_USE_AUX3, True),
    ("relay_aux3b", CONF_USE_AUX3, False),
    ("relay_aux4", CONF_USE_AUX4, True),
    ("relay_aux4b", CONF_USE_AUX4, False),
    ("relay_light", CONF_USE_LIGHT, True),
)


def _build_descriptions() -> dict[str, NeoPoolTimeEntityDescription]:
    """Build the timer start/stop descriptions."""
    out: dict[str, NeoPoolTimeEntityDescription] = {}
    for block, opt_flag, enabled_default in _TIMER_BLOCKS:
        for field in ("start", "stop"):
            key = f"{block}_{field}"
            # Filtration and aux blocks share one translation per field with
            # number placeholders; other blocks keep their own key.
            translation_key = key
            placeholders: dict[str, str] | None = None
            if block.startswith("filtration"):
                translation_key = f"filtration_{field}"
                placeholders = {"number": block.removeprefix("filtration")}
            elif block.startswith("relay_aux"):
                translation_key = f"relay_aux_{field}"
                digits = block.removeprefix("relay_aux")
                placeholders = {
                    "number": digits.rstrip("b"),
                    "subtimer": "2" if digits.endswith("b") else "1",
                }
            if block == "relay_light":
                supported_fn: (
                    Callable[[dict[str, Any], Mapping[str, Any]], bool] | None
                ) = _light_supported
            elif opt_flag is not None:
                supported_fn = _option_supported(opt_flag)
            else:
                supported_fn = None
            out[key] = NeoPoolTimeEntityDescription(
                key=key,
                translation_key=translation_key,
                translation_placeholders=placeholders,
                entity_category=EntityCategory.CONFIG,
                entity_registry_enabled_default=enabled_default,
                timer_block=block,
                timer_field=field,
                supported_fn=supported_fn,
            )
    return out


TIME_DESCRIPTIONS: dict[str, NeoPoolTimeEntityDescription] = _build_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool time entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NeoPoolTime(coordinator, key, desc)
        for key, desc in TIME_DESCRIPTIONS.items()
        if desc.supported_fn is None
        or desc.supported_fn(coordinator.data, entry.options)
    )


class NeoPoolTime(NeoPoolDebouncedWriteEntity[int], TimeEntity):
    """NeoPool timer start/stop time entity."""

    entity_description: NeoPoolTimeEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolTimeEntityDescription,
    ) -> None:
        """Initialize the entity."""
        # Filtration and second-aux-subtimer blocks poll only while an entity
        # is enabled, so register the block as coordinator context. Base aux and
        # light poll on their option flag and need none.
        block = description.timer_block
        context = (
            block if (description.supported_fn is None or block.endswith("b")) else None
        )
        super().__init__(coordinator, context=context)
        self.entity_description = description
        self._key = key
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    def _decode_raw(self) -> dt_time | None:
        """Decode the coordinator-data seconds into HH:MM:SS."""
        seconds = self.coordinator.data.get(self._key)
        if seconds is None:
            return None
        try:
            seconds = int(seconds) % 86400
        except TypeError, ValueError:  # pragma: no cover
            return None
        return dt_time(
            hour=seconds // 3600,
            minute=(seconds % 3600) // 60,
            second=seconds % 60,
        )

    @property
    @override
    def native_value(self) -> dt_time | None:
        """Return the optimistic pending time, else the decoded register."""
        if self._pending_value is not None:
            seconds = self._pending_value % 86400
            return dt_time(
                hour=seconds // 3600,
                minute=(seconds % 3600) // 60,
                second=seconds % 60,
            )
        return self._decode_raw()

    @override
    async def async_set_value(self, value: dt_time) -> None:
        """Apply optimistically, then debounce-write to the device."""
        await self._debounced_set(value.hour * 3600 + value.minute * 60 + value.second)

    @override
    async def _write_pending(self, pending: int) -> Mapping[str, Any] | None:
        """Write the settled timer endpoint, skipping a no-op EEPROM cycle."""
        block = self.entity_description.timer_block
        # The library does the read-modify-write, so pass only this entity's
        # endpoint: start -> on, stop -> stop.
        lib_key = "on" if self.entity_description.timer_field == "start" else "stop"
        # Skip the EEPROM cycle if the device already holds this value.
        if (current := self._decode_raw()) is not None and (
            current.hour * 3600 + current.minute * 60 + current.second
            == pending % 86400
        ):
            return None
        # Siblings (start/stop) share the block's register set, so serialize the
        # library's read-modify-write per block.
        async with self.coordinator.timer_write_lock(block):
            await self.coordinator.client.write_timer(block, {lib_key: pending})
        return {self._key: pending}
