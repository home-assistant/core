"""Preserve identities and explicit preferences when changing PF presentation."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_INPUT


@pytest.mark.parametrize("unique_id", ["test-meter_PF_A", "test-meter-0-6"])
@pytest.mark.parametrize(
    ("unit_options", "expected", "expected_unit"),
    [({}, "0.95", None), ({"unit_of_measurement": "%"}, "95.0", "%")],
)
@pytest.mark.parametrize(
    "private_options", [{}, {"suggested_unit_of_measurement": "%"}]
)
async def test_existing_pf_display(
    hass: HomeAssistant,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    unique_id: str,
    unit_options: dict[str, str],
    private_options: dict[str, str],
    expected: str,
    expected_unit: str | None,
) -> None:
    """Only migrate the old default unit; retain user units and entity IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meter",
        unique_id="test-meter",
        data=MOCK_INPUT,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        unique_id,
        config_entry=entry,
        original_device_class="power_factor",
        unit_of_measurement="%",
        suggested_object_id="original_pf",
    )
    entity_registry.async_update_entity_options(old.entity_id, "sensor", unit_options)
    entity_registry.async_update_entity_options(
        old.entity_id, "sensor.private", private_options
    )
    mock_meter.return_value.async_get_data.return_value = {
        "Model": "WEM3080T",
        "sn": "test-meter",
        "PF_A": 0.95,
    }
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(old.entity_id)
    assert state.state == expected
    assert state.attributes.get("unit_of_measurement") == expected_unit
    assert entity_registry.async_get(old.entity_id).unique_id == "test-meter_PF_A"
    assert entry.minor_version == 2


async def test_future_entry_version(hass: HomeAssistant) -> None:
    """Never downgrade a future config-entry schema."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=MOCK_INPUT)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
