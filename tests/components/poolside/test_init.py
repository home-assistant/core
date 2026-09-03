"""Tests for Poolside setup and unload."""

from unittest.mock import patch

from aiopoolside import (
    PoolsideAuthError,
    PoolsideConnectionError,
    PoolsideDevice,
    PoolsideSite,
)
from aiopoolside.const import LAST_TIME_SITE_WAS_LOADED_FIELD, ControlType, GroupKind

from homeassistant.components.poolside.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    TEST_BODY_OF_WATER_UUID,
    TEST_SITE,
    TEST_SITE_UUID,
    FakePoolsideClient,
    make_control,
    make_group,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A successful connect populates runtime_data and forwards platforms."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_poolside_client
    mock_poolside_client.async_connect.assert_awaited_once()
    mock_poolside_client.async_get_control_layout.assert_awaited_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A connection failure raises ConfigEntryNotReady, leaving the entry retryable."""
    mock_poolside_client.async_connect.side_effect = PoolsideConnectionError("nope")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A revoked/unpaired client triggers the reauth flow."""
    mock_poolside_client.async_connect.side_effect = PoolsideAuthError("revoked")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(mock_config_entry.domain)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Unloading the entry disconnects the client."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_poolside_client.async_disconnect.assert_awaited_once()


async def test_stale_entities_removed_when_control_leaves_layout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entities keyed to a control UUID missing from a re-fetched layout are removed."""
    heater = make_control("heater-1", "Heater", ControlType.TEMPERATURE)
    light = make_control("light-1", "Glow", ControlType.LIGHT)
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [heater, light],
    )
    mock_poolside_client.set_status(
        TEST_BODY_OF_WATER_UUID, "HeatingModesSupported", '["SMART", "SOLAR"]'
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.pool_heater") is not None
    assert entity_registry.async_get("select.pool_heater_heating_mode") is not None
    assert entity_registry.async_get("light.pool_glow") is not None

    mock_poolside_client.async_get_control_layout.return_value = (TEST_SITE, [light])
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.pool_heater") is None
    assert entity_registry.async_get("select.pool_heater_heating_mode") is None
    assert entity_registry.async_get("light.pool_glow") is not None
    assert entity_registry.async_get("sensor.pool_temperature") is not None
    assert (
        entity_registry.async_get("sensor.test_residence_controller_mode") is not None
    )


async def test_stale_entity_removed_when_control_changes_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """A control that moves platforms (switch -> fan) sheds its old entity.

    The UUID is still in the layout, so plain existence checks would keep
    the dead switch entity around forever.
    """
    filter_control = make_control(
        "filter-1", "Filter", ControlType.FILTER, SpeedIncrements=[100]
    )
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [filter_control],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.pool_filter") is not None
    assert entity_registry.async_get("fan.pool_filter") is None

    variable_filter = make_control(
        "filter-1", "Filter", ControlType.FILTER, SpeedIncrements=[50, 100]
    )
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [variable_filter],
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.pool_filter") is None
    assert entity_registry.async_get("fan.pool_filter") is not None


async def test_stale_device_removed_when_group_leaves_layout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A group that disappears from the layout takes its device and entities with it."""
    pool_light = make_control("light-1", "Glow", ControlType.LIGHT)
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [pool_light],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "group-pool")}) is not None

    spa = make_group(
        "group-spa",
        "Spa",
        kind=GroupKind.BODY_OF_WATER,
        body_of_water_uuid="body-spa",
    )
    spa_light = make_control("light-2", "Glow", ControlType.LIGHT, group=spa)
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [spa_light],
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "group-pool")}) is None
    assert device_registry.async_get_device({(DOMAIN, "group-spa")}) is not None
    assert entity_registry.async_get("light.pool_glow") is None
    assert entity_registry.async_get("sensor.pool_temperature") is None


async def test_stale_pool_device_removed_when_it_leaves_the_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A pool device missing from a re-fetched list takes its device and sensors."""
    pump = PoolsideDevice(uuid="device-pump-1", name="Pump", device_type="Pump")
    mock_poolside_client.async_get_pool_devices.return_value = [pump]
    mock_poolside_client.set_status(
        "device-pump-1",
        "InformationFields",
        '[{"Name": "Watts", "DisplayName": "Power",'
        ' "DisplayProcessingLogic": "WATTAGE", "FieldTypes": ["INFORMATION"]}]',
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "device-pump-1")}) is not None
    assert entity_registry.async_get("sensor.pump_power") is not None

    mock_poolside_client.async_get_pool_devices.return_value = []
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "device-pump-1")}) is None
    assert entity_registry.async_get("sensor.pump_power") is None


async def test_reloads_when_site_configuration_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A LastTimeSiteWasLoaded change on the site UUID triggers a full reload."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        mock_poolside_client.set_status(
            TEST_SITE_UUID, LAST_TIME_SITE_WAS_LOADED_FIELD, "2026-01-01T00:00:00Z"
        )
        await hass.async_block_till_done()

    mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_no_reload_when_site_uuid_status_is_unrelated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A status push for the site UUID under another field doesn't trigger a reload."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        mock_poolside_client.set_status(TEST_SITE_UUID, "SomeOtherField", "value")
        await hass.async_block_till_done()

    mock_schedule_reload.assert_not_called()


async def test_no_reload_watcher_without_site_uuid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Older firmware reporting no site UUID skips the reload watcher entirely."""
    mock_poolside_client.async_get_control_layout.return_value = (
        PoolsideSite(uuid=None, name=TEST_SITE.name),
        [],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        mock_poolside_client.set_status(
            TEST_SITE_UUID, LAST_TIME_SITE_WAS_LOADED_FIELD, "2026-01-01T00:00:00Z"
        )
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_schedule_reload.assert_not_called()
