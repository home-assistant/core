"""Tests for the HA → Matter name synchronisation feature."""

from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.matter.const import CONF_SYNC_NAMES, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import create_node_from_fixture, setup_integration_with_node_fixture

from tests.common import MockConfigEntry

BASIC_INFO_NODE_LABEL_PATH = create_attribute_path_from_attribute(
    0, clusters.BasicInformation.Attributes.NodeLabel
)


def _matter_devices_for_entry(
    hass: HomeAssistant, entry_id: str
) -> list[dr.DeviceEntry]:
    """Return all device entries linked to the given Matter config entry."""
    return dr.async_entries_for_config_entry(dr.async_get(hass), entry_id)


async def test_rename_does_not_sync_when_option_disabled(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Renaming a device must not push to Matter when sync_names is off."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    matter_client.write_attribute.reset_mock()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = _matter_devices_for_entry(hass, entry.entry_id)[0]

    dr.async_get(hass).async_update_device(device.id, name_by_user="New Name")
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 0


async def test_rename_syncs_root_node_label(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Renaming a non-bridged device writes BasicInformation.NodeLabel."""
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    device = _matter_devices_for_entry(hass, entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, name_by_user="My Light")
    await hass.async_block_till_done()

    matter_client.write_attribute.assert_called_once_with(
        node_id=node.node_id,
        attribute_path=BASIC_INFO_NODE_LABEL_PATH,
        value="My Light",
    )


async def test_rename_truncates_long_label_to_32_bytes(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Names longer than the Matter NodeLabel limit are truncated to 32 bytes."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    long_name = "a" * 50
    device = _matter_devices_for_entry(hass, entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, name_by_user=long_name)
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 1
    sent = matter_client.write_attribute.call_args.kwargs["value"]
    assert sent == "a" * 32


async def test_rename_truncates_multibyte_utf8_label_on_char_boundary(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Truncation never splits a multibyte UTF-8 character."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    # "é" is 2 bytes in UTF-8; 16 × "é" = 32 bytes (fits exactly).
    # Adding one more "é" would require 34 bytes, so it should be dropped.
    multibyte_name = "é" * 17
    device = _matter_devices_for_entry(hass, entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, name_by_user=multibyte_name)
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 1
    sent = matter_client.write_attribute.call_args.kwargs["value"]
    assert sent == "é" * 16
    assert len(sent.encode("utf-8")) <= 32


async def test_rename_syncs_bridged_endpoint_node_label(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Renaming a bridged device writes BridgedDeviceBasicInformation.NodeLabel."""
    node = await setup_integration_with_node_fixture(
        hass, "atios_knx_bridge", matter_client
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    bridged_endpoint_id = next(
        ep.endpoint_id for ep in node.endpoints.values() if ep.is_bridged_device
    )
    bridged_device = next(
        d
        for d in _matter_devices_for_entry(hass, entry.entry_id)
        if any(
            f"-{bridged_endpoint_id}" in identifier[1] for identifier in d.identifiers
        )
    )
    dr.async_get(hass).async_update_device(
        bridged_device.id, name_by_user="Hallway Light"
    )
    await hass.async_block_till_done()

    expected_path = create_attribute_path_from_attribute(
        bridged_endpoint_id,
        clusters.BridgedDeviceBasicInformation.Attributes.NodeLabel,
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=node.node_id,
        attribute_path=expected_path,
        value="Hallway Light",
    )


async def test_enabling_option_backfills_existing_devices(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Saving options with sync_names=True pushes labels for all existing devices."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    matter_client.write_attribute.reset_mock()

    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count >= 1
    assert (
        matter_client.write_attribute.call_args.kwargs["attribute_path"]
        == BASIC_INFO_NODE_LABEL_PATH
    )


async def test_initial_sync_runs_on_setup_when_option_enabled(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """If the option is already enabled, setup performs a one-shot backfill."""
    node = create_node_from_fixture("device_diagnostics")
    matter_client.get_nodes.return_value = [node]
    matter_client.get_node.return_value = node

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://localhost:5580/ws"},
        options={CONF_SYNC_NAMES: True},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert matter_client.write_attribute.call_count >= 1


async def test_clearing_override_falls_back_to_inferred_name(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Clearing the user override pushes the inferred device name to Matter."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()

    device_id = _matter_devices_for_entry(hass, entry.entry_id)[0].id
    dr.async_get(hass).async_update_device(device_id, name_by_user="Override")
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    dr.async_get(hass).async_update_device(device_id, name_by_user=None)
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 1
    pushed = matter_client.write_attribute.call_args.kwargs["value"]
    inferred = dr.async_get(hass).async_get(device_id).name
    assert pushed == inferred
    assert pushed != "Override"
