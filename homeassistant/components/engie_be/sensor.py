"""Sensor platform for the ENGIE Belgium integration."""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, override

from aioengiebelgium import ConsumptionAddress, bare_ean

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import ATTRIBUTION
from .coordinator import (
    EngieBePricesCoordinator,
    EngieBePricesData,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    runtime_data = entry.runtime_data
    known_unique_ids: set[str] = set()
    subscribed_bans: set[str] = set()

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

    @callback
    def _async_subscribe_new_households() -> None:
        """Subscribe to price updates for every household not yet subscribed."""
        for ban, household in runtime_data.households.items():
            if ban in subscribed_bans:
                continue
            subscribed_bans.add(ban)
            entry.async_on_unload(
                household.prices.async_add_listener(_async_add_new_entities)
            )
        _async_add_new_entities()

    _async_subscribe_new_households()
    entry.async_on_unload(
        runtime_data.relations.async_add_listener(_async_subscribe_new_households)
    )


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

        location = _location_words(
            business_agreement_number, coordinator.agreement.consumption_address
        )
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
