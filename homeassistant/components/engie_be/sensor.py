"""Sensor platform for the ENGIE Belgium integration."""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, override

from aioengiebelgium import (
    ActiveTouPrice,
    EanPrices,
    EpexGranularity,
    EpexSlot,
    TouDirectionSchedule,
    TouSchedule,
    TouScheduleItem,
    bare_ean,
    canonicalise_slot_code,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION
from .coordinator import (
    BRUSSELS_TIME_ZONE,
    EngieBeEpexCoordinator,
    EngieBePricesCoordinator,
    EngieBePricesData,
    EngieBeTouCoordinator,
    epex_slot_covering,
    epex_slots_cover_day,
    epex_slots_for_day,
    lookup_by_ean,
)

if TYPE_CHECKING:
    from . import EngieBeConfigEntry, EngieBeHouseholdCoordinators

PARALLEL_UPDATES = 0

_UNIT = "EUR/kWh"
_SLOT_CODE_SUFFIXES = {
    "total_hours": "",
    "peak": "_peak",
    "offpeak": "_offpeak",
    "superoffpeak": "_superoffpeak",
}
_FALLBACK_SLOT_SUFFIX = "_slot"
_ENERGY_TYPE_KEYS = {"ELECTRICITY": "electricity", "GAS": "gas"}
_FALLBACK_TYPE_KEY = "energy"
_WEEKDAY_FIELDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_DIRECTIONS: tuple[Literal["offtake", "injection"], ...] = ("offtake", "injection")


def _energy_type_key(ean: str, ean_energy_types: Mapping[str, str | None]) -> str:
    """Resolve the translation-key type dimension for an EAN."""
    energy_type = (ean_energy_types.get(bare_ean(ean)) or "").upper()
    return _ENERGY_TYPE_KEYS.get(energy_type, _FALLBACK_TYPE_KEY)


def _duplicate_type_eans(
    eans: Iterable[str], ean_energy_types: Mapping[str, str | None]
) -> set[str]:
    """Return the EANs whose energy type recurs more than once in a household."""
    type_keys = {ean: _energy_type_key(ean, ean_energy_types) for ean in eans}
    counts = Counter(type_keys.values())
    return {ean for ean, type_key in type_keys.items() if counts[type_key] > 1}


def _ean_aware_translation(
    base_key: str, ean_suffix: str
) -> tuple[str, dict[str, str]]:
    """Return the translation key and placeholders for an entity name."""
    if not ean_suffix:
        return base_key, {}
    return f"{base_key}_with_ean", {"ean_suffix": ean_suffix}


def _direction_schedule(
    schedule: TouSchedule, direction: Literal["offtake", "injection"]
) -> TouDirectionSchedule | None:
    """Return the direction schedule of a supplier or grid schedule."""
    if direction == "offtake":
        return schedule.offtake
    return schedule.injection


def _has_price_slots(
    ean_prices: EanPrices, direction: Literal["offtake", "injection"]
) -> bool:
    """Return True when any price period prices the given direction."""
    return any(
        period.offtake if direction == "offtake" else period.injection
        for period in ean_prices.periods
    )


def _build_tou_entities(
    household: EngieBeHouseholdCoordinators,
    ban: str,
    known_unique_ids: set[str],
) -> list[EngieBeTouEntity]:
    """Build the time-of-use entities of one household that are not known yet."""
    tou_data: dict[str, TouScheduleItem] | None = household.tou.data
    if tou_data is None:
        return []
    prices_data = household.prices.data
    eans = {bare_ean(ean) for ean in tou_data} | (
        {bare_ean(ean) for ean in prices_data.eans}
        if prices_data is not None
        else set()
    )
    duplicate_eans = _duplicate_type_eans(eans, household.prices.ean_energy_types)
    entities: list[EngieBeTouEntity] = []
    for ean, item in tou_data.items():
        if (
            _energy_type_key(ean, household.prices.ean_energy_types)
            == _ENERGY_TYPE_KEYS["GAS"]
        ):
            continue
        meter = item.primary_meter()
        if meter is None:
            continue
        ean_suffix = bare_ean(ean)[-4:] if bare_ean(ean) in duplicate_eans else ""
        source_schedules: dict[Literal["supplier", "dgo_tgo"], TouSchedule | None] = {
            "supplier": meter.supplier,
            "dgo_tgo": meter.dgo_tgo,
        }
        for source, schedule in source_schedules.items():
            if schedule is None:
                continue
            for direction in _DIRECTIONS:
                direction_schedule = _direction_schedule(schedule, direction)
                if (
                    direction_schedule is None
                    or not direction_schedule.has_multiple_slot_codes()
                ):
                    continue
                entity: EngieBeTouEntity = EngieBeTouSlotSensor(
                    household.tou,
                    ban=ban,
                    ean=ean,
                    source=source,
                    direction=direction,
                    device_info=household.prices.device_info,
                    ean_suffix=ean_suffix,
                )
                if entity.unique_id not in known_unique_ids:
                    entities.append(entity)
        if household.is_dynamic is False and prices_data is not None:
            supplier = meter.supplier
            if supplier is not None:
                for direction in _DIRECTIONS:
                    direction_schedule = _direction_schedule(supplier, direction)
                    ean_prices = lookup_by_ean(prices_data.prices_by_ean, ean)
                    if (
                        direction_schedule is None
                        or not direction_schedule.has_multiple_slot_codes()
                        or ean_prices is None
                        or not _has_price_slots(ean_prices, direction)
                    ):
                        continue
                    active_entity = EngieBeActivePriceSensor(
                        household.tou,
                        prices=household.prices,
                        ban=ban,
                        ean=ean,
                        direction=direction,
                        device_info=household.prices.device_info,
                        ean_suffix=ean_suffix,
                    )
                    if active_entity.unique_id not in known_unique_ids:
                        entities.append(active_entity)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    runtime_data = entry.runtime_data
    known_unique_ids: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add price sensors for any household/EAN/slot combination not yet known."""
        new_entities: list[EngieBePriceSensor] = []
        for ban, household in runtime_data.households.items():
            prices_data: EngieBePricesData | None = household.prices.data
            if prices_data is None:
                continue
            duplicate_eans = _duplicate_type_eans(
                prices_data.eans, household.prices.ean_energy_types
            )
            for ean, direction, slot_code in prices_data.slots:
                type_key = _energy_type_key(ean, household.prices.ean_energy_types)
                ean_suffix = bare_ean(ean)[-4:] if ean in duplicate_eans else ""
                for excl_vat in (False, True):
                    entity = EngieBePriceSensor(
                        household.prices,
                        business_agreement_number=ban,
                        ean=ean,
                        direction=direction,
                        slot_code=slot_code,
                        excl_vat=excl_vat,
                        type_key=type_key,
                        ean_suffix=ean_suffix,
                    )
                    if entity.unique_id not in known_unique_ids:
                        new_entities.append(entity)
        if new_entities:
            known_unique_ids.update(
                unique_id for entity in new_entities if (unique_id := entity.unique_id)
            )
            async_add_entities(new_entities)

    for household in runtime_data.households.values():
        entry.async_on_unload(
            household.prices.async_add_listener(_async_add_new_entities)
        )
    _async_add_new_entities()

    known_tou_unique_ids: set[str] = set()

    @callback
    def _async_add_tou_entities() -> None:
        """Add time-of-use entities for every switching schedule in the data."""
        new_entities = [
            entity
            for ban, household in runtime_data.households.items()
            for entity in _build_tou_entities(household, ban, known_tou_unique_ids)
        ]
        if new_entities:
            known_tou_unique_ids.update(
                unique_id
                for entity in new_entities
                if (unique_id := entity.unique_id) is not None
            )
            async_add_entities(new_entities)

    for household in runtime_data.households.values():
        entry.async_on_unload(household.tou.async_add_listener(_async_add_tou_entities))
        entry.async_on_unload(
            household.prices.async_add_listener(_async_add_tou_entities)
        )
    _async_add_tou_entities()

    known_epex_bans: set[str] = set()

    @callback
    def _async_add_epex_sensors() -> None:
        """Add the EPEX price sensors for the dynamic households."""
        if (epex := runtime_data.epex) is None:
            return
        new_bans = [
            ban
            for ban, household in runtime_data.households.items()
            if household.is_dynamic and ban not in known_epex_bans
        ]
        if not new_bans:
            return
        known_epex_bans.update(new_bans)
        async_add_entities(
            EngieBeEpexPriceSensor(
                epex,
                ban=ban,
                device_info=runtime_data.households[ban].prices.device_info,
                description=description,
            )
            for ban in new_bans
            for description in _EPEX_SENSORS
        )

    runtime_data.epex_ready_callbacks.append(_async_add_epex_sensors)
    _async_add_epex_sensors()


class EngieBePriceSensor(CoordinatorEntity[EngieBePricesCoordinator], SensorEntity):
    """Representation of an ENGIE Belgium energy price sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = _UNIT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 6

    def __init__(
        self,
        coordinator: EngieBePricesCoordinator,
        *,
        business_agreement_number: str,
        ean: str,
        direction: str,
        slot_code: str,
        excl_vat: bool,
        type_key: str,
        ean_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._ean = ean
        self._direction = direction
        self._slot_code = slot_code
        self._excl_vat = excl_vat

        unique_id = f"{business_agreement_number}_{ean}_{direction}_{slot_code}"
        self._attr_unique_id = f"{unique_id}_excl_vat" if excl_vat else unique_id

        normalized_slot_code = canonicalise_slot_code(slot_code)
        suffix = _SLOT_CODE_SUFFIXES.get(normalized_slot_code, _FALLBACK_SLOT_SUFFIX)
        translation_key = f"{type_key}_price_{direction}{suffix}"
        if excl_vat:
            translation_key = f"{translation_key}_excl_vat"
        if ean_suffix:
            translation_key = f"{translation_key}_with_ean"
        self._attr_translation_key = translation_key
        translation_placeholders: dict[str, str] = {}
        if ean_suffix:
            translation_placeholders["ean_suffix"] = ean_suffix
        if suffix == _FALLBACK_SLOT_SUFFIX:
            translation_placeholders["slot_code"] = normalized_slot_code.lower()
        if translation_placeholders:
            self._attr_translation_placeholders = translation_placeholders
        if excl_vat:
            self._attr_entity_registry_enabled_default = False

    @property
    @override
    def available(self) -> bool:
        """Return True only when this entity's slot is present in the current data."""
        return (
            super().available
            and (self._ean, self._direction, self._slot_code)
            in self.coordinator.data.slots
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current price."""
        slot = self.coordinator.data.slots[self._ean, self._direction, self._slot_code]
        return slot.price_value_excl_vat if self._excl_vat else slot.price_value


class EngieBeTouEntity(CoordinatorEntity[EngieBeTouCoordinator], SensorEntity):
    """Base class for time-of-use entities that write states on the slot boundary."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    _unsub_transition: Callable[[], None] | None = None

    def _next_transition(self) -> datetime | None:
        """Return the next slot boundary of this entity."""
        raise NotImplementedError

    @callback
    def _unschedule_transition(self) -> None:
        """Cancel the pending boundary update."""
        if self._unsub_transition is not None:
            self._unsub_transition()
            self._unsub_transition = None

    @callback
    def _schedule_transition(self) -> None:
        """Write a state when the next slot boundary passes."""
        self._unschedule_transition()
        transition = self._next_transition()
        if transition is None or transition <= dt_util.utcnow():
            return
        self._unsub_transition = async_track_point_in_utc_time(
            self.hass, self._async_transition, transition
        )

    @callback
    def _async_transition(self, _now: datetime) -> None:
        """Write the new slot state and schedule the following boundary."""
        self._unsub_transition = None
        self.async_write_ha_state()
        self._schedule_transition()

    @override
    async def async_added_to_hass(self) -> None:
        """Start writing states on the slot boundary."""
        await super().async_added_to_hass()
        self._schedule_transition()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop the boundary updates."""
        self._unschedule_transition()
        await super().async_will_remove_from_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Reschedule the boundary update and write the new state."""
        self._schedule_transition()
        super()._handle_coordinator_update()


class EngieBeTouSlotSensor(EngieBeTouEntity):
    """Current time-of-use slot of one direction on one meter."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        coordinator: EngieBeTouCoordinator,
        *,
        ban: str,
        ean: str,
        source: Literal["supplier", "dgo_tgo"],
        direction: Literal["offtake", "injection"],
        device_info: DeviceInfo,
        ean_suffix: str = "",
    ) -> None:
        """Initialize the slot sensor."""
        super().__init__(coordinator)
        self._ean = ean
        self._source = source
        self._direction = direction
        self._attr_device_info = device_info
        prefix = "tou" if source == "supplier" else "grid"
        translation_key, placeholders = _ean_aware_translation(
            f"{prefix}_{direction}_slot", ean_suffix
        )
        self._attr_translation_key = translation_key
        if placeholders:
            self._attr_translation_placeholders = placeholders
        self._attr_unique_id = f"{ban}_{ean}_{prefix}_{direction}_slot"

    def _direction_schedule(self) -> TouDirectionSchedule | None:
        """Return the schedule this sensor tracks."""
        item = lookup_by_ean(self.coordinator.data, self._ean)
        meter = item.primary_meter() if item is not None else None
        if meter is None:
            return None
        schedule = meter.supplier if self._source == "supplier" else meter.dgo_tgo
        if schedule is None:
            return None
        return _direction_schedule(schedule, self._direction)

    def _current(self) -> tuple[str | None, datetime | None]:
        """Return the current slot code and the next boundary."""
        schedule = self._direction_schedule()
        if schedule is None:
            return None, None
        return schedule.current_slot(
            dt_util.now(BRUSSELS_TIME_ZONE), BRUSSELS_TIME_ZONE
        )

    @override
    def _next_transition(self) -> datetime | None:
        """Return the next slot boundary of this meter."""
        return self._current()[1]

    @property
    @override
    def options(self) -> list[str] | None:
        """Return the slot codes this meter's schedule switches between."""
        schedule = self._direction_schedule()
        if schedule is None:
            return None
        return sorted(
            {
                slot.slot_code
                for weekday in range(7)
                for slot in schedule.slots_for_weekday(weekday)
            }
        )

    @property
    @override
    def available(self) -> bool:
        """Return True while the schedule data of this direction is present."""
        return super().available and self._direction_schedule() is not None

    @property
    @override
    def native_value(self) -> str | None:
        """Return the current slot code."""
        return self._current()[0]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the weekly schedule of this direction."""
        schedule = self._direction_schedule()
        if schedule is None:
            return {}
        _, next_transition = self._current()
        weekday_slots = {
            day: [
                {
                    "start": slot.start_time,
                    "end": slot.end_time,
                    "code": slot.slot_code,
                    "cost": slot.cost_indicator,
                }
                for slot in schedule.slots_for_weekday(weekday)
            ]
            for weekday, day in enumerate(_WEEKDAY_FIELDS)
        }
        return {
            "optimal_slot": schedule.optimal_timeslot_code,
            "next_transition": next_transition,
            "weekday_slots": weekday_slots,
        }


class EngieBeActivePriceSensor(EngieBeTouEntity):
    """Electricity price that applies right now on the supplier schedule."""

    _attr_native_unit_of_measurement = _UNIT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 6

    def __init__(
        self,
        coordinator: EngieBeTouCoordinator,
        *,
        prices: EngieBePricesCoordinator,
        ban: str,
        ean: str,
        direction: Literal["offtake", "injection"],
        device_info: DeviceInfo,
        ean_suffix: str = "",
    ) -> None:
        """Initialize the active price sensor."""
        super().__init__(coordinator)
        self._prices = prices
        self._ean = ean
        self._direction = direction
        self._attr_device_info = device_info
        translation_key, placeholders = _ean_aware_translation(
            f"electricity_current_{direction}_price", ean_suffix
        )
        self._attr_translation_key = translation_key
        if placeholders:
            self._attr_translation_placeholders = placeholders
        self._attr_unique_id = f"{ban}_{ean}_{direction}_current_price"

    @override
    async def async_added_to_hass(self) -> None:
        """Track price updates next to schedule updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._prices.async_add_listener(self._handle_coordinator_update)
        )

    def _supplier_schedule(self) -> TouSchedule | None:
        """Return the supplier schedule of this meter."""
        item = lookup_by_ean(self.coordinator.data, self._ean)
        meter = item.primary_meter() if item is not None else None
        return meter.supplier if meter is not None else None

    def _active(self) -> ActiveTouPrice | None:
        """Return the joined price that applies right now."""
        prices_data = self._prices.data
        schedule = self._supplier_schedule()
        if schedule is None or prices_data is None:
            return None
        ean_prices = lookup_by_ean(prices_data.prices_by_ean, self._ean)
        if ean_prices is None:
            return None
        return ean_prices.active_tou_price(
            schedule,
            self._direction,
            dt_util.now(BRUSSELS_TIME_ZONE),
            BRUSSELS_TIME_ZONE,
        )

    @override
    def _next_transition(self) -> datetime | None:
        """Return the next slot boundary of the supplier schedule."""
        active = self._active()
        if active is not None:
            return active.next_transition
        schedule = self._supplier_schedule()
        if schedule is None:
            return None
        direction_schedule = _direction_schedule(schedule, self._direction)
        if direction_schedule is None:
            return None
        return direction_schedule.current_slot(
            dt_util.now(BRUSSELS_TIME_ZONE), BRUSSELS_TIME_ZONE
        )[1]

    @property
    @override
    def available(self) -> bool:
        """Return True while this meter still has schedule and price data."""
        prices_data = self._prices.data
        return (
            super().available
            and self._prices.last_update_success
            and prices_data is not None
            and self._supplier_schedule() is not None
            and lookup_by_ean(prices_data.prices_by_ean, self._ean) is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the price that applies right now."""
        active = self._active()
        return active.price_value if active is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the active slot and the next transition details."""
        active = self._active()
        if active is None:
            return {}
        return {
            "slot_code": active.slot_code,
            "next_transition": active.next_transition,
            "next_slot_code": active.next_slot_code,
            "next_price": active.next_price_value,
        }


_EPEX_PRECISION = 4


@dataclass(frozen=True, kw_only=True)
class EngieBeEpexSensorEntityDescription(SensorEntityDescription):
    """Describes an EPEX day-ahead price sensor entity."""

    granularity: EpexGranularity
    value_fn: Callable[[EngieBeEpexPriceSensor], float | None]


def _epex_slot_value(slot: EpexSlot | None) -> float | None:
    """Return the EUR/kWh value of a slot."""
    return None if slot is None else slot.value_eur_per_kwh


_EPEX_SENSORS: tuple[EngieBeEpexSensorEntityDescription, ...] = (
    EngieBeEpexSensorEntityDescription(
        key="epex_current_hour",
        translation_key="epex_current_hour",
        granularity=EpexGranularity.HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.current_slot()),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_next_hour",
        translation_key="epex_next_hour",
        granularity=EpexGranularity.HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.next_slot()),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_low_today_hour",
        translation_key="epex_low_today_hour",
        granularity=EpexGranularity.HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(min)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_high_today_hour",
        translation_key="epex_high_today_hour",
        granularity=EpexGranularity.HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(max)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_current_quarter_hour",
        translation_key="epex_current_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.current_slot()),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_next_quarter_hour",
        translation_key="epex_next_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.next_slot()),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_low_today_quarter_hour",
        translation_key="epex_low_today_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(min)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_high_today_quarter_hour",
        translation_key="epex_high_today_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(max)),
    ),
)


class EngieBeEpexPriceSensor(CoordinatorEntity[EngieBeEpexCoordinator], SensorEntity):
    """EPEX day-ahead price sensor on a dynamic-tariff household device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = _UNIT
    _attr_suggested_display_precision = _EPEX_PRECISION

    entity_description: EngieBeEpexSensorEntityDescription

    def __init__(
        self,
        coordinator: EngieBeEpexCoordinator,
        *,
        ban: str,
        device_info: DeviceInfo,
        description: EngieBeEpexSensorEntityDescription,
    ) -> None:
        """Initialize the EPEX price sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{ban}_{description.key}"

    def _slots(self) -> tuple[EpexSlot, ...]:
        """Return the merged slots of this sensor's granularity."""
        return self.coordinator.data.slots(self.entity_description.granularity)

    def current_slot(self) -> EpexSlot | None:
        """Return the slot covering the current instant."""
        return epex_slot_covering(self._slots(), dt_util.utcnow())

    def next_slot(self) -> EpexSlot | None:
        """Return the slot covering one granularity step from now."""
        step = timedelta(minutes=self.entity_description.granularity.value)
        return epex_slot_covering(self._slots(), dt_util.utcnow() + step)

    def extreme_slot(self, choose: Callable[..., EpexSlot]) -> EpexSlot | None:
        """Return today's cheapest or most expensive slot in Brussels."""
        today = dt_util.now(BRUSSELS_TIME_ZONE).date()
        slots = self._slots()
        if not epex_slots_cover_day(slots, today, self.entity_description.granularity):
            return None
        return choose(
            epex_slots_for_day(slots, today),
            key=lambda slot: slot.value_eur_per_kwh,
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the EPEX day-ahead price."""
        return self.entity_description.value_fn(self)
