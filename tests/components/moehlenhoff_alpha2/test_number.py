"""Tests for the Moehlenhoff Alpha2 numbers."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from moehlenhoff_alpha2 import Alpha2Base
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import number
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration, mock_update_data


async def setup_number_platform(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the number platform."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.PLATFORMS",
        [Platform.NUMBER],
    ):
        return await init_integration(hass)


async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test numbers."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.PLATFORMS",
        [Platform.NUMBER],
    ):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "attribute", "value"),
    [
        pytest.param("number.buro_temperature_offset", "OFFSET", 1.5, id="offset"),
        pytest.param(
            "number.buro_heating_temperature_day", "T_HEAT_DAY", 22.2, id="heating-day"
        ),
        pytest.param(
            "number.buro_heating_temperature_night",
            "T_HEAT_NIGHT",
            20.2,
            id="heating-night",
        ),
        pytest.param(
            "number.buro_cooling_temperature_day", "T_COOL_DAY", 24.2, id="cooling-day"
        ),
        pytest.param(
            "number.buro_cooling_temperature_night",
            "T_COOL_NIGHT",
            25.2,
            id="cooling-night",
        ),
        pytest.param(
            "number.buro_minimum_target_temperature",
            "T_TARGET_MIN",
            6.0,
            id="minimum-target",
        ),
        pytest.param(
            "number.buro_maximum_target_temperature",
            "T_TARGET_MAX",
            31.0,
            id="maximum-target",
        ),
    ],
)
async def test_set_number(
    hass: HomeAssistant, entity_id: str, attribute: str, value: float
) -> None:
    """Test setting room values."""
    await setup_number_platform(hass)

    with patch(
        "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area"
    ) as mock_update_heat_area:
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    mock_update_heat_area.assert_awaited_once_with("Alpha2Test:1", {attribute: value})
    assert (state := hass.states.get(entity_id))
    assert state.state == str(value)


@pytest.mark.parametrize(
    ("entity_id", "value", "state"),
    [
        pytest.param(
            "number.buro_minimum_target_temperature", 31.0, "5.0", id="minimum"
        ),
        pytest.param(
            "number.buro_maximum_target_temperature", 4.0, "30.0", id="maximum"
        ),
    ],
)
async def test_reject_invalid_target_temperature_limits(
    hass: HomeAssistant, entity_id: str, value: float, state: str
) -> None:
    """Test rejecting target limits that conflict with each other."""
    await setup_number_platform(hass)

    with (
        patch(
            "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area"
        ) as mock_update_heat_area,
        pytest.raises(
            HomeAssistantError,
            match="The minimum target temperature must not exceed the maximum",
        ),
    ):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    mock_update_heat_area.assert_not_awaited()
    assert (number_state := hass.states.get(entity_id))
    assert number_state.state == state


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(aiohttp.ClientError, id="client-error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_handle_communication_errors(
    hass: HomeAssistant, error: type[Exception]
) -> None:
    """Test handling communication errors when setting room values."""
    await setup_number_platform(hass)

    with (
        patch(
            "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area",
            side_effect=error,
        ) as mock_update_heat_area,
        pytest.raises(
            HomeAssistantError,
            match="Failed to set heat area settings, communication error with alpha2 base",
        ),
    ):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.buro_temperature_offset",
                ATTR_VALUE: 1.5,
            },
            blocking=True,
        )

    mock_update_heat_area.assert_awaited_once()
    assert (state := hass.states.get("number.buro_temperature_offset"))
    assert state.state == "0.0"


async def test_update_current_snapshot_after_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test writes update the current coordinator snapshot after a refresh."""
    entry = await setup_number_platform(hass)
    write_started = asyncio.Event()
    release_write = asyncio.Event()
    refresh_finished = asyncio.Event()

    async def update_data_and_signal_refresh(base: Alpha2Base) -> None:
        await mock_update_data(base, hass)
        refresh_finished.set()

    async def update_heat_area(
        heat_area_id: str, attributes: dict[str, float | int]
    ) -> None:
        write_started.set()
        await release_write.wait()

    with (
        patch(
            "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_data",
            new=update_data_and_signal_refresh,
        ),
        patch(
            "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area",
            side_effect=update_heat_area,
        ),
    ):
        service_task = hass.async_create_task(
            hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: "number.buro_temperature_offset",
                    ATTR_VALUE: 1.5,
                },
                blocking=True,
            )
        )
        await write_started.wait()
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await refresh_finished.wait()
        release_write.set()
        await service_task

    assert entry.runtime_data.data["heat_areas"]["Alpha2Test:1"]["OFFSET"] == 1.5
    assert (state := hass.states.get("number.buro_temperature_offset"))
    assert state.state == "1.5"


async def test_concurrent_target_temperature_limits(
    hass: HomeAssistant,
) -> None:
    """Test concurrent writes cannot produce invalid target limits."""
    entry = await setup_number_platform(hass)

    async def update_heat_area(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(0)

    with patch(
        "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area",
        side_effect=update_heat_area,
    ) as mock_update_heat_area:
        results = await asyncio.gather(
            hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: "number.buro_minimum_target_temperature",
                    ATTR_VALUE: 25.0,
                },
                blocking=True,
            ),
            hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: "number.buro_maximum_target_temperature",
                    ATTR_VALUE: 20.0,
                },
                blocking=True,
            ),
            return_exceptions=True,
        )

    assert sum(isinstance(result, HomeAssistantError) for result in results) == 1
    mock_update_heat_area.assert_awaited_once()
    heat_area = entry.runtime_data.data["heat_areas"]["Alpha2Test:1"]
    assert heat_area["T_TARGET_MIN"] <= heat_area["T_TARGET_MAX"]
