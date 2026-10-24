"""Test Roborock washing machine state updates."""

from collections.abc import AsyncGenerator
from datetime import timedelta
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from Crypto.Util.Padding import pad
from freezegun.api import FrozenDateTimeFactory
import pytest
from roborock.data import ZeoState
from roborock.devices.traits.a01 import A01Api, ZeoApi
from roborock.devices.transport.mqtt_channel import MqttChannel
from roborock.roborock_message import (
    RoborockMessage,
    RoborockMessageProtocol,
    RoborockZeoProtocol,
)

from homeassistant.components.roborock.coordinator import (
    RoborockWashingMachineUpdateCoordinator,
)
from homeassistant.components.switch import SERVICE_TURN_OFF
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from .conftest import FakeDevice

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Set up washing machine sensors and switches."""
    return [Platform.SENSOR, Platform.SWITCH]


@pytest.fixture
def zeo_mqtt_channel() -> MagicMock:
    """Mock the washing machine MQTT transport."""
    channel = MagicMock(spec=MqttChannel)
    channel.subscribe = AsyncMock(return_value=Mock())
    return channel


@pytest.fixture
async def zeo_api(
    fake_devices: list[FakeDevice], zeo_mqtt_channel: MagicMock
) -> AsyncGenerator[ZeoApi]:
    """Use the real API to decode and merge washing machine MQTT updates."""
    device = next((device for device in fake_devices if device.zeo is not None), None)
    assert device is not None
    api = ZeoApi(
        zeo_mqtt_channel,
        model=device.product.model,
        initial_status={
            RoborockZeoProtocol.STATE: ZeoState.drying.value,
            RoborockZeoProtocol.WASHING_LEFT: 30,
            RoborockZeoProtocol.SOUND_SET: 1,
        },
    )
    # Device setup owns the subscription and initial state synchronization.
    await A01Api.start(api)
    device.zeo = api
    yield api
    api.close()


@pytest.fixture
async def setup_washing_machine(
    hass: HomeAssistant,
    zeo_api: ZeoApi,
    mock_roborock_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with the subscribed washing machine API."""
    assert await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_roborock_entry


def push_update(channel: MagicMock, datapoints: dict[RoborockZeoProtocol, int]) -> None:
    """Deliver a decoded MQTT message through the library's subscription."""
    channel.subscribe.call_args.args[0](
        RoborockMessage(
            protocol=RoborockMessageProtocol.RPC_RESPONSE,
            version=b"A01",
            payload=pad(json.dumps({"dps": datapoints}).encode(), 16),
        )
    )


@pytest.mark.parametrize(
    ("datapoints", "expected_state", "expected_time", "expected_sound"),
    [
        pytest.param(
            {RoborockZeoProtocol.STATE: ZeoState.spinning.value},
            "spinning",
            "30",
            "on",
            id="state",
        ),
        pytest.param(
            {RoborockZeoProtocol.WASHING_LEFT: 29},
            "drying",
            "29",
            "on",
            id="remaining_time",
        ),
        pytest.param(
            {RoborockZeoProtocol.SOUND_SET: 0},
            "drying",
            "30",
            "off",
            id="sound_setting",
        ),
    ],
)
@pytest.mark.usefixtures("setup_washing_machine")
async def test_partial_mqtt_update(
    hass: HomeAssistant,
    zeo_api: ZeoApi,
    zeo_mqtt_channel: MagicMock,
    datapoints: dict[RoborockZeoProtocol, int],
    expected_state: str,
    expected_time: str,
    expected_sound: str,
) -> None:
    """Test partial MQTT updates immediately change entities and retain other state."""
    previous_values = zeo_api.values
    with patch.object(zeo_api, "query_values") as query_values:
        push_update(zeo_mqtt_channel, datapoints)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.zeo_one_state").state == expected_state
        assert hass.states.get("sensor.zeo_one_washing_left").state == expected_time
        assert hass.states.get("switch.zeo_one_sound_setting").state == expected_sound
        assert hass.states.get("sensor.zeo_one_error").state == STATE_UNKNOWN
        assert previous_values[RoborockZeoProtocol.WASHING_LEFT] == 30
        query_values.assert_not_awaited()


async def test_washing_machine_does_not_poll(
    hass: HomeAssistant,
    zeo_api: ZeoApi,
    mock_roborock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup and scheduled updates use the synchronized state without polling."""
    with patch.object(
        zeo_api, "query_values", return_value=zeo_api.values
    ) as query_values:
        assert await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.zeo_one_washing_left").state == "30"
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        query_values.assert_not_awaited()


@pytest.mark.usefixtures("setup_washing_machine")
async def test_refresh_after_command_preserves_mqtt_state(
    hass: HomeAssistant,
    zeo_api: ZeoApi,
    zeo_mqtt_channel: MagicMock,
) -> None:
    """Test a command's refresh keeps the latest MQTT state without querying."""

    async def set_value(protocol: RoborockZeoProtocol, value: int) -> None:
        """Report the changed setting and remaining time before completing a command."""
        push_update(
            zeo_mqtt_channel,
            {protocol: value, RoborockZeoProtocol.WASHING_LEFT: 0},
        )

    with (
        patch.object(zeo_api, "query_values") as query_values,
        patch.object(zeo_api, "set_value", side_effect=set_value) as set_value_mock,
    ):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.zeo_one_sound_setting"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hass.states.get("switch.zeo_one_sound_setting").state == "off"
        assert hass.states.get("sensor.zeo_one_washing_left").state == "0"
        assert hass.states.get("sensor.zeo_one_state").state == "drying"
        set_value_mock.assert_awaited_once_with(RoborockZeoProtocol.SOUND_SET, 0)
        query_values.assert_not_awaited()


async def test_washing_machine_unsubscribed_on_unload(
    hass: HomeAssistant,
    setup_washing_machine: MockConfigEntry,
    zeo_mqtt_channel: MagicMock,
) -> None:
    """Test unloading removes the update listener and shutdown can be repeated."""
    coordinator = next(
        coordinator
        for coordinator in setup_washing_machine.runtime_data.values()
        if isinstance(coordinator, RoborockWashingMachineUpdateCoordinator)
    )
    previous_values = coordinator.data

    assert await hass.config_entries.async_unload(setup_washing_machine.entry_id)
    await hass.async_block_till_done()
    await coordinator.async_shutdown()

    push_update(zeo_mqtt_channel, {RoborockZeoProtocol.WASHING_LEFT: 10})
    await hass.async_block_till_done()

    assert coordinator.data == previous_values
