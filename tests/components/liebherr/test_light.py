"""Test the Liebherr light platform."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import Device, DeviceState, DeviceType, PresentationLightControl
from pyliebherrhomeapi.exceptions import LiebherrConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


@pytest.mark.usefixtures("init_integration")
async def test_lights(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_light_state(
    hass: HomeAssistant,
) -> None:
    """Test light entity reports correct state."""
    entity_id = "light.test_fridge_presentation_light"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    # value=3, max=5 → brightness = ceil(3 * 255 / 5) = 153
    assert state.attributes[ATTR_BRIGHTNESS] == 153


@pytest.mark.parametrize(
    ("service", "service_data", "expected_target"),
    [
        (SERVICE_TURN_ON, {}, 5),
        (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 255}, 5),
        (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 128}, 3),
        (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 51}, 1),
        (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 1}, 1),
        (SERVICE_TURN_OFF, {}, 0),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_light_service_calls(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    service: str,
    service_data: dict[str, Any],
    expected_target: int,
) -> None:
    """Test light turn on/off service calls."""
    entity_id = "light.test_fridge_presentation_light"
    initial_call_count = mock_liebherr_client.get_device_state.call_count

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_liebherr_client.set_presentation_light.assert_called_once_with(
        device_id="test_device_id",
        target=expected_target,
    )

    # Verify coordinator refresh was triggered
    assert mock_liebherr_client.get_device_state.call_count > initial_call_count


@pytest.mark.usefixtures("init_integration")
async def test_light_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test light fails gracefully on connection error."""
    entity_id = "light.test_fridge_presentation_light"
    mock_liebherr_client.set_presentation_light.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the device",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_light_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test light entity behavior when control is removed."""
    entity_id = "light.test_fridge_presentation_light"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Device stops reporting presentation light control
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("value", "max_value", "expected_state", "expected_brightness"),
    [
        (0, 5, STATE_OFF, None),
        (None, 5, STATE_UNKNOWN, None),
        (1, 0, STATE_ON, None),
    ],
    ids=["off", "null_value", "zero_max"],
)
@pytest.mark.usefixtures("init_integration")
async def test_light_state_updates(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    value: int | None,
    max_value: int,
    expected_state: str,
    expected_brightness: int | None,
) -> None:
    """Test light entity state after coordinator update."""
    entity_id = "light.test_fridge_presentation_light"

    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE,
        controls=[
            PresentationLightControl(
                name="presentationlight",
                type="PresentationLightControl",
                value=value,
                max=max_value,
            ),
        ],
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected_brightness


async def test_no_light_entity_without_control(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test no light entity created when device has no presentation light control."""
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("light.test_fridge_presentation_light") is None


async def test_dynamic_device_discovery_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices with presentation light are automatically discovered."""
    mock_config_entry.add_to_hass(hass)

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", [Platform.LIGHT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("light.test_fridge_presentation_light") is not None
    assert hass.states.get("light.new_fridge_presentation_light") is None

    new_device = Device(
        device_id="new_device_id",
        nickname="New Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    new_device_state = DeviceState(
        device=new_device,
        controls=[
            PresentationLightControl(
                name="presentationlight",
                type="PresentationLightControl",
                value=2,
                max=5,
            ),
        ],
    )

    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, new_device]
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(
            new_device_state if device_id == "new_device_id" else MOCK_DEVICE_STATE
        )
    )

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("light.new_fridge_presentation_light")
    assert state is not None
    assert state.state == STATE_ON
