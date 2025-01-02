"""Unit tests the Hass SWITCH component."""

from aiohttp import ClientSession
from freezegun.api import FrozenDateTimeFactory
from iottycloud.verbs import RESULT, STATUS, STATUS_OFF, STATUS_ON
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import UPDATE_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)

from .conftest import test_ls_one_added, test_ls_one_removed, test_ou_one_added

from tests.common import MockConfigEntry, async_fire_time_changed


async def check_command_ok(
    entity_id: str,
    initial_status: str,
    final_status: str,
    command: str,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_status,
    mock_command_fn,
) -> None:
    """Issue a command."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state.state == initial_status

    mock_get_status.return_value = {RESULT: {STATUS: final_status}}

    await hass.services.async_call(
        SWITCH_DOMAIN,
        command,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_command_fn.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == final_status


async def test_turn_on_light_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled_off,
    mock_command_fn,
) -> None:
    """Issue a turnon command."""

    entity_id = "switch.test_light_switch_0_test_serial_0"

    await check_command_ok(
        entity_id=entity_id,
        initial_status=STATUS_OFF,
        final_status=STATUS_ON,
        command=SERVICE_TURN_ON,
        hass=hass,
        mock_config_entry=mock_config_entry,
        local_oauth_impl=local_oauth_impl,
        mock_get_status=mock_get_status_filled_off,
        mock_command_fn=mock_command_fn,
    )


async def test_turn_on_outlet_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_two_outlets,
    mock_get_status_filled_off,
    mock_command_fn,
) -> None:
    """Issue a turnon command."""

    entity_id = "switch.test_outlet_0_test_serial_ou_0"

    await check_command_ok(
        entity_id=entity_id,
        initial_status=STATUS_OFF,
        final_status=STATUS_ON,
        command=SERVICE_TURN_ON,
        hass=hass,
        mock_config_entry=mock_config_entry,
        local_oauth_impl=local_oauth_impl,
        mock_get_status=mock_get_status_filled_off,
        mock_command_fn=mock_command_fn,
    )


async def test_turn_off_light_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    mock_command_fn,
) -> None:
    """Issue a turnoff command."""

    entity_id = "switch.test_light_switch_0_test_serial_0"

    await check_command_ok(
        entity_id=entity_id,
        initial_status=STATUS_ON,
        final_status=STATUS_OFF,
        command=SERVICE_TURN_OFF,
        hass=hass,
        mock_config_entry=mock_config_entry,
        local_oauth_impl=local_oauth_impl,
        mock_get_status=mock_get_status_filled,
        mock_command_fn=mock_command_fn,
    )


async def test_turn_off_outlet_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_two_outlets,
    mock_get_status_filled,
    mock_command_fn,
) -> None:
    """Issue a turnoff command."""

    entity_id = "switch.test_outlet_0_test_serial_ou_0"

    await check_command_ok(
        entity_id=entity_id,
        initial_status=STATUS_ON,
        final_status=STATUS_OFF,
        command=SERVICE_TURN_OFF,
        hass=hass,
        mock_config_entry=mock_config_entry,
        local_oauth_impl=local_oauth_impl,
        mock_get_status=mock_get_status_filled,
        mock_command_fn=mock_command_fn,
    )


async def test_setup_entry_ok_nodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    mock_get_devices_nodevices,
) -> None:
    """Correctly setup, with no iotty Devices to add to Hass."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.async_entity_ids_count() == 0
    assert hass.states.async_entity_ids() == snapshot


async def test_devices_creaction_ok(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
) -> None:
    """Test iotty switch creation."""

    entity_id = "switch.test_light_switch_0_test_serial_0"

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name="state")

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot(name="entity")

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot(name="device")

    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == snapshot(name="entity-ids")


async def test_devices_deletion_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test iotty switch deletion."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == snapshot

    mock_get_devices_twolightswitches.return_value = test_ls_one_removed

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should have one device
    assert hass.states.async_entity_ids_count() == 1
    assert hass.states.async_entity_ids() == snapshot


async def test_devices_insertion_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test iotty switch insertion."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == snapshot

    mock_get_devices_twolightswitches.return_value = test_ls_one_added

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should have three devices
    assert hass.states.async_entity_ids_count() == 3
    assert hass.states.async_entity_ids() == snapshot


async def test_outlet_insertion_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_two_outlets,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test iotty switch insertion."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == snapshot

    mock_get_devices_two_outlets.return_value = test_ou_one_added

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should have three devices
    assert hass.states.async_entity_ids_count() == 3
    assert hass.states.async_entity_ids() == snapshot


async def test_api_not_ok_entities_stay_the_same_as_before(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test case of incorrect response from iotty API on getting device status."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    entity_ids = hass.states.async_entity_ids()
    assert entity_ids == snapshot

    mock_get_status_filled.return_value = {RESULT: "Not a valid restul"}

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should still have have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == entity_ids


async def test_api_throws_response_entities_stay_the_same_as_before(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test case of incorrect response from iotty API on getting device status."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    entity_ids = hass.states.async_entity_ids()
    assert entity_ids == snapshot

    mock_get_devices_twolightswitches.return_value = test_ls_one_added
    mock_get_status_filled.side_effect = Exception("Something went wrong")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should still have have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == entity_ids
