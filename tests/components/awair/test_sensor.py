"""Tests for the Awair sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.awair.sensor import (
    SENSOR_TYPE_SCORE,
    SENSOR_TYPES,
    SENSOR_TYPES_DUST,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_awair
from .const import CLOUD_CONFIG, CLOUD_UNIQUE_ID, LOCAL_CONFIG, LOCAL_UNIQUE_ID

from tests.common import async_fire_time_changed, snapshot_platform

SENSOR_TYPES_MAP = {
    desc.key: desc for desc in (SENSOR_TYPE_SCORE, *SENSOR_TYPES, *SENSOR_TYPES_DUST)
}


def assert_expected_properties(
    hass: HomeAssistant,
    entity_registry: er.RegistryEntry,
    name: str,
    unique_id: str,
    state_value: str,
    attributes: dict,
    model="Awair",
    model_id="awair",
):
    """Assert expected properties from a dict."""
    entity_entry = entity_registry.async_get(name)
    assert entity_entry.unique_id == unique_id

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.model == model
    assert device_entry.model_id == model_id

    state = hass.states.get(name)
    assert state
    assert state.state == state_value
    for attr, value in attributes.items():
        assert state.attributes.get(attr) == value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_awair_gen1_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen1_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on a 1st gen Awair."""

    fixtures = [user, cloud_devices, gen1_data]
    entry = await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_awair_gen2_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen2_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on a 2nd gen Awair."""

    fixtures = [user, cloud_devices, gen2_data]
    entry = await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_local_awair_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    local_devices,
    local_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on a local Awair."""

    fixtures = [local_devices, local_data]
    entry = await setup_awair(hass, fixtures, LOCAL_UNIQUE_ID, LOCAL_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_awair_mint_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    mint_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on an Awair mint."""

    fixtures = [user, cloud_devices, mint_data]
    entry = await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_awair_glow_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    glow_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on an Awair glow."""

    fixtures = [user, cloud_devices, glow_data]
    entry = await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_awair_omni_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    omni_data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test expected sensors on an Awair omni."""

    fixtures = [user, cloud_devices, omni_data]
    entry = await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_awair_offline(
    hass: HomeAssistant, user, cloud_devices, awair_offline
) -> None:
    """Test expected behavior when an Awair is offline."""

    fixtures = [user, cloud_devices, awair_offline]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    # The expected behavior is that we won't have any sensors
    # if the device is not online when we set it up. python_awair
    # does not make any assumptions about what sensors a device
    # might have - they are created dynamically.

    # We check for the absence of the "awair score", which every
    # device *should* have if it's online. If we don't see it,
    # then we probably didn't set anything up. Which is correct,
    # in this case.
    assert hass.states.get("sensor.living_room_score") is None


async def test_awair_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen1_data,
    awair_offline,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test expected behavior when an Awair becomes offline later."""

    fixtures = [user, cloud_devices, gen1_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert hass.states.get("sensor.living_room_score").state != STATE_UNAVAILABLE

    with patch("python_awair.AwairClient.query", side_effect=awair_offline):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert hass.states.get("sensor.living_room_score").state == STATE_UNAVAILABLE
