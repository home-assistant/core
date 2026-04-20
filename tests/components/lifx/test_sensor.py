"""Test the LIFX sensor platform."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx.coordinator import LIFXUpdateCoordinator
from homeassistant.components.lifx.sensor import LIFXRssiSensor
from homeassistant.components.sensor import (
    DATA_COMPONENT as SENSOR_DATA_COMPONENT,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    SERIAL,
    _mocked_bulb,
    _mocked_bulb_old_firmware,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_discovery")
async def test_rssi_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test LIFX RSSI sensor entity."""

    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_bulb_rssi"
    assert not hass.states.get(entity_id)

    entry = entity_registry.entities.get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity, this will trigger a reload of the config entry
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False
    assert updated_entry.unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done()

    rssi = hass.states.get(entity_id)
    assert (
        rssi.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert rssi.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi.attributes["state_class"] == SensorStateClass.MEASUREMENT


@pytest.mark.usefixtures("mock_discovery")
async def test_rssi_sensor_old_firmware(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test LIFX RSSI sensor entity."""

    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_old_firmware()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_bulb_rssi"

    entry = entity_registry.entities.get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity, this will trigger a reload of the config entry
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False
    assert updated_entry.unit_of_measurement == SIGNAL_STRENGTH_DECIBELS

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done()

    rssi = hass.states.get(entity_id)
    assert rssi.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS
    assert rssi.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_rssi_sensor_entity_handles_coordinator_updates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the RSSI entity updates its native value from the coordinator."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    updated_entry = entity_registry.async_update_entity(
        "sensor.my_bulb_rssi", disabled_by=None
    )
    assert updated_entry.disabled is False

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done()

    entity = hass.data[SENSOR_DATA_COMPONENT].get_entity("sensor.my_bulb_rssi")
    assert isinstance(entity, LIFXRssiSensor)

    entity.coordinator._rssi = 42
    entity._handle_coordinator_update()

    assert entity.native_value == 42


async def test_coordinator_rssi_update_and_set_color(hass: HomeAssistant) -> None:
    """Test coordinator RSSI updates and set_color dispatch."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    bulb = _mocked_bulb()
    connection = SimpleNamespace(device=bulb)
    coordinator = LIFXUpdateCoordinator(hass, config_entry, connection)

    disable_rssi = coordinator.async_enable_rssi_updates()

    with patch(
        "homeassistant.components.lifx.coordinator.async_multi_execute_lifx_with_retries",
        AsyncMock(
            return_value=[
                SimpleNamespace(target_addr=SERIAL),
                SimpleNamespace(signal=100),
            ]
        ),
    ) as mock_multi:
        await coordinator._async_update_data()

    methods = mock_multi.await_args.args[0]
    assert methods[0] == bulb.get_color
    assert methods[1] == bulb.get_wifiinfo
    assert coordinator.rssi == 20
    assert coordinator.rssi_uom == SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    disable_rssi()

    with patch(
        "homeassistant.components.lifx.coordinator.async_execute_lifx",
        AsyncMock(),
    ) as mock_execute:
        await coordinator.async_set_color([1, 2, 3, 4], 123)

    mock_execute.assert_awaited_once()
