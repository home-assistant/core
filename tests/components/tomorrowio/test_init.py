"""Tests for Tomorrow.io init."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.climacell.const import CONF_TIMESTEP, DOMAIN as CC_DOMAIN
from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.tomorrowio.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import MIN_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.climacell.const import API_V3_ENTRY_DATA

NEW_NAME = "New Name"


async def test_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading entry."""
    data = _get_config_schema(hass, SOURCE_USER)(MIN_CONFIG)
    data[CONF_NAME] = "test"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options={CONF_TIMESTEP: 1},
        unique_id=_get_unique_id(hass, data),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0


async def test_update_intervals(
    hass: HomeAssistant, tomorrowio_config_entry_update
) -> None:
    """Test coordinator update intervals."""
    now = dt_util.utcnow()
    data = _get_config_schema(hass, SOURCE_USER)(MIN_CONFIG)
    data[CONF_NAME] = "test"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options={CONF_TIMESTEP: 1},
        unique_id=_get_unique_id(hass, data),
        version=1,
    )
    config_entry.add_to_hass(hass)
    with patch("homeassistant.helpers.update_coordinator.utcnow", return_value=now):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(tomorrowio_config_entry_update.call_args_list) == 1

    tomorrowio_config_entry_update.reset_mock()

    # Before the update interval, no updates yet
    future = now + timedelta(minutes=30)
    with patch("homeassistant.helpers.update_coordinator.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert len(tomorrowio_config_entry_update.call_args_list) == 0

    tomorrowio_config_entry_update.reset_mock()

    # On the update interval, we get a new update
    future = now + timedelta(minutes=32)
    with patch("homeassistant.helpers.update_coordinator.utcnow", return_value=future):
        async_fire_time_changed(hass, now + timedelta(minutes=32))
        await hass.async_block_till_done()
        assert len(tomorrowio_config_entry_update.call_args_list) == 1

        tomorrowio_config_entry_update.reset_mock()

        # Adding a second config entry should cause the update interval to double
        config_entry_2 = MockConfigEntry(
            domain=DOMAIN,
            data=data,
            options={CONF_TIMESTEP: 1},
            unique_id=f"{_get_unique_id(hass, data)}_1",
            version=1,
        )
        config_entry_2.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry_2.entry_id)
        await hass.async_block_till_done()
        assert config_entry.data[CONF_API_KEY] == config_entry_2.data[CONF_API_KEY]
        # We should get an immediate call once the new config entry is setup for a
        # partial update
        assert len(tomorrowio_config_entry_update.call_args_list) == 1

    tomorrowio_config_entry_update.reset_mock()

    # We should get no new calls on our old interval
    future = now + timedelta(minutes=64)
    with patch("homeassistant.helpers.update_coordinator.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert len(tomorrowio_config_entry_update.call_args_list) == 0

    tomorrowio_config_entry_update.reset_mock()

    # We should get two calls on our new interval, one for each entry
    future = now + timedelta(minutes=96)
    with patch("homeassistant.helpers.update_coordinator.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert len(tomorrowio_config_entry_update.call_args_list) == 2

    tomorrowio_config_entry_update.reset_mock()


async def test_climacell_migration_logic(
    hass: HomeAssistant, climacell_config_entry_update
) -> None:
    """Test that climacell config entry is properly migrated."""
    old_data = API_V3_ENTRY_DATA.copy()
    old_data[CONF_API_KEY] = "v3apikey"
    old_config_entry = MockConfigEntry(
        domain=CC_DOMAIN,
        data=old_data,
        unique_id="v3apikey_80.0_80.0",
        version=1,
    )
    old_config_entry.add_to_hass(hass)
    # Let's create a device and update its name
    dev_reg = dr.async_get(hass)
    old_device = dev_reg.async_get_or_create(
        config_entry_id=old_config_entry.entry_id,
        identifiers={(CC_DOMAIN, old_data[CONF_API_KEY])},
        manufacturer="ClimaCell",
        sw_version="v4",
        entry_type="service",
        name="ClimaCell",
    )
    dev_reg.async_update_device(old_device.id, name_by_user=NEW_NAME)
    # Now let's create some entity and update some things to see if everything migrates
    # over
    ent_reg = er.async_get(hass)
    old_entity_daily = ent_reg.async_get_or_create(
        "weather",
        CC_DOMAIN,
        "v3apikey_80.0_80.0_daily",
        config_entry=old_config_entry,
        original_name="ClimaCell - Daily",
        suggested_object_id="climacell_daily",
        device_id=old_device.id,
    )
    old_entity_hourly = ent_reg.async_get_or_create(
        "weather",
        CC_DOMAIN,
        "v3apikey_80.0_80.0_hourly",
        config_entry=old_config_entry,
        original_name="ClimaCell - Hourly",
        suggested_object_id="climacell_hourly",
        device_id=old_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    old_entity_nowcast = ent_reg.async_get_or_create(
        "weather",
        CC_DOMAIN,
        "v3apikey_80.0_80.0_nowcast",
        config_entry=old_config_entry,
        original_name="ClimaCell - Nowcast",
        suggested_object_id="climacell_nowcast",
        device_id=old_device.id,
    )
    ent_reg.async_update_entity(old_entity_daily.entity_id, name=NEW_NAME)

    # Now let's create a new tomorrowio config entry that is supposedly created from a
    # climacell import and see what happens - we are also changing the API key to ensure
    # that things work as expected
    new_data = API_V3_ENTRY_DATA.copy()
    new_data[CONF_LOCATION] = {
        CONF_LATITUDE: float(new_data.pop(CONF_LATITUDE)),
        CONF_LONGITUDE: float(new_data.pop(CONF_LONGITUDE)),
    }
    new_data[CONF_API_VERSION] = 4
    new_data["old_config_entry_id"] = old_config_entry.entry_id
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=new_data,
        unique_id=_get_unique_id(hass, new_data),
        version=1,
        source=SOURCE_IMPORT,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the old device no longer exists
    assert dev_reg.async_get(old_device.id) is None

    # Check that the new device was created and that it has the correct name
    assert (
        dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id)[
            0
        ].name_by_user
        == NEW_NAME
    )

    # Check that the new entities match the old ones (minus the default name)
    new_entity_daily = ent_reg.async_get(old_entity_daily.entity_id)
    assert new_entity_daily.platform == DOMAIN
    assert new_entity_daily.name == NEW_NAME
    assert new_entity_daily.original_name == "ClimaCell - Daily"
    assert new_entity_daily.device_id != old_device.id
    assert new_entity_daily.unique_id == f"{_get_unique_id(hass, new_data)}_daily"
    assert new_entity_daily.disabled_by is None

    new_entity_hourly = ent_reg.async_get(old_entity_hourly.entity_id)
    assert new_entity_hourly.platform == DOMAIN
    assert new_entity_hourly.name is None
    assert new_entity_hourly.original_name == "ClimaCell - Hourly"
    assert new_entity_hourly.device_id != old_device.id
    assert new_entity_hourly.unique_id == f"{_get_unique_id(hass, new_data)}_hourly"
    assert new_entity_hourly.disabled_by == er.RegistryEntryDisabler.USER

    new_entity_nowcast = ent_reg.async_get(old_entity_nowcast.entity_id)
    assert new_entity_nowcast.platform == DOMAIN
    assert new_entity_nowcast.name is None
    assert new_entity_nowcast.original_name == "ClimaCell - Nowcast"
    assert new_entity_nowcast.device_id != old_device.id
    assert new_entity_nowcast.unique_id == f"{_get_unique_id(hass, new_data)}_nowcast"
    assert new_entity_nowcast.disabled_by is None
