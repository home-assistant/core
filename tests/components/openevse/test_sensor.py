"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_by_default_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the disabled by default sensor entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("sensor.openevse_mock_config_ir_temperature")
    assert state is None

    entry = entity_registry.async_get("sensor.openevse_mock_config_ir_temperature")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    state = hass.states.get("sensor.openevse_mock_config_rtc_temperature")
    assert state is None

    entry = entity_registry.async_get("sensor.openevse_mock_config_rtc_temperature")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_missing_sensor_graceful_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test that missing sensor attributes are handled gracefully."""
    mock_charger.vehicle_soc = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # The sensor with missing attribute should be unknown
    state = hass.states.get("sensor.openevse_mock_config_vehicle_state_of_charge")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Other sensors should still work
    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state is not None
    assert state.state == "charging"


async def test_websocket_callback_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the websocket callback pushes updates to entity state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state
    assert state.state == "charging"

    mock_charger.status = "Sleeping"
    await mock_charger.callback()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state
    assert state.state == "sleeping"


async def test_sensor_unavailable_on_coordinator_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test sensors become unavailable when coordinator times out."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_charger.update.side_effect = TimeoutError("Connection timed out")
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_yaml_import_success(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful YAML import creates deprecated_yaml issue."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, CONF_HOST: "192.168.1.100"}},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue("homeassistant", "deprecated_yaml")
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_yaml_import_unavailable_host(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import with unavailable host creates domain-specific issue."""
    mock_charger.test_and_get.side_effect = TimeoutError("Connection timed out")

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, CONF_HOST: "192.168.1.100"}},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unavailable_host"
    )
    assert issue is not None


async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import when already configured creates deprecated_yaml issue."""
    # Only add the entry, don't set it up - this allows the YAML platform setup
    # to run while the config flow will still see the existing entry
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, CONF_HOST: "192.168.1.100"}},
    )
    await hass.async_block_till_done()

    # When already configured, it should still create deprecated_yaml issue
    issue = issue_registry.async_get_issue("homeassistant", "deprecated_yaml")
    assert issue is not None
    assert issue.issue_domain == DOMAIN


@pytest.mark.parametrize(
    ("raw_status", "expected_state"),
    [
        pytest.param("not connected", "not_connected", id="not_connected"),
        pytest.param("connected", "connected", id="connected"),
        pytest.param("charging", "charging", id="charging"),
        pytest.param("vent required", "vent_required", id="vent_required"),
        pytest.param(
            "diode check failed", "diode_check_failed", id="diode_check_failed"
        ),
        pytest.param("gfci fault", "gfci_fault", id="gfci_fault"),
        pytest.param("no ground", "no_ground", id="no_ground"),
        pytest.param("stuck relay", "stuck_relay", id="stuck_relay"),
        pytest.param(
            "gfci self-test failure",
            "gfci_self_test_failure",
            id="gfci_self_test_failure",
        ),
        pytest.param("over temperature", "over_temperature", id="over_temperature"),
        pytest.param("sleeping", "sleeping", id="sleeping"),
        pytest.param("disabled", "disabled", id="disabled"),
        pytest.param("unknown", STATE_UNKNOWN, id="unknown"),
        pytest.param("unrecognized_raw_status", STATE_UNKNOWN, id="fallback_unknown"),
        pytest.param(None, STATE_UNKNOWN, id="none_status"),
    ],
)
async def test_status_sensor_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    raw_status: str | None,
    expected_state: str,
) -> None:
    """Test status sensor mapping to enum options."""
    mock_charger.status = raw_status
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("sensor.openevse_mock_config_charging_status")
    assert state is not None
    assert state.state == expected_state
