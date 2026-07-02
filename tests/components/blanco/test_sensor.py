"""Tests for sensor.py — BlancoSensorEntity."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from blanco_smart_home_api_client import BlancoErrorType

from homeassistant.components.blanco.definitions import BlancoDeviceType
from homeassistant.components.blanco.sensor import (
    _DESC_CO2_REST,
    _DESC_ERROR_COUNT_CRITICAL,
    _DESC_ERROR_COUNT_WARNING,
    _DESC_ONLINE,
    SENSOR_DESCRIPTIONS_BY_TYPE,
    BlancoSensorEntity,
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
            },
            {
                "err_code": 202,
                "err_type": BlancoErrorType.WARNING,
                "err_ts": 1700000000001,
            },
        ],
        "info": {},
    },
}


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

    def test_error_count_critical_with_one_critical_error(self) -> None:
        """native_value for error_count_critical returns 1 for one CRITICAL error."""
        entity = _make_entity(_DESC_ERROR_COUNT_CRITICAL)
        assert entity.native_value == 1

    def test_error_count_warning_with_one_warning(self) -> None:
        """native_value for error_count_warning returns 1 for one WARNING error."""
        entity = _make_entity(_DESC_ERROR_COUNT_WARNING)
        assert entity.native_value == 1

    def test_error_count_critical_ignores_warnings(self) -> None:
        """error_count_critical returns 0 when only WARNING errors are present."""
        data = {
            **SAMPLE_DATA,
            "errors": {
                "errors": [
                    {
                        "err_code": 200,
                        "err_type": BlancoErrorType.WARNING,
                        "err_ts": 1700000000000,
                    }
                ],
                "info": {},
            },
        }
        entity = _make_entity(_DESC_ERROR_COUNT_CRITICAL, data=data)
        assert entity.native_value == 0

    def test_error_count_warning_ignores_critical(self) -> None:
        """error_count_warning returns 0 when only CRITICAL errors are present."""
        data = {
            **SAMPLE_DATA,
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
        entity = _make_entity(_DESC_ERROR_COUNT_WARNING, data=data)
        assert entity.native_value == 0

    def test_error_count_critical_ignores_info(self) -> None:
        """error_count_critical returns 0 when only INFO errors are present."""
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
        entity = _make_entity(_DESC_ERROR_COUNT_CRITICAL, data=data)
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

    def test_error_count_critical_returns_only_critical_errors(self) -> None:
        """extra_state_attributes for error_count_critical lists only CRITICAL errors."""
        entity = _make_entity(_DESC_ERROR_COUNT_CRITICAL)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "errors" in attrs
        assert len(attrs["errors"]) == 1
        assert attrs["errors"][0]["err_type"] == "CRITICAL"

    def test_error_count_warning_returns_only_warnings(self) -> None:
        """extra_state_attributes for error_count_warning lists only WARNING errors."""
        entity = _make_entity(_DESC_ERROR_COUNT_WARNING)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "errors" in attrs
        assert len(attrs["errors"]) == 1
        assert attrs["errors"][0]["err_type"] == "WARNING"

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

    def test_all_device_types_include_online(self) -> None:
        """Every device type includes the online sensor."""
        for dev_type in SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "online" in self._keys(dev_type), f"Missing 'online' for {dev_type}"

    def test_all_device_types_include_error_count_critical(self) -> None:
        """Every device type includes the error_count_critical sensor."""
        for dev_type in SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "error_count_critical" in self._keys(dev_type), (
                f"Missing 'error_count_critical' for {dev_type}"
            )

    def test_all_device_types_include_error_count_warning(self) -> None:
        """Every device type includes the error_count_warning sensor."""
        for dev_type in SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "error_count_warning" in self._keys(dev_type), (
                f"Missing 'error_count_warning' for {dev_type}"
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

    def test_error_count_critical_is_diagnostic(self) -> None:
        """_DESC_ERROR_COUNT_CRITICAL must be categorised as DIAGNOSTIC."""
        assert _DESC_ERROR_COUNT_CRITICAL.entity_category == EntityCategory.DIAGNOSTIC

    def test_error_count_warning_is_diagnostic(self) -> None:
        """_DESC_ERROR_COUNT_WARNING must be categorised as DIAGNOSTIC."""
        assert _DESC_ERROR_COUNT_WARNING.entity_category == EntityCategory.DIAGNOSTIC
