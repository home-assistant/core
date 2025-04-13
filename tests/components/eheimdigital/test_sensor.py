"""Tests for the sensor module."""

from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.types import EheimDeviceType, FilterErrorCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("classic_vario_mock")
async def test_setup_classic_vario(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform setup for the filter."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    classic_vario_mock: MagicMock,
) -> None:
    """Test the sensor state update."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    classic_vario_mock.current_speed = 10
    classic_vario_mock.error_code = FilterErrorCode.ROTOR_STUCK
    classic_vario_mock.service_hours = 100

    await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

    assert (state := hass.states.get("sensor.mock_classicvario_current_speed"))
    assert state.state == "10"

    assert (state := hass.states.get("sensor.mock_classicvario_error_code"))
    assert state.state == "rotor_stuck"

    assert (
        state := hass.states.get(
            "sensor.mock_classicvario_remaining_hours_until_service"
        )
    )
    assert state.state == str(round(100 / 24, 1))
