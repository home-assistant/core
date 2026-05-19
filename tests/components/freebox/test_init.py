"""Tests for the Freebox init."""

from copy import deepcopy
from unittest.mock import ANY, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import setup_platform
from .const import DATA_HOME_GET_NODES, MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_MAC = "68:A3:78:00:00:00"


async def test_setup(hass: HomeAssistant, router: Mock) -> None:
    """Test setup of integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
        version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1


async def test_setup_import(hass: HomeAssistant, router: Mock) -> None:
    """Test setup of integration from import."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
        version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}}
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1


async def test_unload_remove(hass: HomeAssistant, router: Mock) -> None:
    """Test unload and remove of integration."""
    entity_id_dt = f"{DT_DOMAIN}.freebox_server_r2"
    entity_id_sensor = f"{SENSOR_DOMAIN}.freebox_server_r2_download_speed"
    entity_id_switch = f"{SWITCH_DOMAIN}.freebox_server_r2_wi_fi"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        version=2,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt.state == STATE_UNAVAILABLE
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor.state == STATE_UNAVAILABLE
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch.state == STATE_UNAVAILABLE

    assert router().close.call_count == 1

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert router().close.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt is None
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor is None
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch is None


@pytest.mark.parametrize(
    ("platform", "old_suffix", "new_key"),
    [
        (SENSOR_DOMAIN, "Freebox download speed", "rate_down"),
        (SENSOR_DOMAIN, "Freebox upload speed", "rate_up"),
        (SENSOR_DOMAIN, "Freebox missed calls", "missed"),
        (SENSOR_DOMAIN, "Freebox Disque dur", "temp_hdd"),
        (SENSOR_DOMAIN, "Freebox Disque dur 2", "temp_hdd2"),
        (SENSOR_DOMAIN, "Freebox Température Switch", "temp_sw"),
        (SENSOR_DOMAIN, "Freebox Température CPU M", "temp_cpum"),
        (SENSOR_DOMAIN, "Freebox Température CPU B", "temp_cpub"),
        (BUTTON_DOMAIN, "Reboot Freebox", "reboot"),
        (BUTTON_DOMAIN, "Mark calls as read", "mark_calls_as_read"),
        (SWITCH_DOMAIN, "Freebox WiFi", "wifi"),
    ],
)
async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    router: Mock,
    platform: str,
    old_suffix: str,
    new_key: str,
) -> None:
    """Test migration of name-based unique ids to key-based ones."""
    old_unique_id = f"{MOCK_MAC} {old_suffix}"
    new_unique_id = f"{MOCK_MAC} {new_key}"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        old_unique_id,
        config_entry=entry,
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(platform, DOMAIN, old_unique_id) is None
    assert (
        entity_registry.async_get_entity_id(platform, DOMAIN, new_unique_id) is not None
    )


async def test_home_device_label_sync(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test home device label changes propagate to the device registry."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    pir_node_id = 26  # Détecteur from fixture
    device = device_registry.async_get_device(identifiers={(DOMAIN, pir_node_id)})
    assert device is not None
    assert device.name == "Détecteur"

    # API now returns a different label for the PIR.
    updated_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in updated_nodes:
        if node["id"] == pir_node_id:
            node["label"] = "Détecteur cuisine"
            break
    router().home.get_home_nodes.return_value = updated_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, pir_node_id)})
    assert device is not None
    assert device.name == "Détecteur cuisine"
