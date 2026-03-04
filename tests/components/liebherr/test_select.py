"""Test the Liebherr select platform."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    BioFreshPlusMode,
    Device,
    DeviceState,
    DeviceType,
    HydroBreezeControl,
    HydroBreezeMode,
    IceMakerControl,
    IceMakerMode,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import LiebherrConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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
    return [Platform.SELECT]


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("init_integration")
async def test_selects(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all select entities with multi-zone device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "option", "method", "kwargs"),
    [
        (
            "select.test_fridge_bottom_zone_icemaker",
            "on",
            "set_ice_maker",
            {
                "device_id": "test_device_id",
                "zone_id": 2,
                "mode": IceMakerMode.ON,
            },
        ),
        (
            "select.test_fridge_bottom_zone_icemaker",
            "max_ice",
            "set_ice_maker",
            {
                "device_id": "test_device_id",
                "zone_id": 2,
                "mode": IceMakerMode.MAX_ICE,
            },
        ),
        (
            "select.test_fridge_top_zone_hydrobreeze",
            "high",
            "set_hydro_breeze",
            {
                "device_id": "test_device_id",
                "zone_id": 1,
                "mode": HydroBreezeMode.HIGH,
            },
        ),
        (
            "select.test_fridge_top_zone_hydrobreeze",
            "off",
            "set_hydro_breeze",
            {
                "device_id": "test_device_id",
                "zone_id": 1,
                "mode": HydroBreezeMode.OFF,
            },
        ),
        (
            "select.test_fridge_top_zone_biofresh_plus",
            "zero_minus_two",
            "set_bio_fresh_plus",
            {
                "device_id": "test_device_id",
                "zone_id": 1,
                "mode": BioFreshPlusMode.ZERO_MINUS_TWO,
            },
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_service_calls(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    entity_id: str,
    option: str,
    method: str,
    kwargs: dict[str, Any],
) -> None:
    """Test select option service calls."""
    initial_call_count = mock_liebherr_client.get_device_state.call_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    getattr(mock_liebherr_client, method).assert_called_once_with(**kwargs)

    # Verify coordinator refresh was triggered
    assert mock_liebherr_client.get_device_state.call_count > initial_call_count


@pytest.mark.parametrize(
    ("entity_id", "method", "option"),
    [
        ("select.test_fridge_bottom_zone_icemaker", "set_ice_maker", "off"),
        ("select.test_fridge_top_zone_hydrobreeze", "set_hydro_breeze", "off"),
        (
            "select.test_fridge_top_zone_biofresh_plus",
            "set_bio_fresh_plus",
            "zero_zero",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    entity_id: str,
    method: str,
    option: str,
) -> None:
    """Test select fails gracefully on connection error."""
    getattr(mock_liebherr_client, method).side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the device",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_select_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select entity behavior when control is removed."""
    entity_id = "select.test_fridge_bottom_zone_icemaker"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Device stops reporting select controls
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_single_zone_select(
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
            IceMakerControl(
                name="icemaker",
                type="IceMakerControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                ice_maker_mode=IceMakerMode.ON,
                has_max_ice=False,
            ),
            HydroBreezeControl(
                name="hydrobreeze",
                type="HydroBreezeControl",
                zone_id=1,
                current_mode=HydroBreezeMode.OFF,
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


@pytest.mark.usefixtures("init_integration")
async def test_select_current_option_none_mode(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select entity state when control mode returns None."""
    entity_id = "select.test_fridge_top_zone_hydrobreeze"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "low"

    # Simulate update where mode is None
    state_with_none_mode = copy.deepcopy(MOCK_DEVICE_STATE)
    for control in state_with_none_mode.controls:
        if isinstance(control, HydroBreezeControl):
            control.current_mode = None
            break

    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        state_with_none_mode
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
