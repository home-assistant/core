"""Tests for sensor.py — BlancoSensorEntity."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from blanco_smart_home_api_client import BlancoDeviceType, BlancoErrorType

from homeassistant.components.blanco.sensor import (
    _DESC_ERROR_COUNT_CRITICAL,
    _DESC_ERROR_COUNT_WARNING,
    _DESC_ONLINE,
    SENSOR_DESCRIPTIONS_COMMON,
    BlancoSensorEntity,
)
from homeassistant.helpers.entity import EntityCategory

# ── Shared test data ───────────────────────────────────────────────────────────

SAMPLE_DATA: dict = {
    "system": {
        "params": {"dev_name": "My BLANCO"},
        "info": {"online": 1700000000000},
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


# ── SENSOR_DESCRIPTIONS_COMMON ─────────────────────────────────────────────────


class TestSensorDescriptionsCommon:
    """Tests for the SENSOR_DESCRIPTIONS_COMMON tuple used by every device type."""

    def test_includes_online_and_error_counts(self) -> None:
        """The common set includes online, error_count_critical, and error_count_warning."""
        keys = {d.key for d in SENSOR_DESCRIPTIONS_COMMON}
        assert keys == {"online", "error_count_critical", "error_count_warning"}


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
