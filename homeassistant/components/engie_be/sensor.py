"""Sensor platform for the ENGIE Belgium integration."""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from aioengiebelgium import EpexGranularity, EpexSlot, bare_ean

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION
from .coordinator import (
    BRUSSELS_TIME_ZONE,
    EngieBeEpexCoordinator,
    EngieBePricesCoordinator,
    EngieBePricesData,
    epex_slot_covering,
    epex_slots_cover_day,
    epex_slots_for_day,
    normalize_slot_code,
)

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

PARALLEL_UPDATES = 0

_UNIT = "EUR/kWh"
_SLOT_CODE_SUFFIXES = {
    "TOTAL_HOURS": "",
    "PEAK": "_peak",
    "OFFPEAK": "_offpeak",
    "SUPEROFFPEAK": "_superoffpeak",
}
_FALLBACK_SLOT_SUFFIX = "_slot"
_ENERGY_TYPE_KEYS = {"ELECTRICITY": "electricity", "GAS": "gas"}
_FALLBACK_TYPE_KEY = "energy"


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

        normalized_slot_code = normalize_slot_code(slot_code)
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


_EPEX_PRECISION = 4


@dataclass(frozen=True, kw_only=True)
class EngieBeEpexSensorEntityDescription(SensorEntityDescription):
    """Describes an EPEX day-ahead price sensor entity."""

    granularity: EpexGranularity
    value_fn: Callable[[EngieBeEpexPriceSensor], float | None]
    extra_fn: Callable[[EngieBeEpexPriceSensor], dict[str, str] | None]


def _epex_slot_value(slot: EpexSlot | None) -> float | None:
    """Return the EUR/kWh value of a slot."""
    return None if slot is None else slot.value_eur_per_kwh


def _epex_slot_attributes(slot: EpexSlot | None) -> dict[str, str] | None:
    """Return the start and end of a slot as attributes."""
    if slot is None:
        return None
    return {"start": slot.start.isoformat(), "end": slot.end.isoformat()}


_EPEX_SENSORS: tuple[EngieBeEpexSensorEntityDescription, ...] = (
    EngieBeEpexSensorEntityDescription(
        key="epex_current_hour",
        translation_key="epex_current_hour",
        granularity=EpexGranularity.HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.current_slot()),
        extra_fn=lambda entity: None,
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_next_hour",
        translation_key="epex_next_hour",
        granularity=EpexGranularity.HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.next_slot()),
        extra_fn=lambda entity: None,
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_low_today_hour",
        translation_key="epex_low_today_hour",
        granularity=EpexGranularity.HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(min)),
        extra_fn=lambda entity: _epex_slot_attributes(entity.extreme_slot(min)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_high_today_hour",
        translation_key="epex_high_today_hour",
        granularity=EpexGranularity.HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(max)),
        extra_fn=lambda entity: _epex_slot_attributes(entity.extreme_slot(max)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_current_quarter_hour",
        translation_key="epex_current_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.current_slot()),
        extra_fn=lambda entity: None,
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_next_quarter_hour",
        translation_key="epex_next_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: _epex_slot_value(entity.next_slot()),
        extra_fn=lambda entity: None,
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_low_today_quarter_hour",
        translation_key="epex_low_today_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(min)),
        extra_fn=lambda entity: _epex_slot_attributes(entity.extreme_slot(min)),
    ),
    EngieBeEpexSensorEntityDescription(
        key="epex_high_today_quarter_hour",
        translation_key="epex_high_today_quarter_hour",
        granularity=EpexGranularity.QUARTER_HOURLY,
        value_fn=lambda entity: _epex_slot_value(entity.extreme_slot(max)),
        extra_fn=lambda entity: _epex_slot_attributes(entity.extreme_slot(max)),
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

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the slot attributes."""
        return self.entity_description.extra_fn(self)
