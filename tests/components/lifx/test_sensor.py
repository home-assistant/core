"""Tests for the lifx integration sensor platform."""

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN, LIFXCoordination
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    SIGNAL_STRENGTH_DECIBELS,
    TIME_MINUTES,
    TIME_SECONDS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.setup import async_setup_component

from . import (
    IP_ADDRESS,
    MAC_ADDRESS,
    MockFailingLifxCommand,
    _mocked_bulb,
    _mocked_hev_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry


async def test_rssi_and_uptime_sensors(hass: HomeAssistant) -> None:
    """Test the RSSI sensor on a LIFX bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_ids = ["sensor.my_bulb_rssi", "sensor.my_bulb_uptime"]

    entity_registry = er.async_get(hass)
    registry_entries = [
        entity_registry.entities.get(entity_id) for entity_id in entity_ids
    ]
    assert [registry_entry.disabled for registry_entry in registry_entries]
    assert [
        registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for registry_entry in registry_entries
    ]

    enabled_entities = [
        entity_registry.async_update_entity(entity_id, disabled_by=None)
        for entity_id in entity_ids
    ]
    assert [not enabled_entity.disabled for enabled_entity in enabled_entities]

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    states = [hass.states.get(entity_id) for entity_id in entity_ids]
    assert states[0].state == "16"
    assert states[1].state == "609815"
    assert (
        states[0].attributes.get(ATTR_UNIT_OF_MEASUREMENT) == SIGNAL_STRENGTH_DECIBELS
    )
    assert states[1].attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS

    disabled_entities = [
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )
        for entity_id in entity_ids
    ]
    assert [disabled_entity.disabled for disabled_entity in disabled_entities]


async def test_hev_sensors(hass: HomeAssistant) -> None:
    """Test the RSSI sensor on a LIFX bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_hev_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    expected = {
        "sensor.my_bulb_clean_cycle_duration": ("7200", TIME_MINUTES),
        "sensor.my_bulb_clean_cycle_remaining": ("0", TIME_MINUTES),
        "sensor.my_bulb_clean_cycle_last_power": ("False", None),
        "sensor.my_bulb_clean_cycle_last_result": ("unknown", None),
    }

    entity_id = "light.my_bulb"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    for sensor_entity_id, value in expected.items():
        state = hass.states.get(sensor_entity_id)
        assert state.state == value[0]
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == value[1]

    updated = {
        "sensor.my_bulb_clean_cycle_duration": "7200",
        "sensor.my_bulb_clean_cycle_remaining": "300",
        "sensor.my_bulb_clean_cycle_last_power": "True",
    }

    for sensor_entity_id, value in updated.items():
        await async_update_entity(hass, sensor_entity_id)
        await hass.async_block_till_done()

        state = hass.states.get(sensor_entity_id)
        assert state.state == value

    entity_registry = er.async_get(hass)
    disabled_entity = entity_registry.async_update_entity(
        "sensor.my_bulb_clean_cycle_last_power",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    assert disabled_entity.disabled


async def test_failing_sensors(hass: HomeAssistant) -> None:
    """Test the RSSI sensor on a LIFX bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_hev_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = [
        entity
        for entity in async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == Platform.SENSOR
    ]

    for entity in entities:
        entity_registry.async_update_entity(entity.entity_id, disabled_by=None)

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    lifx_coordination: LIFXCoordination = hass.data[DOMAIN][config_entry.entry_id]
    sensor_coordinator = lifx_coordination.sensor_coordinator

    bulb.get_hostinfo = MockFailingLifxCommand(bulb)
    bulb.get_wifiinfo = MockFailingLifxCommand(bulb)
    bulb.get_hev_cycle = MockFailingLifxCommand(bulb)
    bulb.get_last_hev_cycle_result = MockFailingLifxCommand(bulb)

    for entity in entities:

        [
            setattr(
                sensor_coordinator,
                f"update_{sensor.unique_id.removeprefix('aa:bb:cc:dd:ee:cc_')}",
                False,
            )
            for sensor in entities
            if sensor.entity_id != entity.entity_id
        ]
        failing_sensor = entity.unique_id.removeprefix("aa:bb:cc:dd:ee:cc_")
        setattr(sensor_coordinator, f"update_{failing_sensor}", True)
        await sensor_coordinator.async_refresh()
        assert not sensor_coordinator.last_update_success
