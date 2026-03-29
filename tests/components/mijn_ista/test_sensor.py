"""Tests for mijn_ista sensor platform."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant

from homeassistant.components.mijn_ista.const import DOMAIN
from homeassistant.components.mijn_ista.coordinator import (
    MonthEntry,
    MonthServiceData,
    _parse_customer,
)
from homeassistant.components.mijn_ista.sensor import (
    MijnIstaSensor,
    _build_sensors,
    _find_month,
    _parse_dt,
    _translate_service,
)

from .conftest import MOCK_AVG_VALUES, MOCK_MONTH_VALUES, MOCK_USER_VALUES


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestTranslateService:
    """Tests for the _translate_service helper."""

    def test_english_translates_verwarming(self):
        """English locale should map Verwarming to Heating."""
        assert _translate_service("Verwarming", "en") == "Heating"

    def test_english_translates_warm_water(self):
        """English locale should map Warm water to Hot water."""
        assert _translate_service("Warm water", "en") == "Hot water"

    def test_english_unknown_service_passes_through(self):
        """Unknown service names should pass through unchanged."""
        assert _translate_service("Zonnepanelen", "en") == "Zonnepanelen"

    def test_dutch_passes_through(self):
        """Dutch locale should not translate service names."""
        assert _translate_service("Verwarming", "nl") == "Verwarming"

    def test_german_passes_through(self):
        """Non-English locales should not translate service names."""
        assert _translate_service("Verwarming", "de") == "Verwarming"

    def test_en_gb_locale_translates(self):
        """en-GB locale should also trigger English translation."""
        assert _translate_service("Verwarming", "en-GB") == "Heating"


class TestFindMonth:
    """Tests for the _find_month helper."""

    def test_returns_most_recent_entry_with_data(self):
        """Should return the first MonthEntry that contains the requested service."""
        empty = MonthEntry(year=2024, month=12, avg_temp=None, services={})
        has_data = MonthEntry(
            year=2024,
            month=11,
            avg_temp=8.2,
            services={
                1: MonthServiceData(
                    service_id=1,
                    total_consumption=4.2,
                    building_average=5.0,
                    has_approximation=False,
                    device_consumptions=[],
                )
            },
        )
        result = _find_month([empty, has_data], 1)
        assert result is has_data

    def test_returns_none_when_no_entry_has_data(self):
        """Should return None when no entry contains the requested service."""
        empty = MonthEntry(year=2024, month=12, avg_temp=None, services={})
        assert _find_month([empty], 99) is None

    def test_returns_none_for_empty_list(self):
        """Should return None for an empty monthly list."""
        assert _find_month([], 1) is None

    def test_skips_empty_first_month(self):
        """Most recent month with empty services should be skipped."""
        current = MonthEntry(year=2024, month=12, avg_temp=None, services={})
        prior = MonthEntry(
            year=2024,
            month=11,
            avg_temp=8.2,
            services={
                1: MonthServiceData(
                    service_id=1,
                    total_consumption=4.2,
                    building_average=5.0,
                    has_approximation=False,
                    device_consumptions=[],
                )
            },
        )
        result = _find_month([current, prior], 1)
        assert result is prior


class TestParseDt:
    """Tests for the _parse_dt helper."""

    def test_valid_iso_string(self):
        """Valid ISO date string should return a UTC-aware datetime."""
        result = _parse_dt("2024-01-01T00:00:00")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None  # UTC-aware

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert _parse_dt("") is None

    def test_invalid_string_returns_none(self):
        """Unparseable string should return None."""
        assert _parse_dt("not-a-date") is None


# ---------------------------------------------------------------------------
# Sensor factory
# ---------------------------------------------------------------------------


def _make_customer_data():
    """Build a CustomerData instance from the shared mock fixtures."""
    cus = MOCK_USER_VALUES["Cus"][0]
    return _parse_customer(cus, MOCK_MONTH_VALUES, MOCK_AVG_VALUES)


class TestBuildSensors:
    """Tests for the _build_sensors factory function."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant):
        """Minimal coordinator stub for sensor factory tests."""
        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": _make_customer_data()}
        return coord

    def test_returns_list_of_sensors(self, coordinator):
        """Should return a non-empty list of MijnIstaSensor instances."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        assert len(sensors) > 0
        assert all(isinstance(s, MijnIstaSensor) for s in sensors)

    def test_unique_ids_are_unique(self, coordinator):
        """Every sensor in the list must have a distinct unique_id."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        uids = [s._attr_unique_id for s in sensors]
        assert len(uids) == len(set(uids))

    def test_unique_id_format(self, coordinator):
        """Unique IDs must follow the domain_cuid_suffix pattern."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        for s in sensors:
            assert s._attr_unique_id.startswith(f"{DOMAIN}_test-cuid-abc123_")

    def test_temperature_sensors_present(self, coordinator):
        """Both temperature sensors should always be created."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        names = [s._attr_name for s in sensors]
        assert "Temperature" in names
        assert "Temperature Previous" in names

    def test_annual_current_sensor_english(self, hass: HomeAssistant):
        """English HA language should produce translated sensor names."""
        coord = MagicMock()
        coord.hass = hass
        hass.config.language = "en"
        customer = _make_customer_data()
        coord.data = {"test-cuid-abc123": customer}
        sensors = _build_sensors(coord, "test-cuid-abc123", customer)
        names = [s._attr_name for s in sensors]
        assert "Heating Current" in names
        assert "Hot water Current" in names

    def test_annual_current_sensor_dutch(self, hass: HomeAssistant):
        """Dutch HA language should keep Dutch service names."""
        coord = MagicMock()
        coord.hass = hass
        hass.config.language = "nl"
        customer = _make_customer_data()
        coord.data = {"test-cuid-abc123": customer}
        sensors = _build_sensors(coord, "test-cuid-abc123", customer)
        names = [s._attr_name for s in sensors]
        assert "Verwarming Current" in names
        assert "Warm water Current" in names

    def test_heating_sensor_has_energy_device_class(self, coordinator):
        """Heating (Gigajoule) sensor should have ENERGY device class."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        heating_current = next(s for s in sensors if s._attr_name == "Heating Current")
        assert heating_current._attr_device_class == SensorDeviceClass.ENERGY
        assert (
            heating_current._attr_native_unit_of_measurement == UnitOfEnergy.GIGA_JOULE
        )

    def test_water_sensor_has_water_device_class(self, coordinator):
        """Water (m3) sensor should have WATER device class."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        water_current = next(
            s for s in sensors if s._attr_name == "Hot water Current"
        )
        assert water_current._attr_device_class == SensorDeviceClass.WATER
        assert (
            water_current._attr_native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
        )

    def test_change_sensor_uses_measurement_state_class(self, coordinator):
        """Year-over-year change sensor should use MEASUREMENT state class."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        change = next(s for s in sensors if s._attr_name == "Heating Change")
        assert change._attr_state_class == SensorStateClass.MEASUREMENT

    def test_annual_sensor_uses_total_state_class(self, coordinator):
        """Annual total sensor should use TOTAL state class."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        assert current._attr_state_class == SensorStateClass.TOTAL

    def test_building_avg_sensor_uses_measurement(self, coordinator):
        """Building average sensor should use MEASUREMENT state class."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        avg = next(s for s in sensors if s._attr_name == "Heating Building Avg")
        assert avg._attr_state_class == SensorStateClass.MEASUREMENT

    def test_monthly_sensors_present(self, coordinator):
        """Monthly total and monthly average sensors should be created."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        names = [s._attr_name for s in sensors]
        assert "Heating Month" in names
        assert "Heating Month Avg" in names

    def test_monthly_sensors_created_when_first_month_is_empty(
        self, hass: HomeAssistant
    ):
        """Monthly sensors must be created even if monthly[0] has no ServiceConsumptions."""
        # Prepend a current-month entry with no service data (in-progress month)
        cus = MOCK_USER_VALUES["Cus"][0]
        month_data = copy.deepcopy(MOCK_MONTH_VALUES)
        month_data["mc"].insert(
            0, {"y": 2024, "m": 12, "at": None, "ServiceConsumptions": []}
        )
        customer = _parse_customer(cus, month_data, MOCK_AVG_VALUES)

        # monthly[0] is now December with empty services
        assert customer.monthly[0].month == 12
        assert customer.monthly[0].services == {}

        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": customer}

        sensors = _build_sensors(coord, "test-cuid-abc123", customer)
        names = [s._attr_name for s in sensors]
        assert "Heating Month" in names
        assert "Heating Month Avg" in names

    def test_monthly_sensor_value_skips_empty_first_month(self, hass: HomeAssistant):
        """native_value for Month sensor must use the most recent month with data."""
        cus = MOCK_USER_VALUES["Cus"][0]
        month_data = copy.deepcopy(MOCK_MONTH_VALUES)
        month_data["mc"].insert(
            0, {"y": 2024, "m": 12, "at": None, "ServiceConsumptions": []}
        )
        customer = _parse_customer(cus, month_data, MOCK_AVG_VALUES)

        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": customer}

        sensors = _build_sensors(coord, "test-cuid-abc123", customer)
        month_sensor = next(s for s in sensors if s._attr_name == "Heating Month")
        # Should return Nov 2024 value (4.2), not None from empty Dec entry
        assert month_sensor.native_value == 4.2


# ---------------------------------------------------------------------------
# MijnIstaSensor.native_value
# ---------------------------------------------------------------------------


class TestSensorNativeValue:
    """Tests for MijnIstaSensor.native_value."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant):
        """Coordinator stub with full customer data loaded."""
        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": _make_customer_data()}
        return coord

    def test_annual_current_value(self, coordinator):
        """Current annual total should match mock fixture value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        assert current.native_value == 42.5

    def test_annual_previous_value(self, coordinator):
        """Previous annual total should match mock fixture value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        previous = next(s for s in sensors if s._attr_name == "Heating Previous")
        assert previous.native_value == 48.0

    def test_change_pct_value(self, coordinator):
        """Year-over-year change percentage should match mock fixture value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        change = next(s for s in sensors if s._attr_name == "Heating Change")
        assert change.native_value == -11.5

    def test_monthly_value(self, coordinator):
        """Monthly total should return the most recent month's value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        month = next(s for s in sensors if s._attr_name == "Heating Month")
        assert month.native_value == 4.2

    def test_temperature_current(self, coordinator):
        """Current period temperature should match mock fixture value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        temp = next(s for s in sensors if s._attr_name == "Temperature")
        assert temp.native_value == 10.5

    def test_temperature_previous(self, coordinator):
        """Previous period temperature should match mock fixture value."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        temp_prev = next(s for s in sensors if s._attr_name == "Temperature Previous")
        assert temp_prev.native_value == 9.8

    def test_returns_none_when_coordinator_data_empty(self, coordinator):
        """Should return None when the cuid is not found in coordinator data."""
        coordinator.data = {}
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        # coordinator.data is now {} — cuid not found
        assert current.native_value is None

    def test_returns_none_when_coordinator_data_is_none(self, coordinator):
        """Should return None when coordinator data is None."""
        coordinator.data = None
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        assert current.native_value is None


# ---------------------------------------------------------------------------
# last_reset
# ---------------------------------------------------------------------------


class TestLastReset:
    """Tests for MijnIstaSensor.last_reset."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant):
        """Coordinator stub with full customer data loaded."""
        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": _make_customer_data()}
        return coord

    def test_annual_current_last_reset(self, coordinator):
        """Annual current sensor last_reset should be the period start date."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        lr = current.last_reset
        assert lr is not None
        assert isinstance(lr, datetime)
        assert lr.year == 2024
        assert lr.month == 1
        assert lr.day == 1

    def test_monthly_last_reset_is_first_of_month(self, coordinator):
        """Monthly sensor last_reset should be the first day of the reported month."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        month_sensor = next(s for s in sensors if s._attr_name == "Heating Month")
        lr = month_sensor.last_reset
        assert lr is not None
        assert lr == datetime(2024, 11, 1, tzinfo=timezone.utc)

    def test_measurement_sensor_has_no_last_reset(self, coordinator):
        """MEASUREMENT state-class sensors should have no last_reset."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        change = next(s for s in sensors if s._attr_name == "Heating Change")
        assert change.last_reset is None

    def test_temperature_has_no_last_reset(self, coordinator):
        """Temperature sensor should have no last_reset."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        temp = next(s for s in sensors if s._attr_name == "Temperature")
        assert temp.last_reset is None


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


class TestExtraStateAttributes:
    """Tests for MijnIstaSensor.extra_state_attributes."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant):
        """Coordinator stub with full customer data loaded."""
        coord = MagicMock()
        coord.hass = hass
        coord.data = {"test-cuid-abc123": _make_customer_data()}
        return coord

    def test_annual_current_has_period_dates(self, coordinator):
        """Annual current sensor attrs should include period start/end and meters."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        current = next(s for s in sensors if s._attr_name == "Heating Current")
        attrs = current.extra_state_attributes
        assert "period_start" in attrs
        assert "period_end" in attrs
        assert "meters" in attrs

    def test_monthly_has_prior_months(self, coordinator):
        """Monthly sensor attrs should include month and prior_months."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        month = next(s for s in sensors if s._attr_name == "Heating Month")
        attrs = month.extra_state_attributes
        assert "prior_months" in attrs
        assert "month" in attrs

    def test_temperature_has_monthly_history(self, coordinator):
        """Temperature sensor attrs should include monthly_history with non-None temps."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        temp = next(s for s in sensors if s._attr_name == "Temperature")
        attrs = temp.extra_state_attributes
        assert "monthly_history" in attrs
        # Only months with non-None avg_temp should be included
        for entry in attrs["monthly_history"]:
            assert entry["avg_temp"] is not None

    def test_no_attrs_fn_returns_empty_dict(self, coordinator):
        """Sensor without attrs_fn should return an empty dict."""
        customer = _make_customer_data()
        sensors = _build_sensors(coordinator, "test-cuid-abc123", customer)
        temp_prev = next(s for s in sensors if s._attr_name == "Temperature Previous")
        # Temperature Previous has no attrs_fn
        assert temp_prev.extra_state_attributes == {}
