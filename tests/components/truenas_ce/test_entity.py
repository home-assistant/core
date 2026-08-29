"""Unit tests for entity.py: module helpers and TrueNASEntity base behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homeassistant.components.truenas_ce.const import CONF_SYSTEM_ID
from homeassistant.components.truenas_ce.entity import (
    TrueNASEntity,
    TrueNASEntityDescription,
    _append_if_new,
    _collect_new_entities,
    _extract_composite_ref,
    _get_composite_container,
    _is_uid_excluded,
    _new_referenced_entities,
    _skip_keyless_description,
    format_device_identifier,
    format_unique_id,
    resolve_entry_identity,
)
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ._fakes import make_config_entry, make_coordinator

_STATIC_DESC = TrueNASEntityDescription(
    key="uptime", name="Uptime", data_path="system_info"
)
_REF_DESC = TrueNASSensorEntityDescription(
    key="disk_temp",
    name="Temperature",
    data_path="disk",
    data_reference="guid",
    func="TrueNASEntity",
)


# ---------------------------
#   format_unique_id / format_device_identifier
# ---------------------------
def test_format_unique_id_without_reference() -> None:
    """A unique id without a reference is just the slugified domain and key."""
    assert format_unique_id("TrueNAS", "system_uptime") == "truenas-system_uptime"


def test_format_unique_id_preserves_reference_case() -> None:
    """Only ``identity`` is lowercased -- the reference keeps its own case."""
    result = format_unique_id("TrueNAS", "disk_temp", "Disk One!")
    assert result == "truenas-disk_temp-Disk One!"


def test_format_unique_id_distinguishes_slash_and_dash_variants() -> None:
    """Distinct dataset references must not collapse to the same unique id."""
    assert format_unique_id("TrueNAS", "dataset", "tank/a-b") != format_unique_id(
        "TrueNAS", "dataset", "tank/a_b"
    )


def test_format_unique_id_distinguishes_case_variants() -> None:
    """Case-sensitive dataset references must not collapse to the same unique id."""
    assert format_unique_id("TrueNAS", "dataset", "tank/Data") != format_unique_id(
        "TrueNAS", "dataset", "tank/data"
    )


def test_format_device_identifier() -> None:
    """A device identifier is the stable per-entry identity, unmodified."""
    assert format_device_identifier("TrueNAS") == "TrueNAS"


# ---------------------------
#   _get_composite_container / _extract_composite_ref
# ---------------------------
def test_get_composite_container_non_dict_vals_returns_none() -> None:
    """A non-dict vals object has no composite container to extract."""
    assert _get_composite_container("not-a-dict", "networks") is None


def test_extract_composite_ref_non_dict_item_returns_none() -> None:
    """A non-dict item cannot yield a composite reference."""
    assert (
        _extract_composite_ref(
            "not-a-dict", _REF_DESC, honor_exclude=True, leaf_key="x"
        )
        is None
    )


def test_extract_composite_ref_excluded_item_returns_none() -> None:
    """An item matching data_exclude is skipped when honor_exclude is True."""
    desc = TrueNASSensorEntityDescription(
        key="net_rx",
        name="RX",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
        data_exclude=("link_state", "DOWN"),
    )
    item = {"interface_name": "eth0", "link_state": "DOWN"}
    ref = _extract_composite_ref(
        item, desc, honor_exclude=True, leaf_key="interface_name"
    )
    assert ref is None


def test_extract_composite_ref_honor_exclude_false_ignores_exclude() -> None:
    """With honor_exclude False, an excluded item's reference is still returned."""
    desc = TrueNASSensorEntityDescription(
        key="net_rx",
        name="RX",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
        data_exclude=("link_state", "DOWN"),
    )
    item = {"interface_name": "eth0", "link_state": "DOWN"}
    ref = _extract_composite_ref(
        item, desc, honor_exclude=False, leaf_key="interface_name"
    )
    assert ref == "eth0"


# ---------------------------
#   _skip_keyless_description
# ---------------------------
def test_skip_keyless_description_true_when_attribute_missing() -> None:
    """A description is skipped when its data_attribute is absent from vals."""
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_attribute="value"
    )
    assert _skip_keyless_description(desc, {}) is True


def test_skip_keyless_description_false_when_attribute_present() -> None:
    """A description is not skipped when its data_attribute is present in vals."""
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_attribute="value"
    )
    assert _skip_keyless_description(desc, {"value": 42}) is False


def test_skip_keyless_description_no_attribute_at_all() -> None:
    """A description without a data_attribute is never skipped as keyless."""
    assert _skip_keyless_description(_STATIC_DESC, {}) is False


# ---------------------------
#   _is_uid_excluded
# ---------------------------
def test_is_uid_excluded_no_data_exclude_configured() -> None:
    """A description with no data_exclude never marks a uid as excluded."""
    assert _is_uid_excluded(_REF_DESC, {"link_state": "DOWN"}) is False


def test_is_uid_excluded_matches() -> None:
    """A uid whose vals match data_exclude is reported as excluded."""
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_exclude=("link_state", "DOWN")
    )
    assert _is_uid_excluded(desc, {"link_state": "DOWN"}) is True


def test_is_uid_excluded_non_dict_vals() -> None:
    """Non-dict vals cannot match data_exclude, so the uid is not excluded."""
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_exclude=("link_state", "DOWN")
    )
    assert _is_uid_excluded(desc, "not-a-dict") is False


# ---------------------------
#   _new_referenced_entities / _collect_new_entities / _append_if_new
# ---------------------------
def _dispatcher() -> dict[str, type[TrueNASEntity]]:
    return {"TrueNASEntity": TrueNASEntity}


def test_new_referenced_entities_creates_one_per_uid() -> None:
    """One entity is created for each uid present in the referenced data."""
    coordinator = make_coordinator(
        data={"disk": {"d1": {"guid": "g1"}, "d2": {"guid": "g2"}}}
    )
    entities = _new_referenced_entities(
        coordinator, _REF_DESC, coordinator.data["disk"], _dispatcher(), set()
    )
    assert {e._uid for e in entities} == {"d1", "d2"}


def test_new_referenced_entities_honors_exclude_behavior() -> None:
    """A uid matching data_exclude is skipped when the behavior option is set."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        data_exclude=("down", True),
        func="TrueNASEntity",
    )
    coordinator = make_coordinator(
        data={
            "disk": {
                "d1": {"guid": "g1", "down": True},
                "d2": {"guid": "g2", "down": False},
            }
        }
    )
    coordinator.config_entry.options = {"behaviors": ["remove_inactive_nic"]}
    entities = _new_referenced_entities(
        coordinator, desc, coordinator.data["disk"], _dispatcher(), set()
    )
    assert {e._uid for e in entities} == {"d2"}


def test_collect_new_entities_skips_missing_data_path() -> None:
    """No entities are collected when the description's data_path is absent."""
    desc = TrueNASSensorEntityDescription(key="k", name="N", data_path="nonexistent")
    coordinator = make_coordinator(data={})
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert not result


def test_collect_new_entities_skips_non_dict_data_path_payload() -> None:
    """A malformed, non-dict coordinator payload for data_path is skipped, not raised."""
    desc = TrueNASSensorEntityDescription(
        key="uptime",
        name="Uptime",
        data_path="system_info",
        data_attribute="hostname",
        func="TrueNASEntity",
    )
    coordinator = make_coordinator(data={"system_info": "not-a-dict"})
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert not result


def test_collect_new_entities_skips_app_stats_sensor_descriptions() -> None:
    """App-stats sensor descriptions are handled elsewhere and skipped here."""
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="disk", func="TrueNASAppStatsSensor"
    )
    coordinator = make_coordinator(data={"disk": {"d1": {}}})
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert not result


def test_collect_new_entities_keyless_description() -> None:
    """A static (non-referenced) description yields a single uid-less entity."""
    desc = TrueNASSensorEntityDescription(
        key="uptime",
        name="Uptime",
        data_path="system_info",
        data_attribute="hostname",
        func="TrueNASEntity",
    )
    coordinator = make_coordinator()
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert len(result) == 1
    assert result[0]._uid is None


def test_collect_new_entities_referenced_description() -> None:
    """A referenced description yields one entity keyed by its uid."""
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    result = _collect_new_entities(coordinator, [_REF_DESC], _dispatcher(), set())
    assert len(result) == 1
    assert result[0]._uid == "d1"


def test_append_if_new_skips_already_seen() -> None:
    """An entity whose unique id is already in seen is not appended again."""
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    entity = _new_referenced_entities(
        coordinator, _REF_DESC, coordinator.data["disk"], _dispatcher(), set()
    )[0]

    new_entities: list[TrueNASEntity] = []
    seen = {entity.unique_id}
    _append_if_new(entity, seen, new_entities)
    assert not new_entities


def test_append_if_new_adds_unseen() -> None:
    """A new entity is appended and its unique id recorded in seen."""
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    entity = _new_referenced_entities(
        coordinator, _REF_DESC, coordinator.data["disk"], _dispatcher(), set()
    )[0]

    new_entities: list[TrueNASEntity] = []
    seen: set[str] = set()
    _append_if_new(entity, seen, new_entities)
    assert new_entities == [entity]
    assert entity.unique_id in seen


# ---------------------------
#   TrueNASEntity
# ---------------------------
def _make_entity(
    *,
    uid: str | None = None,
    data: dict | None = None,
    description: TrueNASEntityDescription | None = None,
    coordinator=None,
) -> TrueNASEntity:
    desc = description or _STATIC_DESC
    coord = coordinator or make_coordinator(
        data={"disk": {uid: (data or {})}} if uid else (data or {})
    )
    return TrueNASEntity(coord, desc, uid)


def test_name_static_description_no_uid() -> None:
    """A static, uid-less entity uses the description's literal name."""
    entity = _make_entity()
    assert entity.name == "Uptime"


def test_name_static_description_no_name() -> None:
    """An entity resolves to no name when the description sets name=None."""
    desc = TrueNASEntityDescription(key="uptime", name=None, data_path="system_info")
    entity = _make_entity(description=desc)
    assert entity.name is None


def test_name_referenced_entity_uses_data_name() -> None:
    """A referenced entity's name is prefixed with the data_name field's value."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        data_name="devname",
    )
    entity = _make_entity(
        uid="d1", data={"devname": "sda", "guid": "g1"}, description=desc
    )
    assert entity.name == "sda Temperature"


def test_name_referenced_entity_falls_back_to_uid() -> None:
    """When data_name's field is missing, the entity's uid prefixes the name."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        data_name="devname",
    )
    entity = _make_entity(uid="d1", data={"guid": "g1"}, description=desc)
    assert entity.name == "d1 Temperature"


def test_name_referenced_entity_no_desc_name() -> None:
    """With no description name, the entity name is just the data_name value."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name=None,
        data_path="disk",
        data_reference="guid",
        data_name="devname",
    )
    entity = _make_entity(
        uid="d1", data={"devname": "sda", "guid": "g1"}, description=desc
    )
    assert entity.name == "sda"


@pytest.mark.parametrize(
    ("platform_translations", "expected_name"),
    [
        pytest.param(
            {"component.truenas_ce.entity.sensor.uptime.name": "Laufzeit"},
            "Laufzeit",
            id="translation_hit",
        ),
        pytest.param({}, "Uptime", id="translation_missing"),
        pytest.param(None, "Uptime", id="no_platform_data"),
    ],
)
def test_name_translation_lookup(
    platform_translations: dict[str, str] | None, expected_name: str
) -> None:
    """The name resolves via platform_translations when available, else falls back."""
    desc = TrueNASEntityDescription(
        key="uptime", name="Uptime", translation_key="uptime", data_path="system_info"
    )
    entity = _make_entity(description=desc)
    if platform_translations is not None:
        entity.platform_data = SimpleNamespace(
            platform_name="truenas_ce",
            domain="sensor",
            platform_translations=platform_translations,
        )
    else:
        entity.platform_data = None
    assert entity.name == expected_name


def test_name_translation_lookup_without_literal_name() -> None:
    """Descriptions that only set translation_key (no literal `name`) must still resolve via platform_translations.

    `name` defaults to EntityDescription's UNDEFINED sentinel, not a str or None.
    """
    desc = TrueNASEntityDescription(
        key="uptime", translation_key="uptime", data_path="system_info"
    )
    entity = _make_entity(description=desc)
    entity.platform_data = SimpleNamespace(
        platform_name="truenas_ce",
        domain="sensor",
        platform_translations={
            "component.truenas_ce.entity.sensor.uptime.name": "Laufzeit"
        },
    )
    assert entity.name == "Laufzeit"


def test_unique_id_static_description() -> None:
    """A static entity's unique id is the domain-prefixed description key."""
    entity = _make_entity()
    assert entity.unique_id == "truenas-uptime"


def test_unique_id_referenced_uses_data_reference_value() -> None:
    """A referenced entity's unique id includes the data_reference field's value."""
    entity = _make_entity(uid="d1", data={"guid": "g1"}, description=_REF_DESC)
    assert entity.unique_id == "truenas-disk_temp-g1"


def test_unique_id_referenced_falls_back_to_uid_when_reference_missing() -> None:
    """When the data_reference field is missing, the uid is used instead."""
    entity = _make_entity(uid="d1", data={}, description=_REF_DESC)
    assert entity.unique_id == "truenas-disk_temp-d1"


def test_device_info_system_group() -> None:
    """The System group's device info exposes the model and configuration URL."""
    desc = TrueNASEntityDescription(
        key="uptime", name="Uptime", data_path="system_info", ha_group="System"
    )
    entity = _make_entity(description=desc)
    info = entity.device_info
    assert info["name"] == "TrueNAS"
    assert info["model"] == "TrueNAS Mini"
    assert info["configuration_url"] == "http://truenas.local"


def test_device_info_system_group_https_when_wss() -> None:
    """A wss:// coordinator connection yields an https:// configuration URL."""
    desc = TrueNASEntityDescription(
        key="uptime", name="Uptime", data_path="system_info", ha_group="System"
    )
    coordinator = make_coordinator(api_scheme="wss")
    entity = TrueNASEntity(coordinator, desc)
    assert entity.device_info["configuration_url"] == "https://truenas.local"


def test_device_info_non_system_group_uses_via_device_id_when_supported() -> None:
    """A non-system group links via via_device_id when HA Core supports it."""
    desc = TrueNASEntityDescription(
        key="disk_temp", name="Temperature", data_path="disk", ha_group="Disks"
    )
    entity = _make_entity(description=desc)
    with patch(
        "homeassistant.components.truenas_ce.entity._supports_via_device_id",
        return_value=True,
    ):
        info = entity.device_info
    assert info["name"] == "TrueNAS Disks"
    assert info["via_device_id"] == "test-system-device-id"
    assert "via_device" not in info


def test_device_info_non_system_group_falls_back_to_via_device() -> None:
    """Older HA Core (pre-2026.8) doesn't accept via_device_id -- see _supports_via_device_id().

    These installs must keep getting the older identifiers-tuple form so
    device linkage isn't silently lost.
    """
    desc = TrueNASEntityDescription(
        key="disk_temp", name="Temperature", data_path="disk", ha_group="Disks"
    )
    entity = _make_entity(description=desc)
    with patch(
        "homeassistant.components.truenas_ce.entity._supports_via_device_id",
        return_value=False,
    ):
        info = entity.device_info
    assert info["name"] == "TrueNAS Disks"
    assert info["via_device"] == ("truenas_ce", "TrueNAS")
    assert "via_device_id" not in info


def test_device_info_data_group_resolves_group_from_data() -> None:
    """A data__ ha_group prefix resolves the group name from the entity's data."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        ha_group="data__pool",
    )
    entity = _make_entity(
        uid="d1", data={"guid": "g1", "pool": "tank"}, description=desc
    )
    info = entity.device_info
    assert info["name"] == "TrueNAS tank"
    assert info["identifiers"] == {("truenas_ce", "TrueNAS_tank")}


def test_device_info_data_group_instance_prefix_prevents_collision() -> None:
    """Two instances resolving the same group must not share a device identifier."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        ha_group="data__pool",
    )
    data = {"disk": {"d1": {"guid": "g1", "pool": "tank"}}}
    entity_a = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(name="TrueNAS-A", entry_id="entry-a"),
        ),
        desc,
        "d1",
    )
    entity_b = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(name="TrueNAS-B", entry_id="entry-b"),
        ),
        desc,
        "d1",
    )
    assert entity_a.device_info["identifiers"] == {("truenas_ce", "entry-a_tank")}
    assert entity_b.device_info["identifiers"] == {("truenas_ce", "entry-b_tank")}


def test_device_info_same_name_different_system_id_prevents_collision() -> None:
    """Two config entries sharing CONF_NAME must still get distinct devices.

    Regression test for #179103's Copilot finding: entities/devices used to
    be namespaced by the user-editable display name (CONF_NAME), so two
    TrueNAS servers with the same name (e.g. both left on the "TrueNAS"
    fallback) would collide. They must now be namespaced by the stable
    per-entry identity (CONF_SYSTEM_ID, falling back to entry_id).
    """
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        ha_group="data__pool",
    )
    data = {"disk": {"d1": {"guid": "g1", "pool": "tank"}}}
    entity_a = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(
                name="TrueNAS",
                entry_id="entry-a",
                data={CONF_SYSTEM_ID: "system-aaa"},
            ),
        ),
        desc,
        "d1",
    )
    entity_b = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(
                name="TrueNAS",
                entry_id="entry-b",
                data={CONF_SYSTEM_ID: "system-bbb"},
            ),
        ),
        desc,
        "d1",
    )
    assert entity_a.device_info["identifiers"] == {("truenas_ce", "system-aaa_tank")}
    assert entity_b.device_info["identifiers"] == {("truenas_ce", "system-bbb_tank")}
    assert entity_a.unique_id != entity_b.unique_id
    # Display name still collides -- that's cosmetic only, not an identity bug.
    assert (
        entity_a.device_info["name"] == entity_b.device_info["name"] == "TrueNAS tank"
    )


def test_device_info_same_name_missing_system_id_falls_back_to_entry_id() -> None:
    """Two entries sharing CONF_NAME with no CONF_SYSTEM_ID still get distinct devices.

    CONF_SYSTEM_ID is only populated when the system.global.id lookup
    succeeded during setup, so both entries falling back to entry_id must
    still avoid a collision.
    """
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        ha_group="data__pool",
    )
    data = {"disk": {"d1": {"guid": "g1", "pool": "tank"}}}
    entity_a = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(name="TrueNAS", entry_id="entry-a"),
        ),
        desc,
        "d1",
    )
    entity_b = TrueNASEntity(
        make_coordinator(
            data=data,
            config_entry=make_config_entry(name="TrueNAS", entry_id="entry-b"),
        ),
        desc,
        "d1",
    )
    assert entity_a.device_info["identifiers"] == {("truenas_ce", "entry-a_tank")}
    assert entity_b.device_info["identifiers"] == {("truenas_ce", "entry-b_tank")}
    assert entity_a.unique_id != entity_b.unique_id


def test_unique_id_same_name_different_system_id_prevents_collision() -> None:
    """Entity unique_ids must be namespaced by identity, not the display name."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp", name="Temperature", data_path="disk", data_reference="guid"
    )
    entity_a = TrueNASEntity(
        make_coordinator(
            data={"disk": {"d1": {"guid": "g1"}}},
            config_entry=make_config_entry(
                name="TrueNAS", data={CONF_SYSTEM_ID: "system-aaa"}
            ),
        ),
        desc,
        "d1",
    )
    entity_b = TrueNASEntity(
        make_coordinator(
            data={"disk": {"d1": {"guid": "g1"}}},
            config_entry=make_config_entry(
                name="TrueNAS", data={CONF_SYSTEM_ID: "system-bbb"}
            ),
        ),
        desc,
        "d1",
    )
    assert entity_a.unique_id == "system-aaa-disk_temp-g1"
    assert entity_b.unique_id == "system-bbb-disk_temp-g1"


def test_resolve_entry_identity_prefers_system_id() -> None:
    """resolve_entry_identity uses CONF_SYSTEM_ID when present."""
    entry = make_config_entry(
        entry_id="entry-1", data={CONF_SYSTEM_ID: "system-guid-123"}
    )
    assert resolve_entry_identity(entry) == "system-guid-123"


def test_resolve_entry_identity_falls_back_to_entry_id_when_missing() -> None:
    """resolve_entry_identity falls back to entry_id when system_id is absent."""
    entry = make_config_entry(entry_id="entry-1")
    assert resolve_entry_identity(entry) == "entry-1"


def test_resolve_entry_identity_falls_back_to_entry_id_when_blank() -> None:
    """resolve_entry_identity falls back to entry_id when system_id is empty."""
    entry = make_config_entry(entry_id="entry-1", data={CONF_SYSTEM_ID: ""})
    assert resolve_entry_identity(entry) == "entry-1"


def test_device_info_explicit_connection_and_value() -> None:
    """An explicit ha_connection and ha_connection_value are used verbatim."""
    desc = TrueNASEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        ha_group="Disks",
        ha_connection="custom_domain",
        ha_connection_value="fixed-value",
    )
    entity = _make_entity(description=desc)
    info = entity.device_info
    assert info["identifiers"] == {("custom_domain", "fixed-value")}


def test_device_info_connection_value_from_data() -> None:
    """A data__ ha_connection_value resolves the connection value from the data."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        ha_group="Disks",
        ha_connection_value="data__pool",
    )
    entity = _make_entity(
        uid="d1", data={"guid": "g1", "pool": "tank"}, description=desc
    )
    info = entity.device_info
    assert info["identifiers"] == {("truenas_ce", "TrueNAS_tank")}


def test_extra_state_attributes_includes_attribution_and_listed_fields() -> None:
    """Extra state attributes include the attribution plus data_attributes_list fields."""
    desc = TrueNASSensorEntityDescription(
        key="disk_temp",
        name="Temperature",
        data_path="disk",
        data_reference="guid",
        data_attributes_list=("model",),
    )
    entity = _make_entity(
        uid="d1", data={"guid": "g1", "model": "WD Red"}, description=desc
    )
    attrs = entity.extra_state_attributes
    assert attrs["model"] == "WD Red"
    assert "attribution" in attrs


def test_handle_coordinator_update_refreshes_data_and_calls_super() -> None:
    """The coordinator-update handler refreshes cached data and calls super()."""
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    entity = TrueNASEntity(coordinator, _REF_DESC, "d1")
    coordinator.data["disk"]["d1"]["guid"] = "g2"

    with patch.object(CoordinatorEntity, "_handle_coordinator_update") as super_update:
        entity._handle_coordinator_update()

    assert entity._data == {"guid": "g2"}
    super_update.assert_called_once()
