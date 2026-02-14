"""Test the Liebherr switch platform."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ToggleControl,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import LiebherrConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("init_integration")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all switch entities with multi-zone device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "service", "method", "kwargs"),
    [
        (
            "switch.test_fridge_top_zone_supercool",
            SERVICE_TURN_ON,
            "set_supercool",
            {"device_id": "test_device_id", "zone_id": 1, "value": True},
        ),
        (
            "switch.test_fridge_top_zone_supercool",
            SERVICE_TURN_OFF,
            "set_supercool",
            {"device_id": "test_device_id", "zone_id": 1, "value": False},
        ),
        (
            "switch.test_fridge_bottom_zone_superfrost",
            SERVICE_TURN_ON,
            "set_superfrost",
            {"device_id": "test_device_id", "zone_id": 2, "value": True},
        ),
        (
            "switch.test_fridge_party_mode",
            SERVICE_TURN_ON,
            "set_party_mode",
            {"device_id": "test_device_id", "value": True},
        ),
        (
            "switch.test_fridge_night_mode",
            SERVICE_TURN_OFF,
            "set_night_mode",
            {"device_id": "test_device_id", "value": False},
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_service_calls(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    entity_id: str,
    service: str,
    method: str,
    kwargs: dict[str, Any],
) -> None:
    """Test switch turn on/off service calls."""
    initial_call_count = mock_liebherr_client.get_device_state.call_count

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_liebherr_client, method).assert_called_once_with(**kwargs)

    # Verify coordinator refresh was triggered
    assert mock_liebherr_client.get_device_state.call_count > initial_call_count


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("switch.test_fridge_top_zone_supercool", "set_supercool"),
        ("switch.test_fridge_party_mode", "set_party_mode"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test switch fails gracefully on connection error."""
    getattr(mock_liebherr_client, method).side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the device: Connection failed",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_switch_update_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch becomes unavailable when coordinator update fails and recovers."""
    entity_id = "switch.test_fridge_top_zone_supercool"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate update error
    mock_liebherr_client.get_device_state.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate recovery
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        MOCK_DEVICE_STATE
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_switch_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch entity behavior when toggle control is removed."""
    entity_id = "switch.test_fridge_top_zone_supercool"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Device stops reporting toggle controls
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_single_zone_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test single zone device uses name without zone suffix."""
    device = Device(
        device_id="single_zone_id",
        nickname="Single Zone Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    single_zone_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=4,
                target=4,
                min=2,
                max=8,
                unit=TemperatureUnit.CELSIUS,
            ),
            ToggleControl(
                name="supercool",
                type="ToggleControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                value=False,
            ),
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        single_zone_state
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
