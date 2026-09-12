"""Tests for the BLUETTI data models."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pybluetti import ApplicationRuntimeException, UnifyResponse
import pytest

from homeassistant.components.bluetti_cloud.models import (
    BluettiData,
    BluettiDevice,
    BluettiState,
)


def test_state_is_switch_without_modes() -> None:
    """State is switch without modes."""
    state = BluettiState(
        fn_code="SetCtrlAc", fn_name="AC", fn_value="0", fn_type="SWITCH"
    )
    assert state.is_switch() is True
    assert state.get_name_for_value() == "Off"


def test_state_set_value_switch() -> None:
    """State set value switch."""
    state = BluettiState(
        fn_code="SetCtrlAc", fn_name="AC", fn_value="0", fn_type="SWITCH"
    )
    state.set_value("1")
    assert state.fn_value == "1"
    assert state.get_name_for_value() == "On"


def test_state_get_name_for_value_falls_back_to_raw_value() -> None:
    """State get name for value falls back to raw value."""
    modes = [{"code": "0", "name": "Standard"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode",
        fn_name="Mode",
        fn_value="unmapped-value",
        fn_type="SELECT",
        support_mode_values=modes,
    )
    assert state.get_name_for_value() == "unmapped-value"


def test_state_repr() -> None:
    """State repr."""
    state = BluettiState(
        fn_code="SOC", fn_name="Battery", fn_value="80", fn_type="SENSOR"
    )
    assert repr(state) == "<BluettiState SOC=80>"


def test_device_repr() -> None:
    """Device repr."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    assert repr(device) == "<BluettiDevice id=SN1 name=Test>"


def test_state_select_valid_value() -> None:
    """State select valid value."""
    modes = [{"code": "0", "name": "Standard"}, {"code": "1", "name": "Silent"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode",
        fn_name="Mode",
        fn_value="0",
        fn_type="SELECT",
        support_mode_values=modes,
    )
    state.set_value("1")
    assert state.fn_value == "1"
    assert state.get_name_for_value() == "Silent"


def test_state_select_invalid_value_raises() -> None:
    """State select invalid value raises."""
    modes = [{"code": "0", "name": "Standard"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode",
        fn_name="Mode",
        fn_value="0",
        fn_type="SELECT",
        support_mode_values=modes,
    )
    with pytest.raises(ValueError):
        state.set_value("99")


def test_device_get_state_returns_none_for_missing_code() -> None:
    """Device get state returns none for missing code."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    assert device.get_state("does-not-exist") is None


def test_state_falls_back_to_fn_code_when_fn_name_is_blank() -> None:
    """Some fn_codes come back from the API without a localized fnName.

    With has_entity_name = True, an empty entity name makes Home
    Assistant's frontend display the raw entity_id (which contains the
    device serial number) instead of a real label, so BluettiDevice must
    fall back to a non-empty name when building its states.
    """
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[{"fnCode": "SetCtrlWorkMode", "fnValue": "2", "fnType": "SELECT"}],
    )
    state = device.get_state("SetCtrlWorkMode")
    assert state.fn_name == "SetCtrlWorkMode"


def test_device_battery_level_reads_soc_state() -> None:
    """Device battery level reads soc state."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {"fnCode": "SOC", "fnName": "Battery", "fnValue": "42", "fnType": "SENSOR"}
        ],
    )
    assert device.battery_level == 42


def test_device_battery_level_defaults_to_zero_without_soc() -> None:
    """Device battery level defaults to zero without soc."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    assert device.battery_level == 0


def test_device_online_property() -> None:
    """Device online property."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    assert device.online is True
    device.on_line = "0"
    assert device.online is False


def test_bluetti_data_get_device_by_sn() -> None:
    """Bluetti data get device by sn."""
    fake_hass = SimpleNamespace(loop=None)
    product = SimpleNamespace(
        sn="SN1", online="1", name="Test", model="AC200L", stateList=[]
    )
    data = BluettiData(fake_hass, [product])
    assert data.get_device_by_sn("SN1") is not None
    assert data.get_device_by_sn("unknown") is None


async def test_async_refresh_from_api_updates_states() -> None:
    """Async refresh from api updates states."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="0",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {"fnCode": "SOC", "fnName": "Battery", "fnValue": "10", "fnType": "SENSOR"}
        ],
    )
    status_data = SimpleNamespace(
        sn="SN1",
        online="1",
        isBindByCurUser="1",
        stateList=[{"fnCode": "SOC", "fnValue": "77"}],
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(
        data=[status_data], is_ok=lambda: True
    )

    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("SOC").fn_value == "77"


async def test_async_refresh_from_api_raises_on_empty_data() -> None:
    """Async refresh from api raises on empty data."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(
        data=[], is_ok=lambda: True
    )

    with pytest.raises(RuntimeError):
        await device.async_refresh_from_api()


async def test_async_refresh_from_api_raises_on_failed_envelope() -> None:
    """A failed application-level response must not look like empty data.

    Regression test: get_device_status() doesn't raise for a nonzero
    msgCode (e.g. an expired token, code 805) - it returns a UnifyResponse
    with data=None. Previously this fell through to the generic "empty
    status response" RuntimeError -> UpdateFailed instead of
    ApplicationRuntimeException -> ConfigEntryAuthFailed/reauth.
    """
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = UnifyResponse(
        msgId="1", msgCode=805, data=None
    )

    with pytest.raises(ApplicationRuntimeException) as exc_info:
        await device.async_refresh_from_api()

    assert exc_info.value.msgCode == 805


async def test_async_refresh_from_api_ignores_mismatched_sn() -> None:
    """Async refresh from api ignores mismatched sn."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="0",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {"fnCode": "SOC", "fnName": "Battery", "fnValue": "10", "fnType": "SENSOR"}
        ],
    )
    status_data = SimpleNamespace(
        sn="OTHER-SN", online="1", isBindByCurUser="1", stateList=[]
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(
        data=[status_data], is_ok=lambda: True
    )

    await device.async_refresh_from_api()

    # Nothing should have changed since the response was for a different device.
    assert device.on_line == "0"
    assert device.get_state("SOC").fn_value == "10"
