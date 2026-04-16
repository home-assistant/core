"""Tests for sensor.py — BlancoSensorEntity and AQUA computed helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from blanco_smart_home_api_client import BlancoErrorType
import pytest

from homeassistant.components.blanco.definitions import BlancoDeviceType
from homeassistant.components.blanco.sensor import (
    _DESC_CO2_REST,
    _DESC_ERROR_COUNT,
    _DESC_ONLINE,
    SENSOR_DESCRIPTIONS_BY_TYPE,
    BlancoSensorEntity,
    _aqua_filter_remaining_days,
    _aqua_filter_remaining_volume,
    _aqua_filter_rest,
)
from homeassistant.helpers.entity import EntityCategory

# ── Shared test data ───────────────────────────────────────────────────────────

SAMPLE_DATA: dict = {
    "system": {
        "params": {"dev_name": "My BLANCO"},
        "info": {"online": 1700000000000},
    },
    "status": {
        "params": {
            "co2_rest": 75,
            "filter_flow_total": 400000,
            "filter_age": 480,
        },
        "info": {},
    },
    "settings": {
        "params": {
            "set_point_cooling": 8,
            "child_protect": False,
            "absence_mode_active": True,
        },
        "info": {},
    },
    "errors": {
        "errors": [
            {
                "err_code": 101,
                "err_type": BlancoErrorType.CRITICAL,
                "err_ts": 1700000000000,
            }
        ],
        "info": {},
    },
}


# ── AQUA computed helpers ──────────────────────────────────────────────────────


class TestAquaFilterRemainingVolume:
    """Tests for _aqua_filter_remaining_volume."""

    def test_normal_value(self) -> None:
        """400 000 mL consumed → 2000 - 400 = 1600 L remaining."""
        result = _aqua_filter_remaining_volume({"filter_flow_total": 400000})
        assert result == pytest.approx(1600.0)

    def test_clamps_to_zero_when_overused(self) -> None:
        """A value beyond the 2000 L capacity is clamped to 0."""
        result = _aqua_filter_remaining_volume({"filter_flow_total": 3000000})
        assert result == pytest.approx(0.0)

    def test_returns_none_when_key_absent(self) -> None:
        """Returns None when the filter_flow_total key is missing."""
        assert _aqua_filter_remaining_volume({}) is None


class TestAquaFilterRemainingDays:
    """Tests for _aqua_filter_remaining_days."""

    def test_normal_value(self) -> None:
        """480 hours of age → 120 - 480/24 = 120 - 20 = 100 days remaining."""
        result = _aqua_filter_remaining_days({"filter_age": 480})
        assert result == pytest.approx(100.0)

    def test_clamps_to_zero_when_overused(self) -> None:
        """An age beyond the 120-day limit is clamped to 0."""
        result = _aqua_filter_remaining_days({"filter_age": 99999})
        assert result == pytest.approx(0.0)

    def test_returns_none_when_key_absent(self) -> None:
        """Returns None when the filter_age key is missing."""
        assert _aqua_filter_remaining_days({}) is None


class TestAquaFilterRest:
    """Tests for _aqua_filter_rest."""

    def test_returns_minimum_of_volume_and_days_percentages(self) -> None:
        """Result is min(vol/2000, days/120) * 100 for the given inputs."""
        # vol_pct = 1600/2000 = 0.8 (80%)
        # days_pct = 100/120 ≈ 0.833 (83.3%)
        # min → 0.8 → 80.0%
        result = _aqua_filter_rest({"filter_flow_total": 400000, "filter_age": 480})
        assert result == pytest.approx(80.0)

    def test_returns_none_when_volume_absent(self) -> None:
        """Returns None when filter_flow_total is missing."""
        assert _aqua_filter_rest({"filter_age": 480}) is None

    def test_returns_none_when_days_absent(self) -> None:
        """Returns None when filter_age is missing."""
        assert _aqua_filter_rest({"filter_flow_total": 400000}) is None


# ── BlancoSensorEntity helpers ─────────────────────────────────────────────────


def _make_entity(
    description: object,
    data: dict | None = None,
    dev_type: BlancoDeviceType = BlancoDeviceType.AIO,
) -> BlancoSensorEntity:
    """Construct a BlancoSensorEntity without invoking the HA entity lifecycle.

    Uses __new__ to bypass __init__ and injects the coordinator and description
    directly so property methods can be exercised in isolation.
    """
    entity: BlancoSensorEntity = BlancoSensorEntity.__new__(BlancoSensorEntity)
    coordinator = MagicMock()
    coordinator.dev_id = "abc123devid"
    coordinator.serial = "SN123456"
    coordinator.dev_type = dev_type
    coordinator.data = data if data is not None else SAMPLE_DATA
    entity.coordinator = coordinator
    entity.entity_description = description
    return entity


# ── native_value ───────────────────────────────────────────────────────────────


class TestNativeValue:
    """Tests for BlancoSensorEntity.native_value."""

    def test_co2_rest_returns_integer_value(self) -> None:
        """native_value for co2_rest returns 75 from SAMPLE_DATA."""
        entity = _make_entity(_DESC_CO2_REST)
        assert entity.native_value == 75

    def test_online_returns_utc_datetime(self) -> None:
        """native_value for online converts the ms timestamp to a UTC datetime."""
        entity = _make_entity(_DESC_ONLINE)
        value = entity.native_value
        assert isinstance(value, datetime)
        expected = datetime.fromtimestamp(1700000000000 / 1000, tz=UTC)
        assert value == expected

    def test_online_returns_none_when_key_absent(self) -> None:
        """native_value for online returns None when the key is absent in info."""
        data = {
            "system": {"params": {}, "info": {}},
            "status": SAMPLE_DATA["status"],
            "settings": SAMPLE_DATA["settings"],
            "errors": SAMPLE_DATA["errors"],
        }
        entity = _make_entity(_DESC_ONLINE, data=data)
        assert entity.native_value is None

    def test_error_count_with_one_critical_error(self) -> None:
        """native_value for error_count returns 1 when there is one CRITICAL error."""
        entity = _make_entity(_DESC_ERROR_COUNT)
        assert entity.native_value == 1

    def test_error_count_with_only_info_errors_returns_zero(self) -> None:
        """native_value for error_count returns 0 when errors are INFO-level only."""
        data = {
            **SAMPLE_DATA,
            "errors": {
                "errors": [
                    {
                        "err_code": 200,
                        "err_type": BlancoErrorType.INFO,
                        "err_ts": 1700000000000,
                    }
                ],
                "info": {},
            },
        }
        entity = _make_entity(_DESC_ERROR_COUNT, data=data)
        assert entity.native_value == 0

    def test_co2_rest_returns_none_when_key_absent(self) -> None:
        """native_value for co2_rest returns None when the key is absent in params."""
        data = {
            **SAMPLE_DATA,
            "status": {"params": {}, "info": {}},
        }
        entity = _make_entity(_DESC_CO2_REST, data=data)
        assert entity.native_value is None


# ── extra_state_attributes ─────────────────────────────────────────────────────


class TestExtraStateAttributes:
    """Tests for BlancoSensorEntity.extra_state_attributes."""

    def test_error_count_returns_errors_list(self) -> None:
        """extra_state_attributes for error_count returns a dict with an errors list."""
        entity = _make_entity(_DESC_ERROR_COUNT)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "errors" in attrs
        assert len(attrs["errors"]) == 1
        assert attrs["errors"][0]["err_type"] == "CRITICAL"

    def test_co2_rest_returns_none(self) -> None:
        """extra_state_attributes for co2_rest (non-error sensor) returns None."""
        entity = _make_entity(_DESC_CO2_REST)
        assert entity.extra_state_attributes is None


# ── SENSOR_DESCRIPTIONS_BY_TYPE lookup ────────────────────────────────────────


class TestSensorDescriptionsByType:
    """Tests for the SENSOR_DESCRIPTIONS_BY_TYPE device-type lookup table."""

    def _keys(self, dev_type: BlancoDeviceType) -> set[str]:
        """Return the set of entity description keys for a given device type."""
        return {d.key for d in SENSOR_DESCRIPTIONS_BY_TYPE[dev_type]}

    def test_aio_excludes_actions_and_stats_sensors(self) -> None:
        """AIO descriptions no longer include actions or stats sensors."""
        keys = self._keys(BlancoDeviceType.AIO)
        assert "water_total" not in keys
        assert "water_today" not in keys

    def test_soda_excludes_water_hot(self) -> None:
        """SODA descriptions do not include the water_hot sensor."""
        assert "water_hot" not in self._keys(BlancoDeviceType.SODA)

    def test_aqua_includes_filter_remaining_volume(self) -> None:
        """AQUA descriptions include the filter_remaining_volume sensor."""
        assert "filter_remaining_volume" in self._keys(BlancoDeviceType.AQUA)

    def test_aqua_includes_filter_remaining_days(self) -> None:
        """AQUA descriptions include the filter_remaining_days sensor."""
        assert "filter_remaining_days" in self._keys(BlancoDeviceType.AQUA)

    def test_all_device_types_include_online(self) -> None:
        """Every device type includes the online sensor."""
        for dev_type in SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "online" in self._keys(dev_type), f"Missing 'online' for {dev_type}"

    def test_all_device_types_include_error_count(self) -> None:
        """Every device type includes the error_count sensor."""
        for dev_type in SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "error_count" in self._keys(dev_type), (
                f"Missing 'error_count' for {dev_type}"
            )

    def test_soda2_has_only_common_sensors(self) -> None:
        """SODA2 descriptions contain only the common sensors."""
        keys = self._keys(BlancoDeviceType.SODA2)
        assert "water_today" not in keys
        assert "water_total" not in keys

    def test_filter_has_only_common_sensors(self) -> None:
        """FILTER descriptions contain only the common sensors."""
        keys = self._keys(BlancoDeviceType.FILTER)
        assert "water_today" not in keys


# ── EntityCategory ─────────────────────────────────────────────────────────────


class TestEntityCategory:
    """Verify diagnostic entity_category assignments."""

    def test_online_is_diagnostic(self) -> None:
        """_DESC_ONLINE must be categorised as DIAGNOSTIC."""
        assert _DESC_ONLINE.entity_category == EntityCategory.DIAGNOSTIC

    def test_error_count_is_diagnostic(self) -> None:
        """_DESC_ERROR_COUNT must be categorised as DIAGNOSTIC."""
        assert _DESC_ERROR_COUNT.entity_category == EntityCategory.DIAGNOSTIC
