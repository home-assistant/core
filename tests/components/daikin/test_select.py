"""Tests for Daikin select entities."""

import asyncio
from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydaikin.exceptions import DaikinException
import pytest

from homeassistant.components.daikin.const import DOMAIN
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import EntityCategory, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, async_setup_daikin


def _demand_control_select_entity_id(
    entity_registry: er.EntityRegistry, mac: str
) -> str | None:
    """Return the demand control select entity ID."""
    return entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{mac}-demand_control"
    )


@pytest.mark.parametrize(
    ("demand_control", "expected_option"),
    [
        pytest.param({"en_demand": "1", "mode": "0"}, "manual", id="manual"),
        pytest.param({"en_demand": "1", "mode": "2"}, "auto", id="auto"),
        pytest.param({"en_demand": "0", "mode": "0"}, "off", id="disabled-manual"),
        pytest.param({"en_demand": "0", "mode": "2"}, "off", id="disabled-auto"),
    ],
)
async def test_select_demand_control_mode_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    demand_control: dict[str, str],
    expected_option: str,
) -> None:
    """Test demand control select state and category."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = demand_control

    await async_setup_daikin(hass, zone_device)

    entity_id = _demand_control_select_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None
    assert (state := hass.states.get(entity_id))
    assert state.state == expected_option
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.entity_category is EntityCategory.CONFIG


async def test_select_demand_control_mode_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Do not create a demand control select when unsupported."""
    await async_setup_daikin(hass, zone_device)

    assert _demand_control_select_entity_id(entity_registry, zone_device.mac) is None


@pytest.mark.parametrize(
    ("option", "initial_mode", "enabled", "mode"),
    [
        pytest.param("off", "0", "off", 0, id="off-preserves-manual"),
        pytest.param("off", "2", "off", 2, id="off-preserves-auto"),
        pytest.param("auto", "0", "on", 2, id="auto"),
        pytest.param("manual", "2", "on", 0, id="manual"),
    ],
)
async def test_select_demand_control_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    option: str,
    initial_mode: str,
    enabled: str,
    mode: int,
) -> None:
    """Test setting the demand control mode."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = {
        "en_demand": "1",
        "mode": initial_mode,
        "max_pow": "50",
    }
    zone_device.set_demand_control = AsyncMock()
    await async_setup_daikin(hass, zone_device)
    entity_id = _demand_control_select_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: entity_id,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_awaited_once_with(
        en_demand=enabled, max_pow=50, mode=mode
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(
            DaikinException("device rejected command"), "device rejected command"
        ),
        pytest.param(ClientError("connection lost"), "connection lost"),
        pytest.param(TimeoutError(), "TimeoutError"),
    ],
)
async def test_select_demand_control_communication_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    error: Exception,
    message: str,
) -> None:
    """Translate communication errors from demand-control select writes."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = {
        "en_demand": "1",
        "mode": "0",
        "max_pow": "50",
    }
    zone_device.set_demand_control = AsyncMock(side_effect=error)
    await async_setup_daikin(hass, zone_device)
    entity_id = _demand_control_select_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                TargetKey.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: "auto",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "error_communicating"
    assert err.value.translation_placeholders == {"error": message}


async def test_concurrent_demand_control_updates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Serialize concurrent select and number service calls."""
    demand_control = {"en_demand": "1", "mode": "0", "max_pow": "50"}
    zone_device.support_demand_control = True
    zone_device.get_demand_control.side_effect = demand_control.copy
    first_write_started = asyncio.Event()
    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()
    writes: list[tuple[str, int, int]] = []

    async def set_demand_control(*, en_demand: str, max_pow: int, mode: int) -> None:
        writes.append((en_demand, max_pow, mode))
        demand_control.update(
            en_demand="1" if en_demand == "on" else "0",
            max_pow=str(max_pow),
            mode=str(mode),
        )
        first_write_started.set()

    async def update_status() -> None:
        refresh_started.set()
        await release_refresh.wait()

    zone_device.set_demand_control = AsyncMock(side_effect=set_demand_control)
    await async_setup_daikin(hass, zone_device)
    zone_device.update_status.side_effect = update_status
    select_entity_id = _demand_control_select_entity_id(
        entity_registry, zone_device.mac
    )
    number_entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN,
        DOMAIN,
        f"{zone_device.mac}-demand_control_max_power",
    )
    assert select_entity_id is not None
    assert number_entity_id is not None

    select_task = asyncio.create_task(
        hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                TargetKey.ENTITY_ID: select_entity_id,
                SelectServiceArgument.OPTION: "auto",
            },
            blocking=True,
        )
    )
    tasks = [select_task]
    try:
        await first_write_started.wait()
        await refresh_started.wait()
        number_started = asyncio.Event()

        async def set_power() -> None:
            number_started.set()
            await hass.services.async_call(
                NUMBER_DOMAIN,
                NumberService.SET_VALUE,
                {
                    TargetKey.ENTITY_ID: number_entity_id,
                    NumberServiceArgument.VALUE: 75.0,
                },
                blocking=True,
            )

        number_task = asyncio.create_task(set_power())
        tasks.append(number_task)
        await number_started.wait()
        await asyncio.sleep(0)

        assert writes == [("on", 50, 2)]

        release_refresh.set()
        await asyncio.gather(select_task, number_task)
    finally:
        release_refresh.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert writes == [("on", 50, 2), ("on", 75, 2)]
    assert demand_control == {"en_demand": "1", "mode": "2", "max_pow": "75"}
