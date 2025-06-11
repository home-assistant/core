"""Tests for the time module."""

from datetime import time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
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
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.TIME]),
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
                    "time.mock_heater_day_start_time",
                    time(9, 0, tzinfo=timezone(timedelta(hours=1))),
                    "dayStartT",
                    9 * 60,
                ),
                (
                    "time.mock_heater_night_start_time",
                    time(19, 0, tzinfo=timezone(timedelta(hours=1))),
                    "nightStartT",
                    19 * 60,
                ),
            ],
        ),
        (
            "classic_vario_mock",
            [
                (
                    "time.mock_classicvario_day_start_time",
                    time(9, 0, tzinfo=timezone(timedelta(hours=1))),
                    "startTime_day",
                    9 * 60,
                ),
                (
                    "time.mock_classicvario_night_start_time",
                    time(19, 0, tzinfo=timezone(timedelta(hours=1))),
                    "startTime_night",
                    19 * 60,
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
    entity_list: list[tuple[str, time, str, tuple[time]]],
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
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: item[0], ATTR_TIME: item[1]},
            blocking=True,
        )
        calls = [call for call in device.hub.mock_calls if call[0] == "send_packet"]
        assert calls[-1][1][0][item[2]] == item[3]


@pytest.mark.usefixtures("classic_vario_mock", "heater_mock")
@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "heater_mock",
            [
                (
                    "time.mock_heater_day_start_time",
                    "heater_data",
                    "dayStartT",
                    540,
                    time(9, 0, tzinfo=timezone(timedelta(hours=1))).isoformat(),
                ),
                (
                    "time.mock_heater_night_start_time",
                    "heater_data",
                    "nightStartT",
                    1140,
                    time(19, 0, tzinfo=timezone(timedelta(hours=1))).isoformat(),
                ),
            ],
        ),
        (
            "classic_vario_mock",
            [
                (
                    "time.mock_classicvario_day_start_time",
                    "classic_vario_data",
                    "startTime_day",
                    540,
                    time(9, 0, tzinfo=timezone(timedelta(hours=1))).isoformat(),
                ),
                (
                    "time.mock_classicvario_night_start_time",
                    "classic_vario_data",
                    "startTime_night",
                    1320,
                    time(22, 0, tzinfo=timezone(timedelta(hours=1))).isoformat(),
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
    entity_list: list[tuple[str, str, str, float, str]],
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
        getattr(device, item[1])[item[2]] = item[3]
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()
        assert (state := hass.states.get(item[0]))
        assert state.state == item[4]
