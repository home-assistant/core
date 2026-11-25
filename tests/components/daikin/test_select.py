"""Tests for Daikin select entities."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydaikin.exceptions import DaikinException
import pytest

from homeassistant.components.daikin.const import DOMAIN
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
