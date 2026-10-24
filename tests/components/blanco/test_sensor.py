"""Tests for the BLANCO sensor platform."""

from blanco_smart_home_api_client import BlancoErrorType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.blanco.sensor import SENSOR_DESCRIPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_blanco_client")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the BLANCO sensors."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("key", "err_type", "expected"),
    [
        pytest.param(
            "error_count_critical", BlancoErrorType.CRITICAL, 1, id="critical"
        ),
        pytest.param(
            "error_count_critical",
            BlancoErrorType.WARNING,
            0,
            id="critical_ignores_warning",
        ),
        pytest.param(
            "error_count_critical", BlancoErrorType.INFO, 0, id="critical_ignores_info"
        ),
        pytest.param("error_count_warning", BlancoErrorType.WARNING, 1, id="warning"),
        pytest.param(
            "error_count_warning",
            BlancoErrorType.CRITICAL,
            0,
            id="warning_ignores_critical",
        ),
    ],
)
def test_error_count_value(key: str, err_type: BlancoErrorType, expected: int) -> None:
    """Test the error count sensors only count errors of their own severity."""
    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
    data = {
        "system": {"params": {}, "info": {}},
        "errors": {
            "errors": [
                {"err_code": 101, "err_type": err_type, "err_ts": 1700000000000}
            ],
            "info": {},
        },
    }

    assert description.value_fn(data) == expected
