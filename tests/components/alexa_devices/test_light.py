"""Tests for the Alexa Devices light platform."""

from typing import Any
from unittest.mock import AsyncMock, call, patch

from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
    CannotSetFeature,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_GLOW, TEST_DEVICE_GLOW_SN

ENTITY_ID = "light.echo_glow_test"


@pytest.fixture(autouse=True)
def mock_glow_device(mock_amazon_devices_client: AsyncMock) -> None:
    """Return the Echo Glow as the only device."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_GLOW_SN: TEST_DEVICE_GLOW
    }


@pytest.mark.usefixtures("mock_amazon_devices_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_call"),
    [
        pytest.param(
            SERVICE_TURN_OFF,
            {},
            call(
                TEST_DEVICE_GLOW,
                "power",
                "turnOff",
                command_payload=None,
                instance=None,
            ),
            id="turn_off",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 255},
            call(
                TEST_DEVICE_GLOW,
                "brightness",
                "setBrightness",
                command_payload={"brightness": 100},
                instance=None,
            ),
            id="brightness",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 1},
            call(
                TEST_DEVICE_GLOW,
                "brightness",
                "setBrightness",
                command_payload={"brightness": 1},
                instance=None,
            ),
            id="brightness_minimum",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            {ATTR_HS_COLOR: (240, 80)},
            call(
                TEST_DEVICE_GLOW,
                "color",
                "setColor",
                command_payload={
                    "color": {"hue": 240, "saturation": 0.8, "brightness": 1.0}
                },
                instance=None,
            ),
            id="hs_color",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "Solid Color"},
            call(
                TEST_DEVICE_GLOW,
                "mode",
                "setMode",
                command_payload={"mode": "1"},
                instance="1",
            ),
            id="effect",
        ),
    ],
)
async def test_light_services(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
    expected_call: Any,
) -> None:
    """Test light services call the matching feature operation."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert mock_amazon_devices_client.call_feature_operation.call_args_list == [
        expected_call
    ]


async def test_turn_on_when_off(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a light that is off powers it on first."""
    mock_amazon_devices_client.sensors[TEST_DEVICE_GLOW_SN]["Power"].value = "OFF"
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_amazon_devices_client.call_feature_operation.assert_called_once_with(
        TEST_DEVICE_GLOW,
        "power",
        "turnOn",
        command_payload=None,
        instance=None,
    )


async def test_pushed_sensor_update(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light reflects sensor values pushed by the Amazon API."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    mock_amazon_devices_client.sensors[TEST_DEVICE_GLOW_SN]["Power"].value = "OFF"
    event_handler = mock_amazon_devices_client.on_sensor_event.append.call_args.args[0]
    await event_handler()
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_unknown_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light state is unknown when its sensors are missing."""
    mock_amazon_devices_client.sensors[TEST_DEVICE_GLOW_SN] = {}
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(
            CannotSetFeature("rejected"),
            "cannot_set_feature_with_error",
            id="set_feature",
        ),
        pytest.param(CannotAuthenticate("expired"), "invalid_auth", id="authenticate"),
        pytest.param(
            CannotConnect("timeout"), "cannot_connect_with_error", id="connect"
        ),
        pytest.param(
            CannotRetrieveData("bad response"),
            "cannot_retrieve_data_with_error",
            id="retrieve_data",
        ),
    ],
)
async def test_feature_operation_error(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Test a failed feature operation raises an error."""
    await setup_integration(hass, mock_config_entry)

    mock_amazon_devices_client.call_feature_operation.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key


async def test_partial_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test attributes are unset when only the power state is known."""
    sensors = mock_amazon_devices_client.sensors[TEST_DEVICE_GLOW_SN]
    mock_amazon_devices_client.sensors[TEST_DEVICE_GLOW_SN] = {
        "Power": sensors["Power"]
    }
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.attributes[ATTR_HS_COLOR] is None
    assert state.attributes[ATTR_EFFECT] is None
