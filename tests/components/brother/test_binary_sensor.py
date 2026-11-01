"""Test binary sensor of Brother integration."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.brother.const import UPDATE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import BROTHER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the binary sensors."""
    with patch("homeassistant.components.brother.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_ink(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_ink_brother_client: AsyncMock,
    mock_ink_config_entry: MockConfigEntry,
) -> None:
    """Test states of the binary sensors for an inkjet printer."""
    with patch("homeassistant.components.brother.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_ink_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_ink_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "entity_id",
    [
        "binary_sensor.hl_l2340dw_input_tray_empty",
        "binary_sensor.hl_l2340dw_input_tray_missing",
        "binary_sensor.hl_l2340dw_low_paper",
        "binary_sensor.hl_l2340dw_output_tray_full",
        "binary_sensor.hl_l2340dw_output_tray_missing",
        "binary_sensor.hl_l2340dw_output_tray_near_full",
        "binary_sensor.hl_l2340dw_preventive_maintenance_overdue",
        "binary_sensor.hl_l2340dw_service_requested",
    ],
)
async def test_binary_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test the less critical errors are disabled by default."""
    await init_integration(hass, mock_config_entry)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert hass.states.get(entity_id) is None


async def test_no_binary_sensors_when_printer_errors_unavailable(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no binary sensors are created when the printer does not report errors."""
    mock_brother_client.async_update.return_value = replace(
        BROTHER_DATA, printer_errors=None
    )

    await init_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("binary_sensor.hl_l2340dw_door_open", STATE_ON),
        ("binary_sensor.hl_l2340dw_low_toner", STATE_ON),
        ("binary_sensor.hl_l2340dw_low_paper", STATE_OFF),
        ("binary_sensor.hl_l2340dw_no_toner", STATE_OFF),
    ],
)
async def test_binary_sensor_state_reflects_printer_errors(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the binary sensor state matches the active printer errors."""
    await init_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    entity_id = "binary_sensor.hl_l2340dw_door_open"
    await init_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    mock_brother_client.async_update.side_effect = ConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mock_brother_client.async_update.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
