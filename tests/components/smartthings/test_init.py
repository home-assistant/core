"""Tests for the SmartThings component init module."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError, RequestInfo
from pysmartthings import (
    Attribute,
    Capability,
    DeviceResponse,
    DeviceStatus,
    Lifecycle,
    SmartThingsSinkError,
    Subscription,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartthings import EVENT_BUTTON
from homeassistant.components.smartthings.const import (
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_SUBSCRIPTION_ID,
    DOMAIN,
    SCOPES,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration, trigger_update

from tests.common import MockConfigEntry, load_fixture


async def test_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    device_id = devices.get_devices.return_value[0].device_id

    device = device_registry.async_get_device({(DOMAIN, device_id)})

    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_device_not_resetting_area(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device not resetting area."""
    await setup_integration(hass, mock_config_entry)

    device_id = devices.get_devices.return_value[0].device_id

    device = device_registry.async_get_device({(DOMAIN, device_id)})

    assert device.area_id == "theater"

    device_registry.async_update_device(device_id=device.id, area_id=None)
    await hass.async_block_till_done()

    device = device_registry.async_get_device({(DOMAIN, device_id)})

    assert device.area_id is None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device({(DOMAIN, device_id)})
    assert device.area_id is None


@pytest.mark.parametrize("device_fixture", ["button"])
async def test_button_event(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button event."""
    await setup_integration(hass, mock_config_entry)
    events = []

    def capture_event(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen_once(EVENT_BUTTON, capture_event)

    await trigger_update(
        hass,
        devices,
        "c4bdd19f-85d1-4d58-8f9c-e75ac3cf113b",
        Capability.BUTTON,
        Attribute.BUTTON,
        "pushed",
    )

    assert len(events) == 1
    assert events[0] == snapshot


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_create_subscription(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a subscription."""
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data

    await setup_integration(hass, mock_config_entry)

    devices.create_subscription.assert_called_once()

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.subscribe.assert_called_once_with(
        "397678e5-9995-4a39-9d9f-ae6ba310236c",
        "5aaaa925-2be1-4e40-b257-e4ef59083324",
        Subscription.from_json(load_fixture("subscription.json", DOMAIN)),
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_create_subscription_sink_error(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test handling an error when creating a subscription."""
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data

    devices.create_subscription.side_effect = SmartThingsSinkError("Sink error")

    await setup_integration(hass, mock_config_entry)

    devices.subscribe.assert_not_called()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_update_subscription_identifier(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating the subscription identifier."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.new_subscription_id_callback("abc")

    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] == "abc"


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_stale_subscription_id(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating the subscription identifier."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SUBSCRIPTION_ID: "test"},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    devices.delete_subscription.assert_called_once_with("test")


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_remove_subscription_identifier(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing the subscription identifier."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.new_subscription_id_callback(None)

    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_max_connections_handling(
    hass: HomeAssistant, devices: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test handling reaching max connections."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.create_subscription.side_effect = SmartThingsSinkError("Sink error")

    devices.max_connections_reached_callback()

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_unloading(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    devices.delete_subscription.assert_called_once_with(
        "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    # Deleting the subscription automatically deletes the subscription ID
    devices.new_subscription_id_callback(None)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_shutdown(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test shutting down Home Assistant."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    devices.delete_subscription.assert_called_once_with(
        "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    # Deleting the subscription automatically deletes the subscription ID
    devices.new_subscription_id_callback(None)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_removing_stale_devices(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing stale devices."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "aaa-bbb-ccc")},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device({(DOMAIN, "aaa-bbb-ccc")})


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_refreshing_expired_token(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing stale devices."""
    with patch(
        "homeassistant.components.smartthings.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientResponseError(
            request_info=RequestInfo(
                url="http://example.com",
                method="GET",
                headers={},
                real_url="http://example.com",
            ),
            status=400,
            history=(),
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress()) == 1


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_error_refreshing_token(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing stale devices."""
    with patch(
        "homeassistant.components.smartthings.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientResponseError(
            request_info=RequestInfo(
                url="http://example.com",
                method="GET",
                headers={},
                real_url="http://example.com",
            ),
            status=500,
            history=(),
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_via_device(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_smartthings: AsyncMock,
) -> None:
    """Test hub with child devices."""
    mock_smartthings.get_devices.return_value = DeviceResponse.from_json(
        load_fixture("devices/hub.json", DOMAIN)
    ).items
    mock_smartthings.get_device_status.side_effect = [
        DeviceStatus.from_json(
            load_fixture(f"device_status/{fixture}.json", DOMAIN)
        ).components
        for fixture in ("hub", "multipurpose_sensor")
    ]
    await setup_integration(hass, mock_config_entry)

    hub_device = device_registry.async_get_device(
        {(DOMAIN, "074fa784-8be8-4c70-8e22-6f5ed6f81b7e")}
    )
    assert hub_device == snapshot
    assert (
        device_registry.async_get_device(
            {(DOMAIN, "374ba6fa-5a08-4ea2-969c-1fa43d86e21f")}
        ).via_device_id
        == hub_device.id
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_deleted_device_runtime(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test devices that are deleted in runtime."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("climate.ac_office_granit").state == HVACMode.OFF

    for call in devices.add_device_lifecycle_event_listener.call_args_list:
        if call[0][0] == Lifecycle.DELETE:
            call[0][1]("96a5ef74-5832-a84b-f1f7-ca799957065d")
    await hass.async_block_till_done()

    assert hass.states.get("climate.ac_office_granit") is None


@pytest.mark.parametrize(
    (
        "device_fixture",
        "domain",
        "old_unique_id",
        "suggested_object_id",
        "new_unique_id",
    ),
    [
        (
            "multipurpose_sensor",
            BINARY_SENSOR_DOMAIN,
            "7d246592-93db-4d72-a10d-5a51793ece8c.contact",
            "deck_door",
            "7d246592-93db-4d72-a10d-5a51793ece8c_main_contactSensor_contact_contact",
        ),
        (
            "multipurpose_sensor",
            SENSOR_DOMAIN,
            "7d246592-93db-4d72-a10d-5a51793ece8c Y Coordinate",
            "deck_door_y_coordinate",
            "7d246592-93db-4d72-a10d-5a51793ece8c_main_threeAxis_threeAxis_y_coordinate",
        ),
        (
            "da_ac_rac_000001",
            SENSOR_DOMAIN,
            "7d246592-93db-4d72-a10d-ca799957065d.energy_meter",
            "ac_office_granit_energy",
            "7d246592-93db-4d72-a10d-ca799957065d_main_powerConsumptionReport_powerConsumption_energy_meter",
        ),
        (
            "da_ac_rac_000001",
            CLIMATE_DOMAIN,
            "7d246592-93db-4d72-a10d-ca799957065d",
            "ac_office_granit",
            "7d246592-93db-4d72-a10d-ca799957065d_main",
        ),
        (
            "c2c_shade",
            COVER_DOMAIN,
            "571af102-15db-4030-b76b-245a691f74a5",
            "curtain_1a",
            "571af102-15db-4030-b76b-245a691f74a5_main",
        ),
        (
            "generic_fan_3_speed",
            FAN_DOMAIN,
            "6d95a8b7-4ee3-429a-a13a-00ec9354170c",
            "bedroom_fan",
            "6d95a8b7-4ee3-429a-a13a-00ec9354170c_main",
        ),
        (
            "hue_rgbw_color_bulb",
            LIGHT_DOMAIN,
            "cb958955-b015-498c-9e62-fc0c51abd054",
            "standing_light",
            "cb958955-b015-498c-9e62-fc0c51abd054_main",
        ),
        (
            "yale_push_button_deadbolt_lock",
            LOCK_DOMAIN,
            "a9f587c5-5d8b-4273-8907-e7f609af5158",
            "basement_door_lock",
            "a9f587c5-5d8b-4273-8907-e7f609af5158_main",
        ),
        (
            "smart_plug",
            SWITCH_DOMAIN,
            "550a1c72-65a0-4d55-b97b-75168e055398",
            "arlo_beta_basestation",
            "550a1c72-65a0-4d55-b97b-75168e055398_main_switch_switch_switch",
        ),
    ],
)
async def test_entity_unique_id_migration(
    hass: HomeAssistant,
    devices: AsyncMock,
    expires_at: int,
    entity_registry: er.EntityRegistry,
    domain: str,
    old_unique_id: str,
    suggested_object_id: str,
    new_unique_id: str,
) -> None:
    """Test entity unique ID migration."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(SCOPES),
                "access_tier": 0,
                "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
            },
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123",
        },
        version=3,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        old_unique_id,
        config_entry=mock_config_entry,
        suggested_object_id=suggested_object_id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entry.entity_id)

    assert entry.unique_id == new_unique_id


@pytest.mark.parametrize(
    (
        "device_fixture",
        "domain",
        "other_unique_id",
        "old_unique_id",
        "suggested_object_id",
        "new_unique_id",
    ),
    [
        (
            "da_ks_microwave_0101x",
            SENSOR_DOMAIN,
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.ovenJobState",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.machineState",
            "microwave_machine_state",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_machineState_machineState",
        ),
        (
            "da_ks_microwave_0101x",
            SENSOR_DOMAIN,
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_ovenJobState_ovenJobState",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.machineState",
            "microwave_machine_state",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_machineState_machineState",
        ),
        (
            "da_ks_microwave_0101x",
            SENSOR_DOMAIN,
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.ovenJobState",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.completionTime",
            "microwave_completion_time",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_completionTime_completionTime",
        ),
        (
            "da_ks_microwave_0101x",
            SENSOR_DOMAIN,
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_ovenJobState_ovenJobState",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a.completionTime",
            "microwave_completion_time",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a_main_ovenOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_dw_000001",
            SENSOR_DOMAIN,
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.dishwasherJobState",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.machineState",
            "dishwasher_machine_state",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_machineState_machineState",
        ),
        (
            "da_wm_dw_000001",
            SENSOR_DOMAIN,
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_dishwasherJobState_dishwasherJobState",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.machineState",
            "dishwasher_machine_state",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_machineState_machineState",
        ),
        (
            "da_wm_dw_000001",
            SENSOR_DOMAIN,
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.dishwasherJobState",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.completionTime",
            "dishwasher_completion_time",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_dw_000001",
            SENSOR_DOMAIN,
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_dishwasherJobState_dishwasherJobState",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676.completionTime",
            "dishwasher_completion_time",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676_main_dishwasherOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_wd_000001",
            SENSOR_DOMAIN,
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.dryerJobState",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.machineState",
            "dryer_machine_state",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_machineState_machineState",
        ),
        (
            "da_wm_wd_000001",
            SENSOR_DOMAIN,
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_dryerJobState_dryerJobState",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.machineState",
            "dryer_machine_state",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_machineState_machineState",
        ),
        (
            "da_wm_wd_000001",
            SENSOR_DOMAIN,
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.dryerJobState",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.completionTime",
            "dryer_completion_time",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_wd_000001",
            SENSOR_DOMAIN,
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_dryerJobState_dryerJobState",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b.completionTime",
            "dryer_completion_time",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b_main_dryerOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_wm_000001",
            SENSOR_DOMAIN,
            "f984b91d-f250-9d42-3436-33f09a422a47.washerJobState",
            "f984b91d-f250-9d42-3436-33f09a422a47.machineState",
            "washer_machine_state",
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_machineState_machineState",
        ),
        (
            "da_wm_wm_000001",
            SENSOR_DOMAIN,
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_washerJobState_washerJobState",
            "f984b91d-f250-9d42-3436-33f09a422a47.machineState",
            "washer_machine_state",
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_machineState_machineState",
        ),
        (
            "da_wm_wm_000001",
            SENSOR_DOMAIN,
            "f984b91d-f250-9d42-3436-33f09a422a47.washerJobState",
            "f984b91d-f250-9d42-3436-33f09a422a47.completionTime",
            "washer_completion_time",
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_completionTime_completionTime",
        ),
        (
            "da_wm_wm_000001",
            SENSOR_DOMAIN,
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_washerJobState_washerJobState",
            "f984b91d-f250-9d42-3436-33f09a422a47.completionTime",
            "washer_completion_time",
            "f984b91d-f250-9d42-3436-33f09a422a47_main_washerOperatingState_completionTime_completionTime",
        ),
    ],
)
async def test_entity_unique_id_migration_machine_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    expires_at: int,
    entity_registry: er.EntityRegistry,
    domain: str,
    other_unique_id: str,
    old_unique_id: str,
    suggested_object_id: str,
    new_unique_id: str,
) -> None:
    """Test entity unique ID migration."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(SCOPES),
                "access_tier": 0,
                "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
            },
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123",
        },
        version=3,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        other_unique_id,
        config_entry=mock_config_entry,
        suggested_object_id="job_state",
    )
    entry = entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        old_unique_id,
        config_entry=mock_config_entry,
        suggested_object_id=suggested_object_id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entry.entity_id)

    assert entry.unique_id == new_unique_id
