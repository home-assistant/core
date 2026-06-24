"""Tests for the HA → Matter name synchronisation feature."""

from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from matter_server.client.exceptions import NotConnected
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.matter.const import (
    CONF_SYNC_NAMES,
    DOMAIN,
    ID_TYPE_DEVICE_ID,
)
from homeassistant.components.matter.helpers import (
    get_device_id,
    get_endpoint_from_device_entry,
)
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
    bridged_suffix = f"-{bridged_endpoint_id}"
    bridged_device = next(
        d
        for d in _matter_devices_for_entry(hass, entry.entry_id)
        if any(identifier[1].endswith(bridged_suffix) for identifier in d.identifiers)
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
    assert any(
        call.kwargs["attribute_path"] == BASIC_INFO_NODE_LABEL_PATH
        for call in matter_client.write_attribute.call_args_list
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


async def test_get_endpoint_from_device_entry_edge_cases(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Endpoint resolution skips gracefully when it cannot find an endpoint."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    real_device = _matter_devices_for_entry(hass, entry.entry_id)[0]

    # A real (non-bridged) device resolves to its backing endpoint.
    assert get_endpoint_from_device_entry(matter_client, real_device) is not None

    # A device without any Matter device-id identifier resolves to None.
    no_identifier = MagicMock(identifiers=set())
    assert get_endpoint_from_device_entry(matter_client, no_identifier) is None

    # A device-id identifier that matches no endpoint resolves to None.
    unknown = MagicMock(identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_does-not-exist")})
    assert get_endpoint_from_device_entry(matter_client, unknown) is None

    # When server info is momentarily unavailable, resolution is skipped.
    matter_client.server_info = None
    assert get_endpoint_from_device_entry(matter_client, real_device) is None


async def test_get_endpoint_returns_compose_parent_for_composed_device(
    matter_client: MagicMock,
) -> None:
    """A composed endpoint resolves to its compose parent (e.g. bridged sub-device)."""
    parent = MagicMock(is_bridged_device=False, endpoint_id=0)
    child = MagicMock(endpoint_id=1)
    child.node = MagicMock(node_id=1)
    child.node.get_compose_parent.return_value = parent
    matter_client.get_nodes.return_value = [MagicMock(endpoints={1: child})]

    device_id = get_device_id(matter_client.server_info, child)
    device = MagicMock(identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{device_id}")})

    assert get_endpoint_from_device_entry(matter_client, device) is parent


async def test_rename_swallows_write_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """A failed NodeLabel write is logged and never escapes the listener."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()
    matter_client.write_attribute.side_effect = NotConnected("server disconnected")

    device = _matter_devices_for_entry(hass, entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, name_by_user="Will Fail")
    await hass.async_block_till_done()

    # The write was attempted; the connection error was swallowed (no raise).
    assert matter_client.write_attribute.call_count == 1


async def test_options_update_with_sync_disabled_skips_backfill(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Saving options with sync disabled does not trigger a backfill."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()

    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: False})
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 0


async def test_rename_skips_when_endpoint_cannot_be_resolved(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """A rename is silently skipped when no Matter endpoint can be resolved."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()
    matter_client.server_info = None

    device = _matter_devices_for_entry(hass, entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, name_by_user="No Endpoint")
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 0


async def test_listener_ignores_unrelated_registry_events(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Creates, non-name updates, and other entries' devices are all ignored."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()
    matter_client.write_attribute.reset_mock()
    device_registry = dr.async_get(hass)

    # A new device in the entry fires a "create" action, not "update".
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "name-sync-extra")},
        name="Extra",
    )
    await hass.async_block_till_done()

    # Updating an unrelated field fires "update" without a name_by_user change.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "name-sync-extra")},
        manufacturer="Acme",
    )
    await hass.async_block_till_done()

    # A renamed device belonging to a different config entry is ignored.
    other_entry = MockConfigEntry(domain="other_domain")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "other-device")},
        name="Other",
    )
    device_registry.async_update_device(other_device.id, name_by_user="Renamed")
    await hass.async_block_till_done()

    assert matter_client.write_attribute.call_count == 0


async def test_backfill_skips_unresolvable_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Backfill skips devices whose Matter endpoint cannot be resolved."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "unresolvable")},
        name="Ghost",
    )
    matter_client.write_attribute.reset_mock()

    hass.config_entries.async_update_entry(entry, options={CONF_SYNC_NAMES: True})
    await hass.async_block_till_done()

    # Real devices were backfilled; the unresolvable one was skipped (no crash).
    assert matter_client.write_attribute.call_count >= 1
