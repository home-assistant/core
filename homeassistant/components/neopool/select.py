"""Select platform for the NeoPool integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.capabilities import (
    has_filtvalve,
    has_heating_relay,
    has_variable_speed_pump,
    is_hydrolysis_present,
    is_ph_module_present,
    is_redox_module_present,
    is_temperature_active,
)
from neopool_modbus.decoders import (
    CELL_BOOST_MODE_LABELS,
    FILTRATION_MODE_LABELS,
    FILTRATION_SPEED_LABELS,
    decode_cell_boost,
    decode_filtration_speed_slot,
)
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import (
    ConfigKind,
    FiltValveMode,
    RelayKind,
    RelayMode,
    TimerRelayMode,
    is_valid_relay_gpio,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_LIGHT,
    DOMAIN,
    PERIOD_MAP,
    PERIOD_SECONDS_TO_KEY,
)
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

PARALLEL_UPDATES = 1

# Timer-period option for a period of 0: the schedule runs once, never repeating.
# Offered permanently so a timer can always be returned to its non-repeating state.
_NO_REPEAT = "no_repeat"

type _WriteFn = Callable[["NeoPoolSelect", NeoPoolModbusClient, str], Awaitable[None]]
type _OptionsFn = Callable[[dict[str, Any]], list[str]]
type _CurrentOptionFn = Callable[[dict[str, Any]], str | None]


@dataclass(frozen=True, kw_only=True)
class NeoPoolSelectEntityDescription(SelectEntityDescription):
    """Describes a NeoPool select entity."""

    options_map: dict[int, str] = field(default_factory=dict)
    select_type: str | None = None
    config_kind: ConfigKind | None = None
    fallback_suffix: str = ""
    supported_fn: Callable[[dict[str, Any]], bool] | None = None
    write_fn: _WriteFn | None = None
    options_fn: _OptionsFn | None = None
    current_option_fn: _CurrentOptionFn | None = None
    translation_placeholders: dict[str, str] | None = None


def _filt_mode_options(data: dict[str, Any]) -> list[str]:
    """Narrow the filtration mode option list based on detected hardware."""
    option_keys = list(FILTRATION_MODE_LABELS.keys())
    no_heating = not has_heating_relay(data)
    temp_inactive = not is_temperature_active(data)
    if no_heating or temp_inactive:
        # Remove keys for "heating" (2) and "intelligent" (4)
        option_keys = [k for k in option_keys if k not in (2, 4)]
    if temp_inactive:
        # Remove key for "smart"
        option_keys = [k for k in option_keys if k != 3]

    # Backwash (13) is display-only: show it only when the device reports it.
    if data.get("MBF_PAR_FILT_MODE") != 13:
        option_keys = [k for k in option_keys if k != 13]

    return [FILTRATION_MODE_LABELS[k] for k in option_keys]


def _cell_boost_options(data: dict[str, Any]) -> list[str]:
    """Drop the active_redox option when no redox module is detected."""
    option_keys = list(CELL_BOOST_MODE_LABELS.keys())
    if not is_redox_module_present(data):
        option_keys = [k for k in option_keys if k != 2]
    return [CELL_BOOST_MODE_LABELS[k] for k in option_keys]


def _decode_cell_boost(data: dict[str, Any]) -> str | None:
    """Surface the current cell boost mode via the lib decoder."""
    reg_val = data.get("MBF_CELL_BOOST")
    if reg_val is None:  # pragma: no cover - register always present once polled
        return None
    return decode_cell_boost(reg_val) or CELL_BOOST_MODE_LABELS[0]


def _make_filtration_speed_decoder(slot: int) -> _CurrentOptionFn:
    """Build a decoder that reads a filtration-speed slot from FILTRATION_CONF."""

    def _decode(data: dict[str, Any]) -> str | None:
        return decode_filtration_speed_slot(data.get("MBF_PAR_FILTRATION_CONF"), slot)

    return _decode


def _resolve_config_value(
    desc: NeoPoolSelectEntityDescription, option: str
) -> int | None:
    """Reverse-lookup the option label to its register value, or None if unmapped."""
    reverse_map = {v: k for k, v in desc.options_map.items()}
    value = reverse_map.get(option)
    if value is None:
        try:  # pragma: no cover - mapped_register options cover every value
            value = int(option.rstrip("ms"))
        except ValueError:  # pragma: no cover - option list is numeric
            return None
    return value


def _commit_config_value(entity: NeoPoolSelect, value: int) -> None:
    """Apply the optimistic update and request a follow-up refresh."""
    overrides = entity.apply_optimistic_update(value)
    entity.coordinator.async_set_updated_data({**entity.coordinator.data, **overrides})
    entity.coordinator.request_refresh_with_followup()


async def _write_config_option(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Reverse-lookup the option label and write it through async_set_config_option."""
    desc = entity.entity_description
    if desc.config_kind is None:  # pragma: no cover - description validated upstream
        return
    value = _resolve_config_value(desc, option)
    if value is None:  # pragma: no cover - mapped_register options cover every value
        return
    await client.async_set_config_option(desc.config_kind, value)
    _commit_config_value(entity, value)


async def _write_relay_activation_delay(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Write the relay activation delay via the lib, which owns the +10 s offset."""
    value = _resolve_config_value(entity.entity_description, option)
    if value is None:  # pragma: no cover - mapped_register options cover every value
        return
    await client.async_set_relay_activation_delay(value)
    _commit_config_value(entity, value)


async def _write_timer_period(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Update the repeat period of a timer via the library's write_timer."""
    timer_name = entity.entity_description.key.rsplit("_", 1)[0]
    if option == _NO_REPEAT:
        period_value = 0
    else:
        # options surfaces an off-map device period as a raw-seconds string, so
        # accept that back as seconds instead of indexing PERIOD_MAP blindly.
        period_value = PERIOD_MAP.get(option, 0) or int(option)
    # write_timer rewrites the whole block, so serialize it per block.
    async with entity.coordinator.timer_write_lock(timer_name):
        await client.write_timer(timer_name, {"period": period_value})
    entity.coordinator.request_refresh_with_followup()


# Map entity keys like "relay_aux1_mode" to the library RelayKind enum. The
# entity key is the timer-block name (without the "_mode" suffix) which the
# library already normalises inside async_set_relay_mode.
_RELAY_MODE_ENTITY_KIND: dict[str, RelayKind] = {
    "relay_aux1_mode": RelayKind.AUX1,
    "relay_aux2_mode": RelayKind.AUX2,
    "relay_aux3_mode": RelayKind.AUX3,
    "relay_aux4_mode": RelayKind.AUX4,
    "relay_light_mode": RelayKind.LIGHT,
}


async def _write_relay_mode(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Switch the relay between automatic (timer-driven) and manual modes."""
    if option not in ("auto", "manual"):
        # disabled and auto_linked are read-only states, not writable targets.
        return
    timer_name = entity.entity_description.key.rsplit("_", 1)[0]
    current = int(entity.coordinator.data.get(f"{timer_name}_enable", 0) or 0)
    if option == "manual" and current in (
        TimerRelayMode.ALWAYS_ON,
        TimerRelayMode.ALWAYS_OFF,
    ):
        # Already in a manual mode; do not touch the physical relay state.
        return
    relay = _RELAY_MODE_ENTITY_KIND[entity.entity_description.key]
    mode = RelayMode.AUTO if option == "auto" else RelayMode.ALWAYS_OFF
    # async_set_relay_mode rewrites the whole block, so serialize it per block.
    async with entity.coordinator.timer_write_lock(timer_name):
        overrides = await client.async_set_relay_mode(relay, mode)
    entity.coordinator.async_set_updated_data({**entity.coordinator.data, **overrides})
    entity.coordinator.request_refresh_with_followup()


async def _write_filtvalve_mode(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Switch the filter valve between automatic and manual modes."""
    if option not in ("auto", "manual"):
        # disabled is a read-only state (uninitialised valve), not a writable target.
        return
    current = int(entity.coordinator.data.get("MBF_PAR_FILTVALVE_MODE", 0) or 0)
    if option == "manual" and current in (
        FiltValveMode.ALWAYS_ON,
        FiltValveMode.ALWAYS_OFF,
    ):
        # Already in a manual mode; do not touch the physical valve state.
        return
    mode = FiltValveMode.AUTO if option == "auto" else FiltValveMode.ALWAYS_OFF
    overrides = await client.async_set_filtvalve_mode(mode) or {}
    entity.coordinator.async_set_updated_data({**entity.coordinator.data, **overrides})
    entity.coordinator.request_refresh_with_followup()


async def _write_cell_boost(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Encode the cell boost mode into the composite cell-status register."""
    await client.async_set_cell_boost(option)
    entity.coordinator.request_refresh_with_followup()


async def _write_filtration_speed(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Pack the live filtration speed into the composite filtration_conf register."""
    if entity.coordinator.data.get("MBF_PAR_FILT_MODE") != 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="filtration_speed_not_manual_mode",
        )
    await client.async_set_filtration_speed(option)
    entity.coordinator.request_refresh_with_followup()


async def _write_filtration_speed_timer(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Pack a per-timer filtration speed into the composite filtration_conf register."""
    timer = int(
        entity.entity_description.key.removeprefix("filtration").removesuffix("_speed")
    )
    await client.async_set_filtration_speed_timer(timer, option)
    entity.coordinator.request_refresh_with_followup()


async def _write_filt_mode(
    entity: NeoPoolSelect, client: NeoPoolModbusClient, option: str
) -> None:
    """Drive the MBF_PAR_FILT_MODE transition.

    The library sequences the manual-mode exit (pump off + settle delay)
    before the mode change, so the platform issues a single write.
    """
    if option == "backwash":
        # backwash is display-only, so reselecting it is a no-op.
        return
    await client.async_set_filtration_mode(option)
    value = next(
        (k for k, v in entity.entity_description.options_map.items() if v == option),
        None,
    )
    overrides = entity.apply_optimistic_update(value)
    entity.coordinator.async_set_updated_data({**entity.coordinator.data, **overrides})
    entity.coordinator.request_refresh_with_followup()


def _light_gpio_supported(data: dict[str, Any]) -> bool:
    """Gate light timer selects on a valid lighting relay GPIO.

    The coordinator skips the relay_light block when the GPIO is invalid, so
    without this gate the entity would be created and stay permanently unknown.
    """
    return is_valid_relay_gpio(data.get("MBF_PAR_LIGHTING_GPIO", 0) or 0)


SELECT_DESCRIPTIONS: dict[str, NeoPoolSelectEntityDescription] = {
    "MBF_PAR_FILT_MODE": NeoPoolSelectEntityDescription(
        key="MBF_PAR_FILT_MODE",
        translation_key="filt_mode",
        options_map=FILTRATION_MODE_LABELS,
        write_fn=_write_filt_mode,
        options_fn=_filt_mode_options,
    ),
    "MBF_PAR_FILTRATION_SPEED": NeoPoolSelectEntityDescription(
        key="MBF_PAR_FILTRATION_SPEED",
        translation_key="filtration_speed",
        options_map=FILTRATION_SPEED_LABELS,
        supported_fn=has_variable_speed_pump,
        write_fn=_write_filtration_speed,
        current_option_fn=_make_filtration_speed_decoder(0),
    ),
    "MBF_CELL_BOOST": NeoPoolSelectEntityDescription(
        key="MBF_CELL_BOOST",
        translation_key="cell_boost",
        options_map=CELL_BOOST_MODE_LABELS,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
        write_fn=_write_cell_boost,
        options_fn=_cell_boost_options,
        current_option_fn=_decode_cell_boost,
    ),
    "MBF_PAR_FILTVALVE_MODE": NeoPoolSelectEntityDescription(
        key="MBF_PAR_FILTVALVE_MODE",
        translation_key="filtvalve_mode",
        options_map={1: "auto", 4: "manual"},
        select_type="filtvalve_mode",
        supported_fn=has_filtvalve,
        write_fn=_write_filtvalve_mode,
    ),
    "MBF_PAR_FILTVALVE_PERIOD_MINUTES": NeoPoolSelectEntityDescription(
        key="MBF_PAR_FILTVALVE_PERIOD_MINUTES",
        translation_key="filtvalve_period_minutes",
        entity_category=EntityCategory.CONFIG,
        select_type="mapped_register",
        fallback_suffix="m",
        options_map={
            1440: "1_day",
            2880: "2_days",
            4320: "3_days",
            5760: "4_days",
            7200: "5_days",
            10080: "1_week",
            20160: "2_weeks",
            30240: "3_weeks",
            40320: "4_weeks",
        },
        config_kind=ConfigKind.FILTVALVE_PERIOD_MINUTES,
        supported_fn=has_filtvalve,
        write_fn=_write_config_option,
    ),
    "MBF_PAR_FILTVALVE_INTERVAL": NeoPoolSelectEntityDescription(
        key="MBF_PAR_FILTVALVE_INTERVAL",
        translation_key="filtvalve_interval",
        entity_category=EntityCategory.CONFIG,
        select_type="mapped_register",
        fallback_suffix="s",
        options_map={
            30: "30s",
            60: "60s",
            90: "90s",
            120: "120s",
            150: "150s",
            180: "180s",
            240: "240s",
            300: "300s",
        },
        config_kind=ConfigKind.FILTVALVE_INTERVAL,
        supported_fn=has_filtvalve,
        write_fn=_write_config_option,
    ),
    "MBF_PAR_INTELLIGENT_FILT_MIN_TIME": NeoPoolSelectEntityDescription(
        key="MBF_PAR_INTELLIGENT_FILT_MIN_TIME",
        translation_key="intelligent_filt_min_time",
        entity_category=EntityCategory.CONFIG,
        select_type="mapped_register",
        fallback_suffix="m",
        options_map={
            120: "2h",
            180: "3h",
            240: "4h",
            300: "5h",
            360: "6h",
            420: "7h",
            480: "8h",
            540: "9h",
            600: "10h",
            660: "11h",
            720: "12h",
        },
        config_kind=ConfigKind.INTELLIGENT_FILT_MIN_TIME,
        supported_fn=lambda data: (
            has_heating_relay(data) and is_temperature_active(data)
        ),
        write_fn=_write_config_option,
    ),
    "MBF_PAR_RELAY_ACTIVATION_DELAY": NeoPoolSelectEntityDescription(
        key="MBF_PAR_RELAY_ACTIVATION_DELAY",
        translation_key="relay_activation_delay",
        entity_category=EntityCategory.CONFIG,
        select_type="mapped_register",
        options_map={
            10: "10",
            20: "20",
            30: "30",
            40: "40",
            50: "50",
            60: "60",
            120: "120",
            180: "180",
            300: "300",
            900: "900",
            1800: "1800",
            3600: "3600",
            10800: "10800",
        },
        config_kind=ConfigKind.RELAY_ACTIVATION_DELAY,
        supported_fn=is_ph_module_present,
        write_fn=_write_relay_activation_delay,
    ),
    "filtration1_speed": NeoPoolSelectEntityDescription(
        key="filtration1_speed",
        translation_key="filtration_speed_timer",
        translation_placeholders={"number": "1"},
        entity_category=EntityCategory.CONFIG,
        options_map=FILTRATION_SPEED_LABELS,
        supported_fn=has_variable_speed_pump,
        write_fn=_write_filtration_speed_timer,
        current_option_fn=_make_filtration_speed_decoder(1),
    ),
    "filtration2_speed": NeoPoolSelectEntityDescription(
        key="filtration2_speed",
        translation_key="filtration_speed_timer",
        translation_placeholders={"number": "2"},
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options_map=FILTRATION_SPEED_LABELS,
        supported_fn=has_variable_speed_pump,
        write_fn=_write_filtration_speed_timer,
        current_option_fn=_make_filtration_speed_decoder(2),
    ),
    "filtration3_speed": NeoPoolSelectEntityDescription(
        key="filtration3_speed",
        translation_key="filtration_speed_timer",
        translation_placeholders={"number": "3"},
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options_map=FILTRATION_SPEED_LABELS,
        supported_fn=has_variable_speed_pump,
        write_fn=_write_filtration_speed_timer,
        current_option_fn=_make_filtration_speed_decoder(3),
    ),
    "relay_aux1_period": NeoPoolSelectEntityDescription(
        key="relay_aux1_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "1", "subtimer": "1"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        write_fn=_write_timer_period,
    ),
    "relay_aux1b_period": NeoPoolSelectEntityDescription(
        key="relay_aux1b_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "1", "subtimer": "2"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        entity_registry_enabled_default=False,
        write_fn=_write_timer_period,
    ),
    "relay_aux2_period": NeoPoolSelectEntityDescription(
        key="relay_aux2_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "2", "subtimer": "1"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        write_fn=_write_timer_period,
    ),
    "relay_aux2b_period": NeoPoolSelectEntityDescription(
        key="relay_aux2b_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "2", "subtimer": "2"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        entity_registry_enabled_default=False,
        write_fn=_write_timer_period,
    ),
    "relay_aux3_period": NeoPoolSelectEntityDescription(
        key="relay_aux3_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "3", "subtimer": "1"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        write_fn=_write_timer_period,
    ),
    "relay_aux3b_period": NeoPoolSelectEntityDescription(
        key="relay_aux3b_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "3", "subtimer": "2"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        entity_registry_enabled_default=False,
        write_fn=_write_timer_period,
    ),
    "relay_aux4_period": NeoPoolSelectEntityDescription(
        key="relay_aux4_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "4", "subtimer": "1"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        write_fn=_write_timer_period,
    ),
    "relay_aux4b_period": NeoPoolSelectEntityDescription(
        key="relay_aux4b_period",
        translation_key="relay_aux_period",
        translation_placeholders={"number": "4", "subtimer": "2"},
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        entity_registry_enabled_default=False,
        write_fn=_write_timer_period,
    ),
    "relay_light_period": NeoPoolSelectEntityDescription(
        key="relay_light_period",
        translation_key="relay_light_period",
        entity_category=EntityCategory.CONFIG,
        select_type="timer_period",
        supported_fn=_light_gpio_supported,
        write_fn=_write_timer_period,
    ),
    "relay_aux1_mode": NeoPoolSelectEntityDescription(
        key="relay_aux1_mode",
        translation_key="relay_aux_mode",
        translation_placeholders={"number": "1"},
        options_map={1: "auto", 4: "manual"},
        select_type="relay_mode",
        write_fn=_write_relay_mode,
    ),
    "relay_aux2_mode": NeoPoolSelectEntityDescription(
        key="relay_aux2_mode",
        translation_key="relay_aux_mode",
        translation_placeholders={"number": "2"},
        options_map={1: "auto", 4: "manual"},
        select_type="relay_mode",
        write_fn=_write_relay_mode,
    ),
    "relay_aux3_mode": NeoPoolSelectEntityDescription(
        key="relay_aux3_mode",
        translation_key="relay_aux_mode",
        translation_placeholders={"number": "3"},
        options_map={1: "auto", 4: "manual"},
        select_type="relay_mode",
        write_fn=_write_relay_mode,
    ),
    "relay_aux4_mode": NeoPoolSelectEntityDescription(
        key="relay_aux4_mode",
        translation_key="relay_aux_mode",
        translation_placeholders={"number": "4"},
        options_map={1: "auto", 4: "manual"},
        select_type="relay_mode",
        write_fn=_write_relay_mode,
    ),
    "relay_light_mode": NeoPoolSelectEntityDescription(
        key="relay_light_mode",
        translation_key="relay_light_mode",
        options_map={1: "auto", 4: "manual"},
        select_type="relay_mode",
        supported_fn=_light_gpio_supported,
        write_fn=_write_relay_mode,
    ),
}


# Entities gated on a config-entry option (in addition to their supported_fn).
_ENTITY_OPTION_KEY: dict[str, str] = {
    "relay_aux1_period": CONF_USE_AUX1,
    "relay_aux1b_period": CONF_USE_AUX1,
    "relay_aux2_period": CONF_USE_AUX2,
    "relay_aux2b_period": CONF_USE_AUX2,
    "relay_aux3_period": CONF_USE_AUX3,
    "relay_aux3b_period": CONF_USE_AUX3,
    "relay_aux4_period": CONF_USE_AUX4,
    "relay_aux4b_period": CONF_USE_AUX4,
    "relay_light_period": CONF_USE_LIGHT,
    "relay_aux1_mode": CONF_USE_AUX1,
    "relay_aux2_mode": CONF_USE_AUX2,
    "relay_aux3_mode": CONF_USE_AUX3,
    "relay_aux4_mode": CONF_USE_AUX4,
    "relay_light_mode": CONF_USE_LIGHT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool select entities from a config entry."""
    coordinator = entry.runtime_data
    options = entry.options

    async_add_entities(
        NeoPoolSelect(coordinator, key, desc)
        for key, desc in SELECT_DESCRIPTIONS.items()
        if (
            (option_key := _ENTITY_OPTION_KEY.get(key)) is None
            or bool(options.get(option_key))
        )
        and (desc.supported_fn is None or desc.supported_fn(coordinator.data))
    )


class NeoPoolSelect(NeoPoolEntity, SelectEntity):
    """Representation of a NeoPool select entity."""

    entity_description: NeoPoolSelectEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolSelectEntityDescription,
    ) -> None:
        """Initialize the NeoPool select entity."""
        # The second aux subtimer's period select gates its block on context;
        # other selects need none.
        block = key.removesuffix("_period").removesuffix("_mode")
        context = block if block.endswith("b") else None
        super().__init__(coordinator, context=context)
        self.entity_description = description
        self._key = key
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Handle option selection by dispatching to the description write_fn."""
        write_fn = self.entity_description.write_fn
        if write_fn is None:  # pragma: no cover - every description wires write_fn
            return
        try:
            await write_fn(self, self.coordinator.client, option)
        except (NeoPoolError, OSError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="modbus_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of options for the select entity."""
        desc = self.entity_description
        data = self.coordinator.data

        if (options_fn := desc.options_fn) is not None:
            return options_fn(data)

        if desc.select_type == "timer_period":
            # no_repeat (period 0) is always offered so a timer can be returned
            # to its non-repeating state after a repeat period was selected.
            options_list = [_NO_REPEAT, *PERIOD_MAP.keys()]
            value = data.get(self._key)
            # Mirror current_option: a non-zero device period outside the
            # canonical map is surfaced as a raw-seconds string so the two
            # stay in sync.
            if isinstance(value, int) and value and value not in PERIOD_SECONDS_TO_KEY:
                return [str(value), *options_list]
            return options_list

        if desc.select_type == "relay_mode":
            options = list(dict.fromkeys(desc.options_map.values()))
            timer_name = self._key.rsplit("_", 1)[0]
            value = data.get(f"{timer_name}_enable")
            if value == 0 and "disabled" not in options:
                options = ["disabled", *options]
            if (
                value == 2 and "auto_linked" not in options
            ):  # pragma: no cover - auto_linked out of scope
                options = ["auto_linked", *options]
            return options

        # If device holds an unknown value, prepend raw fallback string.
        if desc.select_type == "mapped_register":
            options = list(desc.options_map.values())
            value = data.get(self._key)
            if (
                isinstance(value, int) and value not in desc.options_map
            ):  # pragma: no cover - device values stay within the mapped set
                suffix = desc.fallback_suffix
                return [f"{value}{suffix}", *options]
            return options

        if desc.select_type == "filtvalve_mode":
            # An uninitialised valve reports mode 0; expose it as a read-only
            # "disabled" option, mirroring the relay selects.
            options = list(desc.options_map.values())
            if data.get(self._key) == 0 and "disabled" not in options:
                return ["disabled", *options]
            return options

        return list(desc.options_map.values())

    def apply_optimistic_update(self, value: int | None) -> dict[str, Any]:
        """Return the coordinator-data overrides for an optimistic state update."""
        if value is None:  # pragma: no cover - callers pass a resolved value
            return {}
        desc = self.entity_description
        if self._key == "MBF_PAR_FILT_MODE":
            return {self._key: value}
        if desc.select_type == "mapped_register":
            return {self._key: value}
        return {}  # pragma: no cover - selects without optimistic update

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option for the select entity."""
        desc = self.entity_description
        data = self.coordinator.data

        if (current_option_fn := desc.current_option_fn) is not None:
            return current_option_fn(data)

        if desc.select_type == "timer_period":
            value = data.get(self._key)
            if value is None:  # pragma: no cover - timer block present once polled
                return None
            int_value = int(value)
            if int_value == 0:
                return _NO_REPEAT
            return PERIOD_SECONDS_TO_KEY.get(int_value, str(int_value))

        if desc.select_type == "relay_mode":
            timer_name = self._key.rsplit("_", 1)[0]
            value = data.get(f"{timer_name}_enable")
            if value is None:  # pragma: no cover - enable key present once polled
                return None
            int_value = int(value)
            if int_value == 0:
                return "disabled"
            if int_value == 2:  # pragma: no cover - auto_linked out of scope
                return "auto_linked"
            if int_value in (TimerRelayMode.ALWAYS_ON, TimerRelayMode.ALWAYS_OFF):
                return "manual"
            return desc.options_map.get(
                int_value
            )  # pragma: no cover - value is 0/2/manual

        if desc.select_type == "filtvalve_mode":
            value = data.get(self._key)
            if value is None:  # pragma: no cover - register present once polled
                return None
            int_value = int(value)
            if int_value == 0:
                return "disabled"
            if int_value in (FiltValveMode.ALWAYS_ON, FiltValveMode.ALWAYS_OFF):
                return "manual"
            return desc.options_map.get(int_value)

        if desc.select_type == "mapped_register":
            value = data.get(self._key)
            if value is None:  # pragma: no cover - register present once polled
                return None
            suffix = desc.fallback_suffix
            return desc.options_map.get(int(value), f"{value}{suffix}")

        value = data.get(self._key)
        if value is None:  # pragma: no cover - register present once polled
            return None
        return desc.options_map.get(value)
