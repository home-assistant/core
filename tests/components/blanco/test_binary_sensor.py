"""Tests for binary_sensor.py — BlancoBinarySensorEntity."""

from __future__ import annotations

from unittest.mock import MagicMock

from blanco_smart_home_api_client import BlancoErrorType

from homeassistant.components.blanco.binary_sensor import (
    _DESC_ABSENCE_MODE_ACTIVE,
    _DESC_CHILD_PROTECT,
    _DESC_CONNECTED,
    _DESC_HAS_ERROR,
    BINARY_SENSOR_DESCRIPTIONS_BY_TYPE,
    BlancoBinarySensorEntity,
)
from homeassistant.components.blanco.definitions import BlancoDeviceType
from homeassistant.helpers.entity import EntityCategory

# ── Shared test data ───────────────────────────────────────────────────────────

SAMPLE_DATA: dict = {
    "system": {
        "params": {"dev_name": "My BLANCO"},
        "info": {"connected": True},
    },
    "settings": {
        "params": {
            "child_protect": False,
            "absence_mode_active": False,
        },
        "info": {},
    },
    "errors": {
        "errors": [
            {
                "err_code": 99,
                "err_type": BlancoErrorType.CRITICAL,
                "err_ts": 1700000000000,
            }
        ],
        "info": {},
    },
    "status": {"params": {}, "info": {}},
    "actions": {"actions": [], "info": {}, "totals": {}},
}


# ── Factory helper ─────────────────────────────────────────────────────────────


def _make_entity(
    description: object,
    data: dict | None = None,
    dev_type: BlancoDeviceType = BlancoDeviceType.AIO,
) -> BlancoBinarySensorEntity:
    """Construct a BlancoBinarySensorEntity without invoking the HA entity lifecycle.

    Uses __new__ to bypass __init__ and injects the coordinator and description
    directly so property methods can be exercised in isolation.
    """
    entity: BlancoBinarySensorEntity = BlancoBinarySensorEntity.__new__(
        BlancoBinarySensorEntity
    )
    coordinator = MagicMock()
    coordinator.dev_id = "abc123devid"
    coordinator.serial = "SN123456"
    coordinator.dev_type = dev_type
    coordinator.data = data if data is not None else SAMPLE_DATA
    entity.coordinator = coordinator
    entity.entity_description = description
    return entity


# ── is_on ──────────────────────────────────────────────────────────────────────


class TestIsOn:
    """Tests for BlancoBinarySensorEntity.is_on."""

    def test_connected_true_when_info_connected_is_true(self) -> None:
        """is_on for connected returns True when info.connected is True."""
        entity = _make_entity(_DESC_CONNECTED)
        assert entity.is_on is True

    def test_connected_false_when_info_connected_is_false(self) -> None:
        """is_on for connected returns False when info.connected is False."""
        data = {
            **SAMPLE_DATA,
            "system": {"params": {}, "info": {"connected": False}},
        }
        entity = _make_entity(_DESC_CONNECTED, data=data)
        assert entity.is_on is False

    def test_connected_none_when_key_absent(self) -> None:
        """is_on for connected returns None when the connected key is absent."""
        data = {
            **SAMPLE_DATA,
            "system": {"params": {}, "info": {}},
        }
        entity = _make_entity(_DESC_CONNECTED, data=data)
        assert entity.is_on is None

    def test_child_protect_false_raw_maps_to_is_on_true_due_to_invert(self) -> None:
        """child_protect=False → is_on=True because invert=True (hot water active)."""
        entity = _make_entity(_DESC_CHILD_PROTECT)
        # SAMPLE_DATA has child_protect=False
        assert entity.is_on is True

    def test_child_protect_true_raw_maps_to_is_on_false_due_to_invert(self) -> None:
        """child_protect=True → is_on=False because invert=True."""
        data = {
            **SAMPLE_DATA,
            "settings": {
                "params": {"child_protect": True, "absence_mode_active": False},
                "info": {},
            },
        }
        entity = _make_entity(_DESC_CHILD_PROTECT, data=data)
        assert entity.is_on is False

    def test_absence_mode_active_false_returns_false(self) -> None:
        """absence_mode_active=False → is_on=False (no inversion)."""
        entity = _make_entity(_DESC_ABSENCE_MODE_ACTIVE)
        # SAMPLE_DATA has absence_mode_active=False
        assert entity.is_on is False

    def test_has_error_true_when_critical_error_present(self) -> None:
        """is_on for has_error returns True when a CRITICAL error is in the list."""
        entity = _make_entity(_DESC_HAS_ERROR)
        assert entity.is_on is True

    def test_has_error_false_when_no_errors(self) -> None:
        """is_on for has_error returns False when the errors list is empty."""
        data = {
            **SAMPLE_DATA,
            "errors": {"errors": [], "info": {}},
        }
        entity = _make_entity(_DESC_HAS_ERROR, data=data)
        assert entity.is_on is False

    def test_has_error_false_when_only_info_errors(self) -> None:
        """is_on for has_error returns False when all errors are INFO-level."""
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
        entity = _make_entity(_DESC_HAS_ERROR, data=data)
        assert entity.is_on is False


# ── extra_state_attributes ─────────────────────────────────────────────────────


class TestExtraStateAttributes:
    """Tests for BlancoBinarySensorEntity.extra_state_attributes."""

    def test_has_error_returns_errors_list_with_critical_type(self) -> None:
        """extra_state_attributes for has_error contains the error with err_type name."""
        entity = _make_entity(_DESC_HAS_ERROR)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "errors" in attrs
        assert len(attrs["errors"]) == 1
        assert attrs["errors"][0]["err_type"] == "CRITICAL"

    def test_connected_returns_none(self) -> None:
        """extra_state_attributes for connected (non-error sensor) returns None."""
        entity = _make_entity(_DESC_CONNECTED)
        assert entity.extra_state_attributes is None


# ── BINARY_SENSOR_DESCRIPTIONS_BY_TYPE lookup ─────────────────────────────────


class TestBinarySensorDescriptionsByType:
    """Tests for the BINARY_SENSOR_DESCRIPTIONS_BY_TYPE device-type lookup table."""

    def _keys(self, dev_type: BlancoDeviceType) -> set[str]:
        """Return the set of entity description keys for a given device type."""
        return {d.key for d in BINARY_SENSOR_DESCRIPTIONS_BY_TYPE[dev_type]}

    def test_aio_includes_child_protect(self) -> None:
        """AIO descriptions include the child_protect binary sensor."""
        assert "child_protect" in self._keys(BlancoDeviceType.AIO)

    def test_aio_includes_absence_mode_active(self) -> None:
        """AIO descriptions include the absence_mode_active binary sensor."""
        assert "absence_mode_active" in self._keys(BlancoDeviceType.AIO)

    def test_soda_excludes_child_protect(self) -> None:
        """SODA descriptions do not include the child_protect binary sensor."""
        assert "child_protect" not in self._keys(BlancoDeviceType.SODA)

    def test_all_device_types_include_connected(self) -> None:
        """Every device type includes the connected binary sensor."""
        for dev_type in BINARY_SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "connected" in self._keys(dev_type), (
                f"Missing 'connected' for {dev_type}"
            )

    def test_all_device_types_include_has_error(self) -> None:
        """Every device type includes the has_error binary sensor."""
        for dev_type in BINARY_SENSOR_DESCRIPTIONS_BY_TYPE:
            assert "has_error" in self._keys(dev_type), (
                f"Missing 'has_error' for {dev_type}"
            )


# ── EntityCategory ─────────────────────────────────────────────────────────────


class TestEntityCategory:
    """Verify diagnostic entity_category assignments."""

    def test_connected_is_diagnostic(self) -> None:
        """_DESC_CONNECTED must be categorised as DIAGNOSTIC."""
        assert _DESC_CONNECTED.entity_category == EntityCategory.DIAGNOSTIC
