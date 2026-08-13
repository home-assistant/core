"""Unit tests for entity.py: module helpers and TrueNASEntity base behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homeassistant.components.truenas_ce.const import DOMAIN
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
)
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ._fakes import make_coordinator

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
    assert format_unique_id("TrueNAS", "system_uptime") == "truenas-system_uptime"


def test_format_unique_id_with_reference_slugifies() -> None:
    result = format_unique_id("TrueNAS", "disk_temp", "Disk One!")
    assert result == "truenas-disk_temp-disk_one"


def test_format_device_identifier() -> None:
    assert format_device_identifier("TrueNAS", "nas.local") == "TrueNAS_nas.local"


# ---------------------------
#   _get_composite_container / _extract_composite_ref
# ---------------------------
def test_get_composite_container_non_dict_vals_returns_none() -> None:
    assert _get_composite_container("not-a-dict", "networks") is None


def test_extract_composite_ref_non_dict_item_returns_none() -> None:
    assert (
        _extract_composite_ref(
            "not-a-dict", _REF_DESC, honor_exclude=True, leaf_key="x"
        )
        is None
    )


def test_extract_composite_ref_excluded_item_returns_none() -> None:
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
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_attribute="value"
    )
    assert _skip_keyless_description(desc, {}) is True


def test_skip_keyless_description_false_when_attribute_present() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_attribute="value"
    )
    assert _skip_keyless_description(desc, {"value": 42}) is False


def test_skip_keyless_description_no_attribute_at_all() -> None:
    assert _skip_keyless_description(_STATIC_DESC, {}) is False


# ---------------------------
#   _is_uid_excluded
# ---------------------------
def test_is_uid_excluded_no_data_exclude_configured() -> None:
    assert _is_uid_excluded(_REF_DESC, {"link_state": "DOWN"}) is False


def test_is_uid_excluded_matches() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="p", data_exclude=("link_state", "DOWN")
    )
    assert _is_uid_excluded(desc, {"link_state": "DOWN"}) is True


def test_is_uid_excluded_non_dict_vals() -> None:
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
    coordinator = make_coordinator(
        data={"disk": {"d1": {"guid": "g1"}, "d2": {"guid": "g2"}}}
    )
    entities = _new_referenced_entities(
        coordinator, _REF_DESC, coordinator.data["disk"], _dispatcher(), set()
    )
    assert {e._uid for e in entities} == {"d1", "d2"}


def test_new_referenced_entities_honors_exclude_behavior() -> None:
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
    desc = TrueNASSensorEntityDescription(key="k", name="N", data_path="nonexistent")
    coordinator = make_coordinator(data={})
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert not result


def test_collect_new_entities_skips_app_stats_sensor_descriptions() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k", name="N", data_path="disk", func="TrueNASAppStatsSensor"
    )
    coordinator = make_coordinator(data={"disk": {"d1": {}}})
    result = _collect_new_entities(coordinator, [desc], _dispatcher(), set())
    assert not result


def test_collect_new_entities_keyless_description() -> None:
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
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    result = _collect_new_entities(coordinator, [_REF_DESC], _dispatcher(), set())
    assert len(result) == 1
    assert result[0]._uid == "d1"


def test_append_if_new_skips_already_seen() -> None:
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    entity = _new_referenced_entities(
        coordinator, _REF_DESC, coordinator.data["disk"], _dispatcher(), set()
    )[0]

    new_entities: list[TrueNASEntity] = []
    seen = {entity.unique_id}
    _append_if_new(entity, seen, new_entities)
    assert not new_entities


def test_append_if_new_adds_unseen() -> None:
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
    entity = _make_entity()
    assert entity.name == "Uptime"


def test_name_static_description_no_name() -> None:
    desc = TrueNASEntityDescription(key="uptime", name=None, data_path="system_info")
    entity = _make_entity(description=desc)
    assert entity.name is None


def test_name_referenced_entity_uses_data_name() -> None:
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
    """Descriptions that only set translation_key (no literal `name`) must
    still resolve via platform_translations -- `name` defaults to
    EntityDescription's UNDEFINED sentinel, not a str or None.
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
    entity = _make_entity()
    assert entity.unique_id == "truenas-uptime"


def test_unique_id_referenced_uses_data_reference_value() -> None:
    entity = _make_entity(uid="d1", data={"guid": "g1"}, description=_REF_DESC)
    assert entity.unique_id == "truenas-disk_temp-g1"


def test_unique_id_referenced_falls_back_to_uid_when_reference_missing() -> None:
    entity = _make_entity(uid="d1", data={}, description=_REF_DESC)
    assert entity.unique_id == "truenas-disk_temp-d1"


def test_device_info_system_group() -> None:
    desc = TrueNASEntityDescription(
        key="uptime", name="Uptime", data_path="system_info", ha_group="System"
    )
    entity = _make_entity(description=desc)
    info = entity.device_info
    assert info["name"] == "TrueNAS"
    assert info["model"] == "TrueNAS Mini"
    assert info["configuration_url"] == "http://truenas.local"


def test_device_info_system_group_https_when_wss() -> None:
    desc = TrueNASEntityDescription(
        key="uptime", name="Uptime", data_path="system_info", ha_group="System"
    )
    coordinator = make_coordinator(api_scheme="wss")
    entity = TrueNASEntity(coordinator, desc)
    assert entity.device_info["configuration_url"] == "https://truenas.local"


def test_device_info_non_system_group_uses_via_device_id_when_supported() -> None:
    desc = TrueNASEntityDescription(
        key="disk_temp", name="Temperature", data_path="disk", ha_group="Disks"
    )
    entity = _make_entity(description=desc)
    with patch(
        "homeassistant.components.truenas_ce.entity._supports_via_device_id",
        return_value=True,
    ):
        info = entity.device_info
    assert info["default_name"] == "TrueNAS Disks"
    assert info["via_device_id"] == "test-system-device-id"
    assert "via_device" not in info


def test_device_info_non_system_group_falls_back_to_via_device() -> None:
    """Older HA Core (pre-2026.8) doesn't accept via_device_id -- see
    _supports_via_device_id(); these installs must keep getting the older
    identifiers-tuple form so device linkage isn't silently lost."""
    desc = TrueNASEntityDescription(
        key="disk_temp", name="Temperature", data_path="disk", ha_group="Disks"
    )
    entity = _make_entity(description=desc)
    with patch(
        "homeassistant.components.truenas_ce.entity._supports_via_device_id",
        return_value=False,
    ):
        info = entity.device_info
    assert info["default_name"] == "TrueNAS Disks"
    assert info["via_device"] == ("truenas_ce", "TrueNAS_truenas.local")
    assert "via_device_id" not in info


def test_device_info_data_group_resolves_group_from_data() -> None:
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
    assert info["default_name"] == "TrueNAS tank"


def test_device_info_explicit_connection_and_value() -> None:
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
    assert info["connections"] == {("custom_domain", "fixed-value")}


def test_device_info_connection_value_from_data() -> None:
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
    assert info["connections"] == {("truenas_ce", "TrueNAS_tank")}


def test_extra_state_attributes_includes_attribution_and_listed_fields() -> None:
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
    assert attrs["Model"] == "WD Red"
    assert "attribution" in attrs


def test_raise_unsupported_raises_service_validation_error() -> None:
    entity = _make_entity()
    with pytest.raises(ServiceValidationError) as exc_info:
        entity._raise_unsupported("start")
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unsupported_action"
    assert exc_info.value.translation_placeholders == {
        "action": "start",
        "entity_id": entity.entity_id,
    }


def test_raise_if_api_error_no_error_is_noop() -> None:
    entity = _make_entity()
    entity._raise_if_api_error("start")


def test_raise_if_api_error_raises_when_error_set() -> None:
    coordinator = make_coordinator(api_error="boom")
    entity = _make_entity(coordinator=coordinator)
    with pytest.raises(HomeAssistantError) as exc_info:
        entity._raise_if_api_error("start")
    assert exc_info.value.translation_key == "action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "start",
        "host": coordinator.host,
        "error": "boom",
    }


@pytest.mark.parametrize(
    "method_name",
    ["start", "stop", "restart", "reload", "snapshot", "refresh"],
)
async def test_default_action_stubs_raise_unsupported(method_name: str) -> None:
    entity = _make_entity()
    method = getattr(entity, method_name)
    with pytest.raises(ServiceValidationError):
        await method()


async def test_default_unlock_stub_raises_unsupported() -> None:
    entity = _make_entity()
    with pytest.raises(ServiceValidationError):
        await entity.unlock()


async def test_default_lock_stub_raises_unsupported() -> None:
    entity = _make_entity()
    with pytest.raises(ServiceValidationError):
        await entity.lock()


async def test_default_passphrase_set_stub_raises_unsupported() -> None:
    entity = _make_entity()
    with pytest.raises(ServiceValidationError):
        await entity.passphrase_set("secret")


def test_handle_coordinator_update_refreshes_data_and_calls_super() -> None:
    coordinator = make_coordinator(data={"disk": {"d1": {"guid": "g1"}}})
    entity = TrueNASEntity(coordinator, _REF_DESC, "d1")
    coordinator.data["disk"]["d1"]["guid"] = "g2"

    with patch.object(CoordinatorEntity, "_handle_coordinator_update") as super_update:
        entity._handle_coordinator_update()

    assert entity._data == {"guid": "g2"}
    super_update.assert_called_once()
