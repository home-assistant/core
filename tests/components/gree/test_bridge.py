"""Tests for gree component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from greeclimate.air_conditioner import AirConditionerDevice
from greeclimate.cipher import CipherBase, CipherV1
from greeclimate.device import DeviceInfo
from greeclimate.network import DeviceProtocol2, Response
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_MEDIUM,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.gree.const import UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_setup_gree, build_device_mock

ENTITY_ID_1 = f"{CLIMATE_DOMAIN}.fake_device_1"
ENTITY_ID_2 = f"{CLIMATE_DOMAIN}.fake_device_2"


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def test_discovery_after_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, discovery, device, mock_now
) -> None:
    """Test gree devices don't change after multiple discoveries."""
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )

    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    entry = await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 1
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in entry.runtime_data.coordinators]
    assert device_infos[0].ip == "1.1.1.1"
    assert device_infos[1].ip == "2.2.2.2"

    # rediscover the same devices with new ip addresses should update
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.2", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.1", mac="bbccdd223344"
    )
    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    next_update = mock_now + timedelta(minutes=6)
    freezer.move_to(next_update)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in entry.runtime_data.coordinators]
    assert device_infos[0].ip == "1.1.1.2"
    assert device_infos[1].ip == "2.2.2.1"


async def test_coordinator_updates(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test gree devices update their state."""
    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 1

    async def fake_update_state() -> None:
        """Fake update state."""
        device().power = True
        device().raw_properties["Pow"] = 1
        device().callbacks[Response.DATA]({"Pow": 1})

    device().update_state.side_effect = fake_update_state

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == HVACMode.AUTO


@pytest.mark.parametrize(
    ("mid", "fan_mode", "swing_mode", "switch_state"),
    [
        pytest.param("10001", FAN_MEDIUM, "full_swing", STATE_ON, id="known"),
        pytest.param("10014", FAN_MEDIUM, "full_swing", STATE_ON, id="10014"),
        pytest.param(None, None, None, STATE_UNKNOWN, id="missing"),
        pytest.param("unrecognized", None, None, STATE_UNKNOWN, id="unknown"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_real_device_controls_after_dependency_upgrade(
    hass: HomeAssistant,
    discovery: MagicMock,
    device: MagicMock,
    mid: str | None,
    fan_mode: str | None,
    swing_mode: str | None,
    switch_state: str,
) -> None:
    """Use model-specific AC polling and real command encoding."""
    info = DeviceInfo("192.0.2.1", 7000, "aabbcc112233", "fake-device-1", mid=mid)
    discovery.return_value.mock_devices = [AirConditionerDevice(info)]
    device.side_effect = AirConditionerDevice
    reported = {
        "Pow": 1,
        "Mod": 1,
        "SetTem": 25,
        "TemUn": 0,
        "TemRec": 0,
        "TemSen": 25,
        "WdSpd": 3,
        "Lig": 1,
        "Blo": 1,
        "Air": 0,
        "Health": 0,
        "Quiet": 0,
        "Tur": 0,
        "StHt": 0,
        "SvSt": 0,
        "SwhSlp": 0,
        "SlpMod": 0,
        "SwingLfRig": 1,
        "SwUpDn": 1,
    }
    commands: list[dict[str, int]] = []

    async def fake_bind(real_device: AirConditionerDevice) -> None:
        real_device.device_cipher = CipherV1()
        real_device.ready.set()

    async def fake_send(
        real_device: AirConditionerDevice,
        obj: dict,
        addr: tuple[str, int] | None = None,
        cipher: CipherBase | None = None,
    ) -> None:
        pack = obj["pack"]
        if pack["t"] == "status":
            columns = [column for column in pack["cols"] if column != "hid"]
            reply = {
                "t": Response.DATA.value,
                "cols": columns,
                "dat": [reported.get(column, 0) for column in columns],
            }
        else:
            assert pack["t"] == "cmd"
            command = dict(zip(pack["opt"], pack["p"], strict=True))
            commands.append(command)
            reported.update(command)
            reply = {
                "t": Response.RESULT.value,
                "opt": pack["opt"],
                "val": pack["p"],
            }
        DeviceProtocol2.packet_received(
            real_device, {"pack": reply}, (info.ip, info.port)
        )

    panel_light = "switch.fake_device_1_panel_light"
    xfan = "switch.fake_device_1_xtra_fan"
    with (
        patch.object(AirConditionerDevice, "bind", fake_bind),
        patch.object(AirConditionerDevice, "send", fake_send),
    ):
        entry = await async_setup_gree(hass)
        try:
            state = hass.states.get(ENTITY_ID_1)
            assert state is not None
            assert state.state == HVACMode.COOL
            assert state.attributes[ATTR_TEMPERATURE] == 25
            assert state.attributes[ATTR_FAN_MODE] == fan_mode
            assert state.attributes[ATTR_SWING_MODE] == swing_mode
            assert hass.states.get(panel_light).state == switch_state
            assert hass.states.get(xfan).state == switch_state

            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: ENTITY_ID_1, ATTR_TEMPERATURE: 24},
                blocking=True,
            )
            assert commands[-1]["SetTem"] == 24
            assert commands[-1]["TemUn"] == 0
            assert commands[-1]["TemRec"] == 0
            assert hass.states.get(ENTITY_ID_1).attributes[ATTR_TEMPERATURE] == 24

            await hass.services.async_call(
                SWITCH_DOMAIN,
                SwitchService.TURN_OFF,
                {TargetKey.ENTITY_ID: panel_light},
                blocking=True,
            )
            assert commands[-1]["Lig"] == 0
            assert hass.states.get(panel_light).state == STATE_OFF

            await hass.services.async_call(
                SWITCH_DOMAIN,
                SwitchService.TURN_OFF,
                {TargetKey.ENTITY_ID: xfan},
                blocking=True,
            )
            assert commands[-1]["Blo"] == 0
            assert hass.states.get(xfan).state == STATE_OFF
        finally:
            for coordinator in entry.runtime_data.coordinators:
                coordinator.device.close()
            discovery.return_value.mock_devices[0].close()
