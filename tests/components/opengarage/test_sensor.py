"""Test OpenGarage optional sensors."""

from unittest.mock import MagicMock

from opengarage.state import normalize_state
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("field", "entity_id", "value", "expected"),
    [
        pytest.param(
            "obstruct", "binary_sensor.garage_abcdef_obstruction", 0, "off", id="clear"
        ),
        pytest.param(
            "obstruct",
            "binary_sensor.garage_abcdef_obstruction",
            1,
            "on",
            id="obstructed",
        ),
        pytest.param(
            "nopenings", "sensor.garage_abcdef_openings", 0, "0", id="zero_openings"
        ),
        pytest.param(
            "nopenings", "sensor.garage_abcdef_openings", "42", "42", id="openings"
        ),
    ],
)
async def test_optional_sensor(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    field: str,
    entity_id: str,
    value: int | str,
    expected: str,
) -> None:
    """Discover optional readings and mark missing capabilities unavailable."""
    coordinator = init_integration.runtime_data
    original = mock_opengarage.get_state.return_value.raw
    assert hass.states.get(entity_id) is None
    mock_opengarage.get_state.return_value = normalize_state({**original, field: value})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    mock_opengarage.get_state.return_value = normalize_state(original)
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_openings_disabled_by_default(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The diagnostic counter is opt-in."""
    mock_opengarage.get_state.return_value = normalize_state(
        {**mock_opengarage.get_state.return_value.raw, "nopenings": 42}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = entity_registry.async_get("sensor.garage_abcdef_openings")
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.unique_id == "12345_nopenings"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_existing_sensors(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Retain legacy sensor values and unique IDs after normalized polling."""
    mock_opengarage.get_state.return_value = normalize_state(
        {
            **mock_opengarage.get_state.return_value.raw,
            "dist": 123,
            "temp": 20,
            "humid": 45,
            "rssi": -60,
            "vehicle": 1,
        }
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    values = {
        entry.unique_id: hass.states.get(entry.entity_id).state for entry in entries
    }
    assert (
        values.items()
        >= {
            "12345_dist": "123",
            "12345_temp": "20",
            "12345_humid": "45",
            "12345_rssi": "-60",
            "12345_vehicle": "on",
        }.items()
    )
