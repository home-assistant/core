"""Test the Indoor Air Quality controller and setup."""

from typing import Any

import pytest

from homeassistant import config_entries
from homeassistant.components.indoor_air_quality import IndoorAirQualityController
from homeassistant.components.indoor_air_quality.const import (
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
    CONF_SOURCES,
    CONF_STANDARD,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    DOMAIN,
    LEVEL_EXCELLENT,
    LEVEL_FAIR,
    LEVEL_GOOD,
    LEVEL_INADEQUATE,
    LEVEL_POOR,
    MOLAR_MASS_CO2,
    MOLAR_MASS_HCHO,
    MOLAR_MASS_TVOC,
    STANDARD_UK,
    UNIT_MGM3,
    UNIT_PPM,
    UNIT_UGM3,
)
from homeassistant.components.indoor_air_quality.helpers import (
    convert_value,
    resolve_state,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Test a config entry is set up, exposes sensors, and unloads cleanly."""
    hass.states.async_set(
        "sensor.temp",
        20,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCES: {CONF_TEMPERATURE: "sensor.temp"},
            CONF_STANDARD: STANDARD_UK,
        },
        title="Living Room",
        unique_id="living-room",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state_index = hass.states.get("sensor.living_room_index")
    state_level = hass.states.get("sensor.living_room_level")
    assert state_index is not None
    assert state_level is not None
    assert state_index.state == "65"
    assert state_level.state == LEVEL_EXCELLENT

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_state_change_updates_sensor(hass: HomeAssistant) -> None:
    """Test the calculated sensors update when a source state changes."""
    hass.states.async_set(
        "sensor.temp",
        20,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCES: {CONF_TEMPERATURE: "sensor.temp"},
            CONF_STANDARD: STANDARD_UK,
        },
        title="Bedroom",
        unique_id="bedroom",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bedroom_level").state == LEVEL_EXCELLENT

    hass.states.async_set(
        "sensor.temp",
        14,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bedroom_level").state == LEVEL_INADEQUATE


async def test_controller_initial_state(hass: HomeAssistant) -> None:
    """Test the controller starts with no calculated value."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_TEMPERATURE: "sensor.test"}
    )

    assert controller.unique_id == "test"
    assert controller.name == "Test"
    assert controller.standard == STANDARD_UK
    assert controller.iaq_index is None
    assert controller.iaq_level is None
    assert controller.extra_state_attributes == {
        ATTR_SOURCES_SET: 1,
        ATTR_SOURCES_USED: 0,
    }


async def test_controller_update_multi_source(hass: HomeAssistant) -> None:
    """Test the controller combines multiple sources into a level."""
    hass.states.async_set(
        "sensor.t", 17, {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set("sensor.h", 50, {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE})
    hass.states.async_set("sensor.c", 800, {ATTR_UNIT_OF_MEASUREMENT: "ppm"})

    controller = IndoorAirQualityController(
        hass,
        "test",
        "Test",
        {
            CONF_TEMPERATURE: "sensor.t",
            CONF_HUMIDITY: "sensor.h",
            CONF_CO2: "sensor.c",
        },
    )
    controller.update()

    assert controller.iaq_index == 56
    assert controller.iaq_level == LEVEL_GOOD
    assert controller.extra_state_attributes == {
        ATTR_SOURCES_SET: 3,
        ATTR_SOURCES_USED: 3,
        ATTR_SOURCE_INDEX_TPL.format(CONF_TEMPERATURE): 4,
        ATTR_SOURCE_INDEX_TPL.format(CONF_HUMIDITY): 5,
        ATTR_SOURCE_INDEX_TPL.format(CONF_CO2): 4,
    }


@pytest.mark.parametrize(
    ("celsius", "expected_index", "expected_level"),
    [
        (18, 65, LEVEL_EXCELLENT),
        (16, 39, LEVEL_FAIR),
        (15, 26, LEVEL_POOR),
        (14, 13, LEVEL_INADEQUATE),
    ],
)
async def test_temperature_levels(
    hass: HomeAssistant,
    celsius: float,
    expected_index: int,
    expected_level: str,
) -> None:
    """Test temperature-only calculations across each band."""
    hass.states.async_set(
        "sensor.t",
        celsius,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_TEMPERATURE: "sensor.t"}
    )
    controller.update()
    assert controller.iaq_index == expected_index
    assert controller.iaq_level == expected_level


async def test_temperature_fahrenheit_conversion(hass: HomeAssistant) -> None:
    """Test temperature input in °F is converted to the matching band."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_TEMPERATURE: "sensor.t"}
    )
    for fahrenheit, expected_score in ((57, 1), (59, 2), (60, 3), (63, 4), (67, 5)):
        hass.states.async_set(
            "sensor.t",
            fahrenheit,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
        )
        controller.update()
        assert (
            controller.extra_state_attributes[
                ATTR_SOURCE_INDEX_TPL.format("temperature")
            ]
            == expected_score
        )


async def test_humidity_levels(hass: HomeAssistant) -> None:
    """Test humidity bands score correctly on both sides of the optimum."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_HUMIDITY: "sensor.h"}
    )
    for value, expected_score in (
        (5, 1),
        (15, 2),
        (25, 3),
        (35, 4),
        (50, 5),
        (75, 3),
        (85, 2),
        (95, 1),
    ):
        hass.states.async_set("sensor.h", value, {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE})
        controller.update()
        assert (
            controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("humidity")]
            == expected_score
        )


async def test_co2_levels(hass: HomeAssistant) -> None:
    """Test CO2 bands."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_CO2: "sensor.c"}
    )
    for value, expected_score in (
        (500, 5),
        (600, 4),
        (1500, 3),
        (1800, 2),
        (1801, 1),
    ):
        hass.states.async_set("sensor.c", value, {ATTR_UNIT_OF_MEASUREMENT: "ppm"})
        controller.update()
        assert (
            controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("co2")]
            == expected_score
        )


async def test_pm_summed_levels(hass: HomeAssistant) -> None:
    """Test PM source list is summed in µg/m³."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_PM: ["sensor.pm1", "sensor.pm2"]}
    )

    hass.states.async_set("sensor.pm1", 10, {ATTR_UNIT_OF_MEASUREMENT: "µg/m³"})
    hass.states.async_set("sensor.pm2", 0.01, {ATTR_UNIT_OF_MEASUREMENT: "mg/m³"})
    controller.update()
    # 10 + 0.01 mg/m³ * 1000 = 20 µg/m³ → score 5
    assert controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("pm")] == 5


async def test_co_levels(hass: HomeAssistant) -> None:
    """Test CO bands and zero-special case."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_CO: "sensor.co"}
    )
    for value, expected_score in ((0, 5), (5, 3), (8, 1)):
        hass.states.async_set("sensor.co", value, {ATTR_UNIT_OF_MEASUREMENT: "mg/m³"})
        controller.update()
        assert (
            controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("co")]
            == expected_score
        )


async def test_radon_levels(hass: HomeAssistant) -> None:
    """Test radon bands and zero-special case."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_RADON: "sensor.r"}
    )
    for value, expected_score in ((0, 5), (10, 3), (50, 2), (200, 1)):
        hass.states.async_set("sensor.r", value, {ATTR_UNIT_OF_MEASUREMENT: "Bq/m³"})
        controller.update()
        assert (
            controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("radon")]
            == expected_score
        )


async def test_voc_index_levels(hass: HomeAssistant) -> None:
    """Test dimensionless VOC index bands."""
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_VOC_INDEX: "sensor.v"}
    )
    for value, expected_score in ((0, 5), (115, 4), (180, 3), (260, 2), (261, 1)):
        hass.states.async_set("sensor.v", value)
        controller.update()
        assert (
            controller.extra_state_attributes[ATTR_SOURCE_INDEX_TPL.format("voc_index")]
            == expected_score
        )


async def test_resolve_state(hass: HomeAssistant) -> None:
    """Test resolve_state behaviour for valid, invalid and missing states."""
    assert resolve_state(hass, "sensor.missing") is None

    hass.states.async_set("sensor.s", STATE_UNKNOWN)
    assert resolve_state(hass, "sensor.s") is None

    hass.states.async_set("sensor.s", STATE_UNAVAILABLE)
    assert resolve_state(hass, "sensor.s") is None

    hass.states.async_set("sensor.s", "not a number")
    assert resolve_state(hass, "sensor.s") is None

    hass.states.async_set("sensor.s", "12.5", {ATTR_UNIT_OF_MEASUREMENT: "ppm"})
    value, unit = resolve_state(hass, "sensor.s")
    assert value == 12.5
    assert unit == "ppm"


def test_convert_value_same_family() -> None:
    """Test direct unit conversions inside a single family."""
    # ppb -> ppm (target unit ppm has factor 1, ppb has factor 0.001)
    assert convert_value(1500, "ppb", UNIT_PPM) == pytest.approx(1.5)
    # mg/m³ -> µg/m³
    assert convert_value(0.01, "mg/m³", UNIT_UGM3) == pytest.approx(10)


@pytest.mark.parametrize(
    "source_unit",
    [
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # canonical Greek mu
        "µg/m³",  # micro sign alias
        "ug/m³",  # ASCII alias
    ],
)
def test_convert_value_ugm3_aliases(source_unit: str) -> None:
    """Canonical and alias µg/m³ unit strings all hit the target unit."""
    assert convert_value(7, source_unit, UNIT_UGM3) == pytest.approx(7)


@pytest.mark.parametrize(
    "source_unit",
    [
        CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,  # canonical
        "mg/m³",
    ],
)
def test_convert_value_mgm3_aliases(source_unit: str) -> None:
    """Canonical and alias mg/m³ unit strings all hit the target unit."""
    assert convert_value(2, source_unit, UNIT_MGM3) == pytest.approx(2)


def test_convert_value_molar_mass() -> None:
    """Test ppm/ppb to mass concentration conversions via molar mass."""
    # 1 ppm CO2 ≈ MOLAR_MASS_CO2 / 24.45 mg/m³
    expected = MOLAR_MASS_CO2 / 24.45
    assert convert_value(
        1, "ppm", UNIT_MGM3, molar_mass=MOLAR_MASS_CO2
    ) == pytest.approx(expected)

    # Same in µg/m³ → 1000× larger
    assert convert_value(
        1, "ppm", UNIT_UGM3, molar_mass=MOLAR_MASS_CO2
    ) == pytest.approx(expected * 1000)


def test_convert_value_unknown_unit() -> None:
    """Test convert returns None for unknown source units without molar mass."""
    assert convert_value(1, "weird", UNIT_PPM) is None
    # ppm into a mass unit without molar mass cannot be resolved.
    assert convert_value(1, "ppm", UNIT_MGM3) is None


@pytest.mark.parametrize(
    "molar_mass",
    [MOLAR_MASS_TVOC, MOLAR_MASS_HCHO],
)
def test_convert_value_molar_masses_present(molar_mass: float) -> None:
    """Smoke-test all renamed molar-mass constants are usable."""
    assert convert_value(1, "ppm", UNIT_MGM3, molar_mass=molar_mass) == pytest.approx(
        molar_mass / 24.45
    )


async def test_voc_conflict_excluded(hass: HomeAssistant) -> None:
    """Test that configuring both tVOC and VOC index lets controller skip neither."""
    # The flow rejects this combination, but the controller itself should still
    # tolerate it: each resolver runs independently.
    hass.states.async_set("sensor.tvoc", 0.05, {ATTR_UNIT_OF_MEASUREMENT: "mg/m³"})
    hass.states.async_set("sensor.voc", 50)
    controller = IndoorAirQualityController(
        hass,
        "test",
        "Test",
        {CONF_TVOC: "sensor.tvoc", CONF_VOC_INDEX: "sensor.voc"},
    )
    controller.update()
    attrs = controller.extra_state_attributes
    assert attrs[ATTR_SOURCE_INDEX_TPL.format("tvoc")] == 5
    assert attrs[ATTR_SOURCE_INDEX_TPL.format("voc_index")] == 5


async def test_hcho_and_no2_levels(hass: HomeAssistant) -> None:
    """Test HCHO and NO2 bands using the µg/m³ targets."""
    controller = IndoorAirQualityController(
        hass,
        "test",
        "Test",
        {CONF_HCHO: "sensor.hcho", CONF_NO2: "sensor.no2"},
    )
    hass.states.async_set("sensor.hcho", 5, {ATTR_UNIT_OF_MEASUREMENT: "µg/m³"})
    hass.states.async_set("sensor.no2", 100, {ATTR_UNIT_OF_MEASUREMENT: "µg/m³"})
    controller.update()
    attrs = controller.extra_state_attributes
    assert attrs[ATTR_SOURCE_INDEX_TPL.format("hcho")] == 5
    assert attrs[ATTR_SOURCE_INDEX_TPL.format("no2")] == 5


async def test_iaq_index_state_class(hass: HomeAssistant) -> None:
    """The numeric IAQ index sensor exposes a measurement state class."""
    hass.states.async_set(
        "sensor.temp", 20, {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCES: {CONF_TEMPERATURE: "sensor.temp"},
            CONF_STANDARD: STANDARD_UK,
        },
        title="Bedroom",
        unique_id="bedroom",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.bedroom_index")
    assert state is not None
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize(
    "data",
    [
        {CONF_SOURCES: {}, CONF_STANDARD: "uk"},
        {CONF_SOURCES: {CONF_TEMPERATURE: "sensor.t"}, CONF_STANDARD: "not_a_standard"},
        {CONF_SOURCES: {"unknown_key": "sensor.x"}, CONF_STANDARD: "uk"},
    ],
    ids=["empty_sources", "unknown_standard", "only_unknown_source_keys"],
)
async def test_invalid_entry_data_raises(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    """Invalid entry data should raise ConfigEntryError."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        title="Bad",
        unique_id="bad",
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR


async def test_state_resets_when_all_sources_unavailable(
    hass: HomeAssistant,
) -> None:
    """Index, level and per-source attributes clear when no source resolves."""
    hass.states.async_set(
        "sensor.t", 17, {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set("sensor.h", 50, {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE})

    controller = IndoorAirQualityController(
        hass,
        "test",
        "Test",
        {CONF_TEMPERATURE: "sensor.t", CONF_HUMIDITY: "sensor.h"},
    )
    controller.update()
    assert controller.iaq_index is not None
    assert controller.iaq_level is not None
    assert ATTR_SOURCE_INDEX_TPL.format(CONF_TEMPERATURE) in (
        controller.extra_state_attributes
    )

    hass.states.async_remove("sensor.t")
    hass.states.async_remove("sensor.h")
    controller.update()

    assert controller.iaq_index is None
    assert controller.iaq_level is None
    assert controller.extra_state_attributes == {
        ATTR_SOURCES_SET: 2,
        ATTR_SOURCES_USED: 0,
    }


async def test_state_resets_for_unknown_standard(hass: HomeAssistant) -> None:
    """An unknown rating standard clears any previously computed state."""
    hass.states.async_set(
        "sensor.t", 17, {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    controller = IndoorAirQualityController(
        hass, "test", "Test", {CONF_TEMPERATURE: "sensor.t"}
    )
    controller.update()
    assert controller.iaq_index is not None

    controller._standard = "not_a_standard"
    controller.update()

    assert controller.iaq_index is None
    assert controller.iaq_level is None
    assert controller.extra_state_attributes == {
        ATTR_SOURCES_SET: 1,
        ATTR_SOURCES_USED: 0,
    }
