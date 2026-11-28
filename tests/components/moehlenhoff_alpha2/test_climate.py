"""Tests for the Moehlenhoff Alpha2 climate."""

import asyncio
from unittest.mock import call, patch

from pytest_homeassistant.common import snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import climate, number
from homeassistant.components.moehlenhoff_alpha2.const import PRESET_NIGHT
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.PLATFORMS",
        [Platform.CLIMATE],
    ):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_preset_change_waits_for_number_write(hass: HomeAssistant) -> None:
    """Test a preset change waits for a pending active temperature write."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.PLATFORMS",
        [Platform.CLIMATE, Platform.NUMBER],
    ):
        entry = await init_integration(hass)

    temperature_write_started = asyncio.Event()
    release_temperature_write = asyncio.Event()

    async def update_heat_area(
        _heat_area_id: str, attributes: dict[str, float | int]
    ) -> None:
        if "T_HEAT_DAY" in attributes:
            temperature_write_started.set()
            await release_temperature_write.wait()

    with patch(
        "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_heat_area",
        side_effect=update_heat_area,
    ) as mock_update_heat_area:
        temperature_task = hass.async_create_task(
            hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: "number.buro_heating_temperature_day",
                    ATTR_VALUE: 22.2,
                },
                blocking=True,
            )
        )
        await temperature_write_started.wait()

        preset_change_started = asyncio.Event()
        set_heat_area_mode = entry.runtime_data.async_set_heat_area_mode

        async def track_preset_change(heat_area_id: str, heat_area_mode: int) -> None:
            preset_change_started.set()
            await set_heat_area_mode(heat_area_id, heat_area_mode)

        with patch.object(
            entry.runtime_data,
            "async_set_heat_area_mode",
            new=track_preset_change,
        ):
            preset_task = hass.async_create_task(
                hass.services.async_call(
                    climate.DOMAIN,
                    climate.SERVICE_SET_PRESET_MODE,
                    {
                        ATTR_ENTITY_ID: hass.states.async_entity_ids(climate.DOMAIN)[0],
                        climate.ATTR_PRESET_MODE: PRESET_NIGHT,
                    },
                    blocking=True,
                )
            )
            await preset_change_started.wait()

            preset_waited_for_temperature_write = (
                mock_update_heat_area.await_args_list
                == [call("Alpha2Test:1", {"T_HEAT_DAY": 22.2, "T_TARGET": 22.2})]
            )

            release_temperature_write.set()
            await asyncio.gather(temperature_task, preset_task)

    await hass.async_block_till_done()

    assert preset_waited_for_temperature_write
    assert mock_update_heat_area.await_args_list == [
        call("Alpha2Test:1", {"T_HEAT_DAY": 22.2, "T_TARGET": 22.2}),
        call("Alpha2Test:1", {"HEATAREA_MODE": 2}),
    ]
    assert (state := hass.states.get(hass.states.async_entity_ids(climate.DOMAIN)[0]))
    assert state.attributes[ATTR_TEMPERATURE] == 19.0
