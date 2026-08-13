"""Sensor platform for the ENGIE Belgium integration."""

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, override

from aioengiebelgium import ConsumptionAddress, EanPrices, PricePeriod, bare_ean

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import ATTRIBUTION
from .coordinator import EngieBePricesCoordinator, household_device_info

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

PARALLEL_UPDATES = 0

_UNIT = "EUR/kWh"
_DIRECTIONS = ("offtake", "injection")
_DIRECTION_PREFIXES = ("OFFTAKE_", "INJECTION_")
_BLENDED_SLOT_CODE = "EN"
_SLOT_CODE_SUFFIXES = {
    "TOTAL_HOURS": "",
    "PEAK": "_peak",
    "OFFPEAK": "_offpeak",
    "SUPEROFFPEAK": "_superoffpeak",
}
_FALLBACK_SLOT_SUFFIX = "_slot"
_ENERGY_TYPE_KEYS = {"ELECTRICITY": "electricity", "GAS": "gas"}
_FALLBACK_TYPE_KEY = "energy"


def _normalize_slot_code(raw_code: str) -> str:
    """Strip a redundant direction prefix from a raw time-of-use slot code."""
    for prefix in _DIRECTION_PREFIXES:
        idx = raw_code.rfind(prefix)
        if idx != -1:
            return raw_code[idx + len(prefix) :]
    return raw_code


def _parse_date(value: str) -> date | None:
    """Parse a date or datetime string into a date."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _current_period(
    periods: tuple[PricePeriod, ...], today: date
) -> PricePeriod | None:
    """Return the price period covering today, if any."""
    for period in periods:
        from_date = _parse_date(period.valid_from)
        to_date = _parse_date(period.valid_to)
        if from_date is None or to_date is None:
            continue
        if from_date <= today < to_date:
            return period
    return None


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


def _location_words(ban: str, consumption_address: ConsumptionAddress | None) -> str:
    """Return the street-based entity_id location, falling back to the bare BAN."""
    if consumption_address is not None:
        parts = [
            part
            for part in (consumption_address.street, consumption_address.house_number)
            if part
        ]
        if parts:
            return " ".join(parts)
    return ban


def _entity_id_words(
    *,
    type_key: str,
    direction: str,
    slot_suffix: str,
    normalized_slot_code: str,
    excl_vat: bool,
    ean_suffix: str,
) -> list[str]:
    """Build the entity_id object-id words in display-name word order."""
    words: list[str] = []
    if type_key != _FALLBACK_TYPE_KEY:
        words.append(type_key)
    if slot_suffix not in ("", _FALLBACK_SLOT_SUFFIX):
        words.append(slot_suffix.removeprefix("_"))
    words.append(direction)
    words.append("price")
    if excl_vat:
        words.extend(("excl", "vat"))
    if slot_suffix == _FALLBACK_SLOT_SUFFIX:
        words.append(normalized_slot_code.lower())
    if ean_suffix:
        words.append(ean_suffix)
    return words


def _build_entities(
    coordinator: EngieBePricesCoordinator,
    device_info: DeviceInfo,
    ban: str,
    ean_prices: EanPrices,
    today: date,
    *,
    type_key: str,
    ean_suffix: str,
    consumption_address: ConsumptionAddress | None,
) -> list[EngieBePriceSensor]:
    """Build the price sensors for one EAN's current period."""
    period = _current_period(ean_prices.periods, today)
    if period is None:
        return []
    return [
        EngieBePriceSensor(
            coordinator,
            device_info=device_info,
            business_agreement_number=ban,
            ean=ean_prices.ean,
            direction=direction,
            slot_code=slot.time_of_use_slot_code,
            excl_vat=excl_vat,
            type_key=type_key,
            ean_suffix=ean_suffix,
            consumption_address=consumption_address,
        )
        for direction in _DIRECTIONS
        for slot in getattr(period, direction)
        if _normalize_slot_code(slot.time_of_use_slot_code) != _BLENDED_SLOT_CODE
        for excl_vat in (False, True)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    agreements = entry.runtime_data.agreements
    known_unique_ids: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add price sensors for any household/EAN/slot combination not yet known."""
        today = dt_util.now().date()
        new_entities: list[EngieBePriceSensor] = []
        for ban, prices in coordinator.data.items():
            device_info = household_device_info(ban, agreements[ban])
            consumption_address = agreements[ban].consumption_address
            eans = [ean_prices.ean for ean_prices in prices.items]
            duplicate_eans = _duplicate_type_eans(eans, coordinator.ean_energy_types)
            for ean_prices in prices.items:
                new_entities.extend(
                    entity
                    for entity in _build_entities(
                        coordinator,
                        device_info,
                        ban,
                        ean_prices,
                        today,
                        type_key=_energy_type_key(
                            ean_prices.ean, coordinator.ean_energy_types
                        ),
                        ean_suffix=(
                            bare_ean(ean_prices.ean)[-4:]
                            if ean_prices.ean in duplicate_eans
                            else ""
                        ),
                        consumption_address=consumption_address,
                    )
                    if entity.unique_id not in known_unique_ids
                )
        if new_entities:
            known_unique_ids.update(
                unique_id for entity in new_entities if (unique_id := entity.unique_id)
            )
            async_add_entities(new_entities)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


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
        device_info: DeviceInfo,
        business_agreement_number: str,
        ean: str,
        direction: str,
        slot_code: str,
        excl_vat: bool,
        type_key: str,
        ean_suffix: str,
        consumption_address: ConsumptionAddress | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._business_agreement_number = business_agreement_number
        self._ean = ean
        self._direction = direction
        self._slot_code = slot_code
        self._excl_vat = excl_vat

        unique_id = f"{business_agreement_number}_{ean}_{direction}_{slot_code}"
        self._attr_unique_id = f"{unique_id}_excl_vat" if excl_vat else unique_id

        normalized_slot_code = _normalize_slot_code(slot_code)
        suffix = _SLOT_CODE_SUFFIXES.get(normalized_slot_code, _FALLBACK_SLOT_SUFFIX)
        translation_key = f"{type_key}_price_{direction}{suffix}"
        self._attr_translation_key = (
            f"{translation_key}_excl_vat" if excl_vat else translation_key
        )
        translation_placeholders = {
            "ean_suffix": f" {ean_suffix}" if ean_suffix else "",
        }
        if suffix == _FALLBACK_SLOT_SUFFIX:
            translation_placeholders["slot_code"] = normalized_slot_code.lower()
        self._attr_translation_placeholders = translation_placeholders
        if excl_vat:
            self._attr_entity_registry_enabled_default = False

        location = _location_words(business_agreement_number, consumption_address)
        entity_words = _entity_id_words(
            type_key=type_key,
            direction=direction,
            slot_suffix=suffix,
            normalized_slot_code=normalized_slot_code,
            excl_vat=excl_vat,
            ean_suffix=ean_suffix,
        )
        object_id = slugify(f"{location} {' '.join(entity_words)}")
        self.entity_id = f"sensor.{object_id}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current price."""
        prices = self.coordinator.data.get(self._business_agreement_number)
        if prices is None:
            return None
        today = dt_util.now().date()
        for ean_prices in prices.items:
            if ean_prices.ean != self._ean:
                continue
            period = _current_period(ean_prices.periods, today)
            if period is None:
                return None
            direction_slots = (
                period.offtake if self._direction == "offtake" else period.injection
            )
            for slot in direction_slots:
                if slot.time_of_use_slot_code == self._slot_code:
                    return (
                        slot.price_value_excl_vat
                        if self._excl_vat
                        else slot.price_value
                    )
            return None
        return None
