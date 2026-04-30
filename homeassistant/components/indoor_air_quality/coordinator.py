"""Indoor Air Quality controller."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    CarbonMonoxideConcentrationConverter,
    MassVolumeConcentrationConverter,
    NitrogenDioxideConcentrationConverter,
    TemperatureConverter,
)

from .bands import BANDS, level_for_index, score_from_bands
from .const import (
    ATTR_SOURCE_INDEX_TPL,
    ATTR_SOURCES_SET,
    ATTR_SOURCES_USED,
    CONF_CO,
    CONF_CO2,
    CONF_HCHO,
    CONF_HUMIDITY,
    CONF_NO2,
    CONF_PM,
    CONF_RADON,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    DEFAULT_STANDARD,
    MOLAR_MASS_CO2,
    MOLAR_MASS_HCHO,
    MOLAR_MASS_TVOC,
    UNIT_MGM3,
    UNIT_PPM,
    UNIT_UGM3,
)
from .helpers import convert_value, normalise_unit, resolve_state

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Declarative configuration for a single IAQ source.

    Either ``converter`` (a Home Assistant core unit converter) or
    ``target_units`` (a custom alias/factor mapping with optional
    ``molar_mass``) is used to normalise the source value into
    ``target_unit``. ``valid_units`` rejects sources that report a unit
    outside the listed set without performing any conversion.
    """

    converter: type[BaseUnitConverter] | None = None
    target_unit: str | None = None
    target_units: Mapping[str, float] | None = None
    molar_mass: float | None = None
    is_list: bool = False
    valid_units: frozenset[str | None] | None = None


# Per-source conversion declarations. Sources missing here are ignored.
SOURCE_SPECS: Final[dict[str, SourceSpec]] = {
    CONF_TEMPERATURE: SourceSpec(
        valid_units=frozenset({UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT})
    ),
    CONF_HUMIDITY: SourceSpec(valid_units=frozenset({PERCENTAGE})),
    CONF_CO2: SourceSpec(target_units=UNIT_PPM, molar_mass=MOLAR_MASS_CO2),
    CONF_TVOC: SourceSpec(target_units=UNIT_MGM3, molar_mass=MOLAR_MASS_TVOC),
    CONF_VOC_INDEX: SourceSpec(),
    CONF_PM: SourceSpec(
        converter=MassVolumeConcentrationConverter,
        target_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        is_list=True,
    ),
    CONF_NO2: SourceSpec(
        converter=NitrogenDioxideConcentrationConverter,
        target_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CONF_CO: SourceSpec(
        converter=CarbonMonoxideConcentrationConverter,
        target_unit=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    ),
    CONF_HCHO: SourceSpec(target_units=UNIT_UGM3, molar_mass=MOLAR_MASS_HCHO),
    CONF_RADON: SourceSpec(valid_units=frozenset({None, "Bq/m3", "Bq/m³"})),
}


class IndoorAirQualityController:
    """Indoor Air Quality controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        sources: Mapping[str, str | list[str]],
        device_id: str | None = None,
        *,
        standard: str = DEFAULT_STANDARD,
    ) -> None:
        """Initialize controller."""
        self.hass = hass
        self._entry_id = entry_id
        self._name = name
        self._sources = sources
        self._device_id = device_id
        self._standard = standard

        self._iaq_index: int | None = None
        self._iaq_sources = 0
        self._indexes: dict[str, int] = {}
        self._listeners: list[CALLBACK_TYPE] = []

    # --- public read-only properties ---------------------------------------

    @property
    def entry_id(self) -> str:
        """Return the config entry id this controller belongs to."""
        return self._entry_id

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._entry_id

    @property
    def name(self) -> str:
        """Get controller name."""
        return self._name

    @property
    def device_id(self) -> str | None:
        """Return the source device ID."""
        return self._device_id

    @property
    def standard(self) -> str:
        """Return the active rating standard."""
        return self._standard

    @property
    def iaq_index(self) -> int | None:
        """Get IAQ index."""
        return self._iaq_index

    @property
    def iaq_level(self) -> str | None:
        """Get IAQ level."""
        if self._iaq_index is None:
            return None
        return level_for_index(self._standard, self._iaq_index)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes for the IAQ sensors."""
        attrs: dict[str, Any] = {
            ATTR_SOURCES_SET: len(self._sources),
            ATTR_SOURCES_USED: self._iaq_sources,
        }
        for src, idx in self._indexes.items():
            attrs[ATTR_SOURCE_INDEX_TPL.format(src)] = idx
        return attrs

    # --- listener API ------------------------------------------------------

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe to controller updates and return an unsubscribe callback."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def async_update_listeners(self) -> None:
        """Notify all subscribed listeners of an update."""
        for listener in self._listeners:
            listener()

    # --- index calculation -------------------------------------------------

    def update(self) -> None:
        """Recalculate the IAQ index from the configured sources."""
        _LOGGER.debug("[%s] State update", self._entry_id)

        bands_for_standard = BANDS.get(self._standard)
        if bands_for_standard is None:
            _LOGGER.warning(
                "[%s] Unknown IAQ standard %r", self._entry_id, self._standard
            )
            return

        total = 0
        used = 0
        indexes: dict[str, int] = {}

        for src in self._sources:
            spec = SOURCE_SPECS.get(src)
            if spec is None:
                _LOGGER.debug("[%s] Unknown source %s", self._entry_id, src)
                continue

            value = self._resolve_source(src, spec)
            if value is None:
                continue

            bands = bands_for_standard.get(src)
            if bands is None:
                _LOGGER.debug(
                    "[%s] No bands for source %s in standard %s",
                    self._entry_id,
                    src,
                    self._standard,
                )
                continue

            idx = score_from_bands(value, bands)
            _LOGGER.debug(
                "[%s] %s_index=%s (value=%s)", self._entry_id, src, idx, value
            )
            indexes[src] = idx
            total += idx
            used += 1

        if used:
            self._indexes = indexes
            self._iaq_index = int((65 * total) / (5 * used))
            self._iaq_sources = used
            _LOGGER.debug(
                "[%s] Update IAQ index to %d (%d sources used)",
                self._entry_id,
                self._iaq_index,
                self._iaq_sources,
            )

    # --- per-source resolution ---------------------------------------------

    def _resolve_source(self, source: str, spec: SourceSpec) -> float | None:
        """Resolve a configured source into the controller's calculation unit."""
        # Specialised paths first; these don't fit the generic conversion model.
        if source == CONF_TEMPERATURE:
            return self._resolve_temperature()
        if source == CONF_VOC_INDEX:
            return self._resolve_dimensionless(source)

        if spec.is_list:
            return self._resolve_list(source, spec)

        entity_id = self._single_entity_id(source)
        if entity_id is None:
            return None
        resolved = resolve_state(self.hass, entity_id)
        if resolved is None:
            return None
        value, unit = resolved

        if spec.valid_units is not None:
            if unit not in spec.valid_units:
                _LOGGER.debug(
                    "Entity %s has unsupported %s unit %r", entity_id, source, unit
                )
                return None
            return value

        return self._normalise(source, entity_id, value, unit, spec)

    def _normalise(
        self,
        source: str,
        entity_id: str,
        value: float,
        unit: str | None,
        spec: SourceSpec,
    ) -> float | None:
        """Normalise ``value`` into the source's target unit."""
        if spec.converter is not None and spec.target_unit is not None:
            normalised_unit = normalise_unit(unit)
            if normalised_unit not in spec.converter.VALID_UNITS:
                _LOGGER.debug(
                    "Entity %s has unsupported %s unit %r", entity_id, source, unit
                )
                return None
            return spec.converter.convert(value, normalised_unit, spec.target_unit)

        if spec.target_units is None:
            return value

        return convert_value(
            value,
            unit,
            spec.target_units,
            molar_mass=spec.molar_mass,
            source_type=source,
        )

    def _resolve_dimensionless(self, source: str) -> float | None:
        """Resolve a numeric, unit-agnostic source (e.g. VOC index)."""
        entity_id = self._single_entity_id(source)
        if entity_id is None:
            return None
        resolved = resolve_state(self.hass, entity_id)
        if resolved is None:
            return None
        return resolved[0]

    def _resolve_temperature(self) -> float | None:
        """Resolve temperature in °C."""
        entity_id = self._single_entity_id(CONF_TEMPERATURE)
        if entity_id is None:
            return None
        resolved = resolve_state(self.hass, entity_id)
        if resolved is None:
            return None
        value, unit = resolved
        if unit not in (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT):
            _LOGGER.debug(
                "Entity %s has unsupported temperature unit %r",
                entity_id,
                unit,
            )
            return None
        if unit != UnitOfTemperature.CELSIUS:
            value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        return value

    def _resolve_list(self, source: str, spec: SourceSpec) -> float | None:
        """Resolve a list-of-entities source, summing converted values."""
        entity_ids = self._sources.get(source)
        if not entity_ids:
            return None
        if not isinstance(entity_ids, list):
            entity_ids = [entity_ids]

        values: list[float] = []
        for eid in entity_ids:
            resolved = resolve_state(self.hass, eid)
            if resolved is None:
                continue
            value, unit = resolved
            converted = self._normalise(source, eid, value, unit, spec)
            if converted is not None:
                values.append(converted)

        if not values:
            return None
        return sum(values)

    def _single_entity_id(self, source: str) -> str | None:
        """Return a configured single-entity source id, ignoring lists."""
        entity_id = self._sources.get(source)
        if not entity_id or isinstance(entity_id, list):
            return None
        return entity_id


# Subscribers that can receive notifications from a controller.
ControllerListener = Callable[[], None]
