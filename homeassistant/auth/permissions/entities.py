"""Entity permissions."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

import voluptuous as vol

from .const import POLICY_CONTROL, POLICY_EDIT, POLICY_READ, SUBCAT_ALL
from .models import PermissionLookup
from .types import CategoryType, SubCategoryDict, ValueType
from .util import SubCatLookupType, compile_merged_policy, lookup_all

SINGLE_ENTITY_SCHEMA = vol.Any(
    True,
    False,
    vol.Schema(
        {
            vol.Optional(POLICY_READ): vol.Any(True, False),
            vol.Optional(POLICY_CONTROL): vol.Any(True, False),
            vol.Optional(POLICY_EDIT): vol.Any(True, False),
        }
    ),
)

ENTITY_DOMAINS = "domains"
ENTITY_AREAS = "area_ids"
ENTITY_DEVICE_IDS = "device_ids"
ENTITY_ENTITY_IDS = "entity_ids"

ENTITY_VALUES_SCHEMA = vol.Any(True, False, vol.Schema({str: SINGLE_ENTITY_SCHEMA}))

ENTITY_POLICY_SCHEMA = vol.Any(
    True,
    False,
    vol.Schema(
        {
            vol.Optional(SUBCAT_ALL): SINGLE_ENTITY_SCHEMA,
            vol.Optional(ENTITY_AREAS): ENTITY_VALUES_SCHEMA,
            vol.Optional(ENTITY_DEVICE_IDS): ENTITY_VALUES_SCHEMA,
            vol.Optional(ENTITY_DOMAINS): ENTITY_VALUES_SCHEMA,
            vol.Optional(ENTITY_ENTITY_IDS): ENTITY_VALUES_SCHEMA,
        }
    ),
)


def _lookup_domain(
    perm_lookup: PermissionLookup, domains_dict: SubCategoryDict, entity_id: str
) -> ValueType | None:
    """Look up entity permissions by domain."""
    return domains_dict.get(entity_id.split(".", 1)[0])


def _lookup_area(
    perm_lookup: PermissionLookup, area_dict: SubCategoryDict, entity_id: str
) -> ValueType | None:
    """Look up entity permissions by area."""
    entity_entry = perm_lookup.entity_registry.async_get(entity_id)

    if entity_entry is None:
        return None

    area_id = None

    if entity_entry.device_id is not None:
        device_entry = perm_lookup.device_registry.async_get(entity_entry.device_id)

        if device_entry is not None and device_entry.area_id is not None:
            area_id = device_entry.area_id

    if area_id is None:
        area_id = entity_entry.area_id

    if area_id is None:
        return None

    return area_dict.get(area_id)


def _lookup_device(
    perm_lookup: PermissionLookup, devices_dict: SubCategoryDict, entity_id: str
) -> ValueType | None:
    """Look up entity permissions by device."""
    entity_entry = perm_lookup.entity_registry.async_get(entity_id)

    if entity_entry is None or entity_entry.device_id is None:
        return None

    return devices_dict.get(entity_entry.device_id)


def _lookup_entity_id(
    perm_lookup: PermissionLookup, entities_dict: SubCategoryDict, entity_id: str
) -> ValueType | None:
    """Look up entity permission by entity id."""
    return entities_dict.get(entity_id)


def compile_entities(
    policies: list[CategoryType], perm_lookup: PermissionLookup
) -> Callable[[str, str], bool]:
    """Compile policy into a function that tests policy."""
    subcategories: SubCatLookupType = OrderedDict()
    subcategories[ENTITY_ENTITY_IDS] = _lookup_entity_id
    subcategories[ENTITY_DEVICE_IDS] = _lookup_device
    subcategories[ENTITY_AREAS] = _lookup_area
    subcategories[ENTITY_DOMAINS] = _lookup_domain
    subcategories[SUBCAT_ALL] = lookup_all

    return compile_merged_policy(policies, subcategories, perm_lookup)
