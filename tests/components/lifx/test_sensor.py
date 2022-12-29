"""Test the LIFX sensor platform."""
from __future__ import annotations

from datetime import timedelta
from random import randint

from homeassistant.components import lifx
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
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
    MAC_ADDRESS,
    _mocked_bulb,
    _mocked_bulb_old_firmware,
    _mocked_light_strip,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_zones_sensor(hass: HomeAssistant) -> None:
    """Test the zones sensor for multizone devices."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    # generate random zone values and count
    _random_color_zones = []
    for _ in range(0, randint(8, 80)):
        _random_color_zones.append(
            (
                randint(0, 65535),
                randint(0, 65535),
                randint(0, 65535),
                randint(1500, 9000),
            )
        )
    _random_zone_index = randint(0, len(_random_color_zones))
    bulb.zones_count = len(_random_color_zones)
    bulb.color_zones = _random_color_zones.copy()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_bulb_zones"
    entity_registry = er.async_get(hass)

    entry = entity_registry.entities.get(entity_id)
    assert entry
    assert entry.disabled is False

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    zones = hass.states.get(entity_id)

    # test that the sensor has the same value as the length of the randomly
    # generated strip and that a random zone on that strip matches the
    # calculated sensor attributes for that zone
    random_color_zone = _random_color_zones[_random_zone_index]
    assert zones.state == str(len(_random_color_zones))
    assert zones.attributes[f"Zone {_random_zone_index}"] == {
        "brightness_pct": round(random_color_zone[2] / 65535 * 100),
        "brightness": round(lifx.util.convert_16_to_8(random_color_zone[2])),
        "color_temp_kelvin": random_color_zone[3],
        "hs_color": f"({int((random_color_zone[0]/65535)*360)}, {int((random_color_zone[1]/65535) * 100)})",
    }

    disabled_entry = entity_registry.async_update_entity(
        entry.entity_id, **{"disabled_by": er.RegistryEntryDisabler.USER}
    )
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert disabled_entry != entry
    assert disabled_entry.disabled is True


async def test_rssi_sensor(hass: HomeAssistant) -> None:
    """Test LIFX RSSI sensor entity."""

    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
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

    entity_id = "sensor.my_bulb_rssi"
    entity_registry = er.async_get(hass)

    entry = entity_registry.entities.get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert updated_entry != entry
    assert updated_entry.disabled is False
    assert updated_entry.unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    rssi = hass.states.get(entity_id)
    assert (
        rssi.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert rssi.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_rssi_sensor_old_firmware(hass: HomeAssistant) -> None:
    """Test LIFX RSSI sensor entity."""

    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_old_firmware()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_bulb_rssi"
    entity_registry = er.async_get(hass)

    entry = entity_registry.entities.get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert updated_entry != entry
    assert updated_entry.disabled is False
    assert updated_entry.unit_of_measurement == SIGNAL_STRENGTH_DECIBELS

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    rssi = hass.states.get(entity_id)
    assert rssi.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS
    assert rssi.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi.attributes["state_class"] == SensorStateClass.MEASUREMENT
