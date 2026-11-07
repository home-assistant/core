"""Tests for the sensor module."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync import VeSync
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import ProductTypes, TemperatureUnits
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_HUMIDIFIER_HUMIDITY, mock_devices_response


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_sensor_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == SENSOR_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("cook_status", "expected_state"),
    [
        pytest.param(None, "unknown", id="missing"),
        pytest.param("appointing", "appointing", id="appointing"),
    ],
)
async def test_cook_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    cook_status: str | None,
    expected_state: str,
) -> None:
    """Test cook status values supported by the integration."""
    mock_devices_response(
        aioclient_mock,
        "CS158-AF Air Fryer Cooking",
        details_override={"cookStatus": cook_status},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cs158_af_air_fryer_cooking_basket_1_cooking_status")
    assert state is not None
    assert state.state == expected_state


async def test_dual_chamber_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fryer sensors are created for both chambers."""
    chamber_1 = cast(
        FryerState,
        SimpleNamespace(
            connection_status="online",
            cook_status="cooking",
            current_temp=101,
            cook_set_temp=180,
            cook_set_time=600,
            preheat_set_time=120,
        ),
    )
    chamber_2 = cast(
        FryerState,
        SimpleNamespace(
            connection_status="online",
            cook_status="standby",
            current_temp=202,
            cook_set_temp=200,
            cook_set_time=900,
            preheat_set_time=180,
        ),
    )
    fryer = Mock(
        VeSyncFryer,
        cid="dual_fryer",
        device_name="Dual Fryer",
        device_type="Dual Air Fryer",
        product_type=ProductTypes.AIR_FRYER,
        sub_device_no=None,
        current_firm_version="1.0",
        state=chamber_1,
        state_chamber_1=chamber_1,
        state_chamber_2=chamber_2,
        is_dual_chamber=True,
        temp_unit=TemperatureUnits.CELSIUS,
    )
    manager._dev_list["air_fryers"].append(cast(VeSyncFryer, fryer))

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == SENSOR_DOMAIN
    ]
    sensor_keys = {
        "cook_status",
        "current_temp",
        "cook_set_temp",
        "cook_set_time",
        "preheat_set_time",
    }
    assert {entity.unique_id for entity in entities} == {
        f"dual_fryer-{key}{suffix}"
        for key in sensor_keys
        for suffix in ("", "-chamber_2")
    }

    states_by_unique_id = {}
    for entity in entities:
        state = hass.states.get(entity.entity_id)
        assert state is not None
        states_by_unique_id[entity.unique_id] = state.state
    assert states_by_unique_id["dual_fryer-current_temp"] == "101"
    assert states_by_unique_id["dual_fryer-current_temp-chamber_2"] == "202"
    assert states_by_unique_id["dual_fryer-cook_status"] == "cooking"
    assert states_by_unique_id["dual_fryer-cook_status-chamber_2"] == "standby"


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"
