"""Tests for the number module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("classic_vario_mock", "heater_mock")
async def test_setup(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number platform setup."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.NUMBER]),
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
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("classic_vario_mock", "heater_mock")
@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "heater_mock",
            [
                (
                    "number.mock_heater_temperature_offset",
                    0.4,
                    "set_temperature_offset",
                    (0.4,),
                ),
                (
                    "number.mock_heater_night_temperature_offset",
                    0.4,
                    "set_night_temperature_offset",
                    (0.4,),
                ),
            ],
        ),
        (
            "classic_vario_mock",
            [
                (
                    "number.mock_classicvario_manual_speed",
                    72.1,
                    "set_manual_speed",
                    (int(72.1),),
                ),
                (
                    "number.mock_classicvario_day_speed",
                    72.1,
                    "set_day_speed",
                    (int(72.1),),
                ),
                (
                    "number.mock_classicvario_night_speed",
                    72.1,
                    "set_night_speed",
                    (int(72.1),),
                ),
            ],
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    entity_list: list[tuple[str, float, str, tuple[float]]],
    request: pytest.FixtureRequest,
) -> None:
    """Test setting a value."""
    device: MagicMock = request.getfixturevalue(device_name)
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        device.mac_address, device.device_type
    )

    await hass.async_block_till_done()

    for item in entity_list:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: item[0], ATTR_VALUE: item[1]},
            blocking=True,
        )
        calls = [call for call in device.mock_calls if call[0] == item[2]]
        assert len(calls) == 1 and calls[0][1] == item[3]


@pytest.mark.usefixtures("classic_vario_mock", "heater_mock")
@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "heater_mock",
            [
                (
                    "number.mock_heater_temperature_offset",
                    "temperature_offset",
                    -1.1,
                ),
                (
                    "number.mock_heater_night_temperature_offset",
                    "night_temperature_offset",
                    2.3,
                ),
            ],
        ),
        (
            "classic_vario_mock",
            [
                (
                    "number.mock_classicvario_manual_speed",
                    "manual_speed",
                    34,
                ),
                (
                    "number.mock_classicvario_day_speed",
                    "day_speed",
                    79,
                ),
                (
                    "number.mock_classicvario_night_speed",
                    "night_speed",
                    12,
                ),
            ],
        ),
    ],
)
async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    entity_list: list[tuple[str, str, float]],
    request: pytest.FixtureRequest,
) -> None:
    """Test state updates."""
    device: MagicMock = request.getfixturevalue(device_name)
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        device.mac_address, device.device_type
    )

    await hass.async_block_till_done()

    for item in entity_list:
        setattr(device, item[1], item[2])
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()
        assert (state := hass.states.get(item[0]))
        assert state.state == str(item[2])
