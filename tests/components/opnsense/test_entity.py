"""Unit tests for homeassistant.components.opnsense.entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.opnsense.const import CONF_DEVICE_UNIQUE_ID, DOMAIN
from homeassistant.components.opnsense.coordinator import OPNsenseDataUpdateCoordinator
from homeassistant.components.opnsense.entity import OPNsenseBaseEntity, OPNsenseEntity
from homeassistant.util import slugify


def test_init_sets_unique_and_name_suffixes(
    make_config_entry, dummy_coordinator
) -> None:
    """Verify unique_id and name suffix handling for base entities."""
    entry = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "dev-123", "url": "http://x"}, title="MyBox"
    )
    coord = dummy_coordinator
    ent = OPNsenseBaseEntity(
        config_entry=entry,
        coordinator=coord,
        unique_id_suffix="suf",
        name_suffix="Name",
    )

    assert hasattr(ent, "unique_id")
    # deterministically compute expected slug from device_unique_id and assert
    device_unique = entry.data.get(CONF_DEVICE_UNIQUE_ID)
    expected_prefix = slugify(device_unique)
    # entity unique id is slugified(device_unique_id) + '_' + suffix
    assert ent.unique_id.startswith(f"{expected_prefix}_")
    assert ent.unique_id.endswith("_suf")
    assert ent.has_entity_name is True
    assert hasattr(ent, "name")
    assert ent.name == "Name"


def test_available_property_toggle(make_config_entry, dummy_coordinator) -> None:
    """Entity available property reflects internal availability flag."""
    entry = make_config_entry()
    coord = dummy_coordinator
    ent = OPNsenseBaseEntity(
        config_entry=entry, coordinator=coord, unique_id_suffix="test"
    )
    assert ent.available is False
    ent._available = True
    assert ent.available is True
    coord.last_update_success = False
    assert ent.available is False


def test_opnsense_device_name_prefers_title_and_fallback_to_state(
    make_config_entry, dummy_coordinator
) -> None:
    """Device name prefers config entry title and falls back to state name."""
    # when title present
    entry = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "dev-123", "url": "http://x"}, title="BoxTitle"
    )
    coord = dummy_coordinator
    ent = OPNsenseBaseEntity(
        config_entry=entry, coordinator=coord, unique_id_suffix="test"
    )
    assert ent.opnsense_device_name == "BoxTitle"

    # when title empty -> falls back to coordinator.data system_info.name
    entry2 = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "dev-123", "url": "http://x"}, title=""
    )
    coord2 = MagicMock(spec=OPNsenseDataUpdateCoordinator)
    coord2.data = {"system_info": {"name": "FromState"}}
    ent2 = OPNsenseBaseEntity(
        config_entry=entry2, coordinator=coord2, unique_id_suffix="test"
    )
    assert ent2.opnsense_device_name == "FromState"


def test_get_opnsense_state_value_nested_lookup(
    make_config_entry, dummy_coordinator
) -> None:
    """Nested state lookup returns deep values or None when missing."""
    entry = make_config_entry()
    coord = dummy_coordinator
    coord.data = {"a": {"b": {"c": 5}}}
    ent = OPNsenseBaseEntity(
        config_entry=entry, coordinator=coord, unique_id_suffix="test"
    )
    assert ent._get_opnsense_state_value("a.b.c") == 5
    assert ent._get_opnsense_state_value("non.existent.path") is None


@pytest.mark.asyncio
async def test_async_added_to_hass_sets_client_and_calls_update(
    make_config_entry, dummy_coordinator
) -> None:
    """async_added_to_hass attaches client and triggers update handler."""
    entry = make_config_entry()
    coord = dummy_coordinator
    # provide a runtime client
    client = object()
    # make_config_entry provides runtime_data; attach a client on it
    entry.runtime_data.opnsense_client = client

    ent = OPNsenseBaseEntity(
        config_entry=entry, coordinator=coord, unique_id_suffix="test"
    )

    # stub the entity update handler to observe it being called
    called = {"count": 0}

    def fake_handle():
        called["count"] += 1

    ent._handle_coordinator_update = fake_handle

    # provide a minimal hass stub so lifecycle behaves more like real HA
    ent.hass = MagicMock()
    # should not raise because runtime_data contains OPNSENSE_CLIENT
    await ent.async_added_to_hass()
    assert ent._client is client
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_async_added_to_hass_missing_client_raises(
    make_config_entry, dummy_coordinator
) -> None:
    """async_added_to_hass raises when runtime client is missing."""
    entry = make_config_entry()
    coord = dummy_coordinator
    # runtime_data has opnsense_client attribute but it's None -> triggers assertion
    entry.runtime_data.opnsense_client = None

    ent = OPNsenseBaseEntity(
        config_entry=entry, coordinator=coord, unique_id_suffix="test"
    )

    # avoid writing HA state (which requires hass) by stubbing the handler
    ent._handle_coordinator_update = lambda: None
    ent.hass = MagicMock()
    with pytest.raises(AssertionError):
        await ent.async_added_to_hass()


def test_device_info_variants(make_config_entry, dummy_coordinator) -> None:
    """Device info reflects identifiers and firmware when present."""
    entry = make_config_entry({CONF_DEVICE_UNIQUE_ID: "dev-123"})
    coord = dummy_coordinator
    # when coordinator.data is None
    coord.data = None
    ent = OPNsenseEntity(config_entry=entry, coordinator=coord, unique_id_suffix="test")
    info = ent.device_info
    assert info["identifiers"] == {(DOMAIN, "dev-123")}
    assert info["sw_version"] is None

    # when firmware present
    coord2 = MagicMock(spec=OPNsenseDataUpdateCoordinator)
    coord2.data = {"host_firmware_version": "1.2.3"}
    ent2 = OPNsenseEntity(
        config_entry=entry, coordinator=coord2, unique_id_suffix="test"
    )
    info2 = ent2.device_info
    assert info2["sw_version"] == "1.2.3"
