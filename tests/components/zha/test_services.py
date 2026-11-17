"""Tests for the ZHA services."""

from collections.abc import Callable, Coroutine
from datetime import time
import json
from unittest.mock import AsyncMock, _Call, call, patch

import pytest
from pytest_homeassistant.common import MockUser
from zigpy.device import GreenPowerDevice as ZigpyGreenPowerDevice, ZigbeeDevice
from zigpy.profiles import zha
from zigpy.typing import UNDEFINED as ZIGPY_UNDEFINED
from zigpy.zcl.clusters import general
from zigpy.zcl.clusters.hvac import Thermostat
from zigpy.zgp.types import ApplicationID, SrcID

from homeassistant.components.schedule.const import (
    CONF_DATA,
    CONF_FROM,
    CONF_TO,
    WEEKDAY_TO_CONF,
)
from homeassistant.components.zha.const import DOMAIN, ZHAService
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.components.zha.services import _schedule_helper_transitions
from homeassistant.components.zha.weekly_schedule import (
    ScheduleConversionError,
    schedule_to_transitions,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.setup import async_setup_component

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

IEEE_SWITCH_DEVICE = "01:2d:6f:00:0a:90:69:e7"
SET_ATTRIBUTE_DATA = {"endpoint_id": 1, "cluster_id": 6, "attribute": 0, "value": 1}
CLUSTER_COMMAND_DATA = {
    "endpoint_id": 1,
    "cluster_id": 6,
    "command": 0,
    "command_type": "server",
    "params": {},
}


async def test_services_registered_without_gateway(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    for service in (
        ZHAService.PERMIT,
        ZHAService.REMOVE,
        ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
        ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
        ZHAService.WARNING_DEVICE_SQUAWK,
        ZHAService.WARNING_DEVICE_WARN,
    ):
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(ZHAService.PERMIT, {}, id="permit"),
        pytest.param(ZHAService.REMOVE, {"ieee": IEEE_SWITCH_DEVICE}, id="remove"),
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "attribute": 0,
                "value": 1,
            },
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "command": 0,
                "command_type": "server",
                "params": {},
            },
            id="issue_zigbee_cluster_command",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
            {"group": 1, "cluster_id": 6, "command": 0},
            id="issue_zigbee_group_command",
        ),
        pytest.param(
            ZHAService.WARNING_DEVICE_SQUAWK,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_squawk",
        ),
        pytest.param(
            ZHAService.WARNING_DEVICE_WARN,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_warn",
        ),
    ],
)
async def test_service_without_gateway_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise a user-facing error when no gateway is loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_gateway"


@pytest.mark.parametrize(
    ("service", "data", "method", "expected_call"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            "write_zigbee_attribute",
            call(1, 6, 0, 1, cluster_type="in", manufacturer=ZIGPY_UNDEFINED),
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {**CLUSTER_COMMAND_DATA, "manufacturer": 0x1234},
            "issue_cluster_command",
            call(1, 6, 0, "server", None, {}, cluster_type="in", manufacturer=0x1234),
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    service: str,
    data: dict,
    method: str,
    expected_call: _Call,
) -> None:
    """Test the cluster actions are forwarded to the device."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    zha_device = gateway.get_or_create_device(zigpy_device)

    with patch.object(zha_device, method, AsyncMock()) as method_mock:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE, **data}, blocking=True
        )

    assert method_mock.await_args_list == [expected_call]


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            CLUSTER_COMMAND_DATA,
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service_unknown_device_raises(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    service: str,
    data: dict,
) -> None:
    """Test the cluster actions reject an unknown device."""
    await setup_zha()

    with pytest.raises(ValueError, match=f"Device with IEEE {IEEE_SWITCH_DEVICE}"):
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE, **data}, blocking=True
        )


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            CLUSTER_COMMAND_DATA,
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service_green_power_device_raises(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    service: str,
    data: dict,
) -> None:
    """Test the cluster actions reject a Green Power device."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_gpd = ZigpyGreenPowerDevice(
        gateway.application_controller,
        application_id=ApplicationID.SrcID,
        src_id=SrcID(0x12345678),
    )
    gateway.application_controller.devices[zigpy_gpd.ieee] = zigpy_gpd
    gateway.get_or_create_device(zigpy_gpd)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": str(zigpy_gpd.ieee), **data}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_zigbee_device"
    assert err.value.translation_placeholders == {"ieee": str(zigpy_gpd.ieee)}


async def test_cluster_command_optional_named_response(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Return real Zigpy schema fields as JSON without changing legacy calls."""
    await setup_zha()
    gateway = get_zha_gateway(hass)
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    zha_device = gateway.get_or_create_device(zigpy_device)
    zigpy_response = Thermostat.ClientCommandDefs.get_weekly_schedule_response.schema(
        num_transitions_for_sequence=1,
        day_of_week_for_sequence=2,
        mode_for_sequence=1,
        values=[360, 2150],
    )
    with patch.object(zha_device, "issue_cluster_command", AsyncMock()) as command:
        command.return_value = zigpy_response
        response = await hass.services.async_call(
            DOMAIN,
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {"ieee": IEEE_SWITCH_DEVICE, **CLUSTER_COMMAND_DATA},
            blocking=True,
            return_response=True,
        )
        assert response == {
            "response": {
                "num_transitions_for_sequence": 1,
                "day_of_week_for_sequence": 2,
                "mode_for_sequence": 1,
                "values": [360, 2150],
            }
        }
        json.dumps(response, allow_nan=False)
        assert command.await_args.kwargs["return_response"] is True

        command.reset_mock()
        command.return_value = object()
        await hass.services.async_call(
            DOMAIN,
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {"ieee": IEEE_SWITCH_DEVICE, **CLUSTER_COMMAND_DATA},
            blocking=True,
        )
        assert "return_response" not in command.await_args.kwargs
        with pytest.raises(HomeAssistantError, match="Unsupported Zigbee response"):
            await hass.services.async_call(
                DOMAIN,
                ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
                {"ieee": IEEE_SWITCH_DEVICE, **CLUSTER_COMMAND_DATA},
                blocking=True,
                return_response=True,
            )

        command.reset_mock()
        with (
            patch.object(zha_device, "supports_cluster_command_response", False),
            pytest.raises(ServiceValidationError) as err,
        ):
            await hass.services.async_call(
                DOMAIN,
                ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
                {"ieee": IEEE_SWITCH_DEVICE, **CLUSTER_COMMAND_DATA},
                blocking=True,
                return_response=True,
            )
        assert err.value.translation_key == "cluster_command_response_unsupported"
        command.assert_not_awaited()


async def test_raw_cluster_command_stays_admin_only(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
) -> None:
    """The optional response does not relax the existing admin-only action."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {"ieee": IEEE_SWITCH_DEVICE, **CLUSTER_COMMAND_DATA},
            context=Context(user_id=hass_read_only_user.id),
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "problem",
    [
        "missing_day",
        "empty_day",
        "gap",
        "overlap",
        "missing_midnight",
        "missing_end",
        "seconds",
        "missing_temperature",
        "boolean_temperature",
        "string_temperature",
        "non_finite_temperature",
        "fractional_centi_degree",
    ],
)
def test_schedule_helper_requires_complete_precise_heat_data(problem: str) -> None:
    """Invalid helper schedules are rejected before reaching the thermostat."""
    schedule = {
        day: [{"from": time.min, "to": time.max, "data": {"temperature": 21.5}}]
        for day in WEEKDAY_TO_CONF.values()
    }
    day = schedule["sunday"]
    if problem == "missing_day":
        del schedule["sunday"]
    elif problem == "empty_day":
        schedule["sunday"] = []
    elif problem in ("gap", "overlap"):
        day[0]["to"] = time(12)
        day.append(
            {
                "from": time(13 if problem == "gap" else 11),
                "to": time.max,
                "data": {"temperature": 20.0},
            }
        )
    elif problem == "missing_midnight":
        day[0]["from"] = time(0, 1)
    elif problem == "missing_end":
        day[0]["to"] = time(23, 59)
    elif problem == "seconds":
        day[0]["from"] = time(0, 0, 1)
    elif problem == "missing_temperature":
        day[0]["data"] = {}
    elif problem == "boolean_temperature":
        day[0]["data"] = {"temperature": True}
    elif problem == "string_temperature":
        day[0]["data"] = {"temperature": "21.5"}
    elif problem == "non_finite_temperature":
        day[0]["data"] = {"temperature": float("nan")}
    elif problem == "fractional_centi_degree":
        day[0]["data"] = {"temperature": 21.501}

    with pytest.raises(ServiceValidationError):
        _schedule_helper_transitions(schedule)


def test_schedule_link_conversion_fallbacks() -> None:
    """Link temperatures fill blocks without data and uncovered time."""
    schedule = {day: [] for day in WEEKDAY_TO_CONF.values()}
    schedule["monday"] = [
        {CONF_FROM: time(6), CONF_TO: time(8)},
        {CONF_FROM: time(8), CONF_TO: time(9), CONF_DATA: {"temperature": 21}},
        {CONF_FROM: time(17), CONF_TO: time.max, CONF_DATA: {"temperature": 17}},
    ]
    result = schedule_to_transitions(schedule, block_temperature=21, gap_temperature=17)
    assert result["monday"] == [(0, 1700), (360, 2100), (540, 1700)]
    assert result["sunday"] == [(0, 1700)]

    with pytest.raises(
        ScheduleConversionError, match=r"no temperature.*temperature: 23"
    ):
        schedule_to_transitions(schedule, gap_temperature=17)
    with pytest.raises(
        ScheduleConversionError,
        match=r"default temperature outside of time blocks.*whole day",
    ):
        schedule_to_transitions(schedule, block_temperature=21)
