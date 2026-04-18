"""Tests for the binary sensor module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, get_sensor_display_state, snapshot_platform


async def test_setup(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.eheimdigital.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    for device in eheimdigital_hub_mock.return_value.devices:
        await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
            device, eheimdigital_hub_mock.return_value.devices[device].device_type
        )
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "reeflex_mock",
            [
                (
                    "binary_sensor.mock_reeflex_light",
                    "reeflex_data",
                    "isLighting",
                    True,
                    "on",
                ),
                (
                    "binary_sensor.mock_reeflex_light",
                    "reeflex_data",
                    "isLighting",
                    False,
                    "off",
                ),
                (
                    "binary_sensor.mock_reeflex_uvc_lamp_connected",
                    "reeflex_data",
                    "isUVCConnected",
                    True,
                    "on",
                ),
                (
                    "binary_sensor.mock_reeflex_uvc_lamp_connected",
                    "reeflex_data",
                    "isUVCConnected",
                    False,
                    "off",
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
    entity_list: list[tuple[str, str, str, bool | int, str]],
    request: pytest.FixtureRequest,
) -> None:
    """Test the binary sensor state update."""
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
