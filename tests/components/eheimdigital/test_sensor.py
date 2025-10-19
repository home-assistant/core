"""Tests for the sensor module."""

from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.types import EheimDeviceType, FilterErrorCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, get_sensor_display_state, snapshot_platform


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


@pytest.mark.usefixtures("classic_vario_mock")
@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "classic_vario_mock",
            [
                (
                    "sensor.mock_classicvario_current_speed",
                    "classic_vario_data",
                    "rel_speed",
                    10,
                    10,
                ),
                (
                    "sensor.mock_classicvario_error_code",
                    "classic_vario_data",
                    "errorCode",
                    int(FilterErrorCode.ROTOR_STUCK),
                    "rotor_stuck",
                ),
                (
                    "sensor.mock_classicvario_remaining_hours_until_service",
                    "classic_vario_data",
                    "serviceHour",
                    100,
                    str(round(100 / 24, 2)),
                ),
            ],
        ),
    ],
)
async def test_state_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    entity_list: list[tuple[str, str, str, float, float]],
    request: pytest.FixtureRequest,
) -> None:
    """Test the sensor state update."""
    device: MagicMock = request.getfixturevalue(device_name)
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        device.mac_address, device.device_type
    )

    await hass.async_block_till_done()

    for item in entity_list:
        getattr(device, item[1])[item[2]] = item[3]
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()
        assert get_sensor_display_state(hass, entity_registry, item[0]) == str(item[4])
