"""Tests for the light module."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.types import EheimDeviceType, EheimDigitalClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eheimdigital.const import EFFECT_DAYCL_MODE
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.color import value_to_brightness

from .conftest import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    "tankconfig",
    [
        [["CLASSIC_DAYLIGHT"], []],
        [[], ["CLASSIC_DAYLIGHT"]],
        [["CLASSIC_DAYLIGHT"], ["CLASSIC_DAYLIGHT"]],
    ],
)
async def test_setup_classic_led_ctrl(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    tankconfig: list[list[str]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    classic_led_ctrl_mock: MagicMock,
) -> None:
    """Test light platform setup with different channels."""
    mock_config_entry.add_to_hass(hass)

    classic_led_ctrl_mock.tankconfig = tankconfig

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.LIGHT]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dynamic_new_devices(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_led_ctrl_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light platform setup with at first no devices and dynamically adding a device."""
    mock_config_entry.add_to_hass(hass)

    eheimdigital_hub_mock.return_value.devices = {}

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.LIGHT]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (
        len(
            entity_registry.entities.get_entries_for_config_entry_id(
                mock_config_entry.entry_id
            )
        )
        == 0
    )

    eheimdigital_hub_mock.return_value.devices = {
        "00:00:00:00:00:01": classic_led_ctrl_mock
    }

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    eheimdigital_hub_mock: MagicMock,
    classic_led_ctrl_mock: EheimDigitalClassicLEDControl,
) -> None:
    """Test turning off the light."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    classic_led_ctrl_mock.hub.send_packet.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.mock_classicledcontrol_e_channel_1"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"

    classic_led_ctrl_mock.hub.send_packet.side_effect = None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.mock_classicledcontrol_e_channel_1"},
        blocking=True,
    )

    calls = [
        call
        for call in classic_led_ctrl_mock.hub.mock_calls
        if call[0] == "send_packet"
    ]
    assert len(calls) == 3
    assert calls[1][1][0].get("title") == "MAN_MODE"
    assert calls[2][1][0]["currentValues"][1] == 0


@pytest.mark.parametrize(
    ("dim_input", "expected_dim_value"),
    [
        (3, 1),
        (255, 100),
        (128, 50),
    ],
)
async def test_turn_on_brightness(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    classic_led_ctrl_mock: EheimDigitalClassicLEDControl,
    dim_input: int,
    expected_dim_value: int,
) -> None:
    """Test turning on the light with different brightness values."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    classic_led_ctrl_mock.hub.send_packet.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.mock_classicledcontrol_e_channel_1",
                ATTR_BRIGHTNESS: dim_input,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"

    classic_led_ctrl_mock.hub.send_packet.side_effect = None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.mock_classicledcontrol_e_channel_1",
            ATTR_BRIGHTNESS: dim_input,
        },
        blocking=True,
    )

    calls = [
        call
        for call in classic_led_ctrl_mock.hub.mock_calls
        if call[0] == "send_packet"
    ]
    assert len(calls) == 3
    assert calls[1][1][0].get("title") == "MAN_MODE"
    assert calls[2][1][0]["currentValues"][1] == expected_dim_value


async def test_turn_on_effect(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    classic_led_ctrl_mock: EheimDigitalClassicLEDControl,
) -> None:
    """Test turning on the light with an effect value."""
    classic_led_ctrl_mock.clock["mode"] = "MAN_MODE"

    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.mock_classicledcontrol_e_channel_1",
            ATTR_EFFECT: EFFECT_DAYCL_MODE,
        },
        blocking=True,
    )

    calls = [
        call
        for call in classic_led_ctrl_mock.hub.mock_calls
        if call[0] == "send_packet"
    ]
    assert len(calls) == 1
    assert calls[0][1][0].get("title") == "DAYCL_MODE"


async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    classic_led_ctrl_mock: EheimDigitalClassicLEDControl,
) -> None:
    """Test the light state update."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    classic_led_ctrl_mock.ccv["currentValues"] = [30, 20]

    await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

    assert (state := hass.states.get("light.mock_classicledcontrol_e_channel_1"))
    assert state.attributes["brightness"] == value_to_brightness((1, 100), 20)


async def test_update_failed(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an failed update."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    eheimdigital_hub_mock.return_value.update.side_effect = ClientError

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("light.mock_classicledcontrol_e_channel_1").state
        == STATE_UNAVAILABLE
    )
