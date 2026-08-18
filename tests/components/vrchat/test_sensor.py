"""Test VRChat sensors."""

from types import SimpleNamespace
from typing import cast

from homeassistant.components.vrchat.api_data_types import World
from homeassistant.components.vrchat.const import VRChatUserState
from homeassistant.components.vrchat.coordinator import VRChatUserDataCoordinator
from homeassistant.components.vrchat.sensor import VRChatUserLocationSensor
from homeassistant.components.vrchat.utils import VRChatSpecialLocationString
from homeassistant.components.vrchat.world import VRChatWorldData


def test_location_sensor_without_world_metadata() -> None:
    """Test an unresolved world ID has no location state."""
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(
                data={"location": "wrld_test", "worldId": "wrld_test"},
                world=None,
                destination_world=None,
            ),
        )
    )

    assert sensor.native_value is None


def test_location_sensor_options_are_stable_and_unique() -> None:
    """Test location sensor options have a stable order without duplicates."""
    VRChatWorldData.registry.clear()
    VRChatWorldData.get("wrld_first", cast(World, {"name": "World one"}))
    VRChatWorldData.get("wrld_second", cast(World, {"name": "World one"}))
    VRChatWorldData.get("wrld_third", cast(World, {"name": "World two"}))
    VRChatWorldData.get("wrld_offline", cast(World, {"name": "offline"}))
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(data={}, world=None, destination_world=None),
        )
    )

    assert sensor.options == [
        *VRChatSpecialLocationString,
        VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE,
        "World one",
        "World two",
    ]
