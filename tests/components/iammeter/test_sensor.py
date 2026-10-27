"""Test entry lifecycle, legacy import and entity continuity."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import ConnectionError

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MOCK_DATA, MOCK_INPUT

pytestmark = pytest.mark.usefixtures("mock_meter")


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Set up existing measurement semantics and release the entry cleanly."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_Power"
    )
    assert hass.states.get(entity_id).state == "460.0"
    assert hass.states.get(entity_id).attributes["unit_of_measurement"] == "W"
    imported = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_ImportEnergy"
    )
    assert hass.states.get(imported).attributes["state_class"] == "total_increasing"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "test-meter"), mock_entry.entry_id
    )
    assert device.config_entry_id == mock_entry.entry_id
    assert (
        len(er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id))
        == 5
    )
    mock_meter.assert_called_once_with("192.0.2.1", 80)
    mock_meter.return_value.client.get_data.assert_not_called()
    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    calls = mock_meter.return_value.client.get_data.call_count
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done()
    assert mock_meter.return_value.client.get_data.call_count == calls


@pytest.mark.parametrize(
    "error", [ConnectionError(), TimeoutError(), ValueError(), KeyError()]
)
async def test_setup_retry(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    error: Exception,
) -> None:
    """Unavailable meters are retried without creating entities."""
    mock_meter.side_effect = error
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_entity_ids("sensor")


@pytest.mark.parametrize(
    "data", [{**MOCK_DATA, "sn": "another-meter"}, {**MOCK_DATA, "sn": ""}]
)
async def test_wrong_identity_at_setup(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    data: dict[str, Any],
) -> None:
    """A changed device cannot overwrite the existing device's readings."""
    mock_meter.return_value.measurement = data
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError(),
        ValueError(),
        KeyError(),
        {**MOCK_DATA, "sn": "another-meter"},
        {**MOCK_DATA, "Model": "unsupported"},
    ],
)
async def test_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    failure: Exception | dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Failed reads become unavailable; valid reads restore the same entity."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_Power"
    )
    mock_meter.return_value.client.get_data.side_effect = [failure, MOCK_DATA]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "460.0"


@pytest.mark.parametrize("unique_id", ["test-meter_Power", "test-meter-0-2"])
async def test_yaml_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    unique_id: str,
) -> None:
    """Import YAML and retain both generations of entity identities."""
    old = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, unique_id, suggested_object_id="existing_power"
    )
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": DOMAIN, CONF_HOST: "192.0.2.1", CONF_NAME: "Solar"}},
    )
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Solar"
    assert entries[0].data == MOCK_INPUT
    assert hass.states.get(old.entity_id).state == "460.0"
    migrated = entity_registry.async_get(old.entity_id)
    assert migrated.unique_id == "test-meter_Power"
    assert migrated.config_entry_id == entries[0].entry_id
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_iammeter"
    )


async def test_yaml_duplicate(hass: HomeAssistant, mock_entry: MockConfigEntry) -> None:
    """A YAML configuration for an existing entry does not add another meter."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": DOMAIN, CONF_HOST: "192.0.2.1"}}
    )
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_yaml_failed_import(
    hass: HomeAssistant, mock_meter: MagicMock, issue_registry: ir.IssueRegistry
) -> None:
    """Do not tell an offline YAML user migration has succeeded."""
    mock_meter.side_effect = ConnectionError()
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": DOMAIN, CONF_HOST: "192.0.2.1"}}
    )
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)
    assert (
        issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml_iammeter")
        is None
    )


@pytest.mark.parametrize("unique_id", ["test-meter-3-2", "test-meter_Power_NET"])
@pytest.mark.parametrize(("pf_value", "expected"), [(None, "unknown"), (0.95, "95.0")])
async def test_three_phase_optional_values(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    unique_id: str,
    pf_value: float | None,
    expected: str,
) -> None:
    """NET values retain their IDs and absent PF reads as unknown."""
    data = {"Model": "WEM3080T", "sn": "test-meter"}
    data.update(
        {
            f"{key}_{phase}": value
            for phase in ("A", "B", "C", "Net")
            for key, value in (
                ("Voltage", 230),
                ("Current", 2),
                ("Power", 460),
                ("ImportEnergy", 100),
                ("ExportGrid", 10),
                ("Frequency", 50),
            )
        }
    )
    data["PF_A"] = pf_value
    mock_meter.return_value.measurement = data
    old = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        unique_id,
        suggested_object_id="existing_net_power",
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(old.entity_id).unique_id == "test-meter_Power_Net"
    pf = entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, "test-meter_PF_A")
    entity_registry.async_update_entity(pf, disabled_by=None)
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(pf).state == expected


async def test_migration_collision(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Do not overwrite an existing canonical entity during ID migration."""
    old = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, "test-meter-0-2", suggested_object_id="old_power"
    )
    canonical = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, "test-meter_Power", suggested_object_id="power"
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(old.entity_id).unique_id == "test-meter-0-2"
    assert hass.states.get(canonical.entity_id).state == "460.0"
    assert "because it already exists" in caplog.text


@pytest.mark.parametrize(
    ("options", "seconds"), [({}, 30), ({CONF_SCAN_INTERVAL: 5}, 5)]
)
async def test_polling_interval(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    options: dict[str, int],
    seconds: int,
) -> None:
    """Use the chosen interval while old entries retain the original default."""
    mock_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_entry, options=options)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.runtime_data.update_interval == timedelta(seconds=seconds)
    freezer.tick(timedelta(seconds=seconds / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_meter.return_value.client.get_data.assert_not_called()
    mock_meter.return_value.client.get_data.return_value = {**MOCK_DATA, "Power": 690}
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_meter.return_value.client.get_data.assert_called_once()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_Power"
    )
    assert hass.states.get(entity_id).state == "690"
