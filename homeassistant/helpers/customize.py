"""A helper module for customization."""
import collections
from typing import Dict, List
import fnmatch

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, split_entity_id

_OVERWRITE_KEY = 'overwrite'
_OVERWRITE_CACHE_KEY = 'overwrite_cache'


def set_customize(hass: HomeAssistant, customize: List[Dict]) -> None:
    """Overwrite all current customize settings.

    Async friendly.
    """
    hass.data[_OVERWRITE_KEY] = customize
    hass.data[_OVERWRITE_CACHE_KEY] = {}


def get_overrides(hass: HomeAssistant, entity_id: str) -> Dict:
    """Return a dictionary of overrides related to entity_id.

    Whole-domain overrides are of lowest priorities,
    then glob on entity ID, and finally exact entity_id
    matches are of highest priority.

    The lookups are cached.
    """
    if _OVERWRITE_CACHE_KEY in hass.data and \
            entity_id in hass.data[_OVERWRITE_CACHE_KEY]:
        return hass.data[_OVERWRITE_CACHE_KEY][entity_id]
    if _OVERWRITE_KEY not in hass.data:
        return {}
    domain_result = {}  # type: Dict[str, Any]
    glob_result = {}  # type: Dict[str, Any]
    exact_result = {}  # type: Dict[str, Any]
    domain = split_entity_id(entity_id)[0]

    def clean_entry(entry: Dict) -> Dict:
        """Clean up entity-matching keys."""
        entry.pop(CONF_ENTITY_ID, None)
        return entry

    def deep_update(target: Dict, source: Dict) -> None:
        """Deep update a dictionary."""
        for key, value in source.items():
            if isinstance(value, collections.Mapping):
                updated_value = target.get(key, {})
                # If the new value is map, but the old value is not -
                # overwrite the old value.
                if not isinstance(updated_value, collections.Mapping):
                    updated_value = {}
                deep_update(updated_value, value)
                target[key] = updated_value
            else:
                target[key] = source[key]

    for rule in hass.data[_OVERWRITE_KEY]:
        if CONF_ENTITY_ID in rule:
            entities = rule[CONF_ENTITY_ID]
            if domain in entities:
                deep_update(domain_result, rule)
            if entity_id in entities:
                deep_update(exact_result, rule)
            for entity_id_glob in entities:
                if entity_id_glob == entity_id:
                    continue
                if fnmatch.fnmatchcase(entity_id, entity_id_glob):
                    deep_update(glob_result, rule)
                    break
    result = {}
    deep_update(result, clean_entry(domain_result))
    deep_update(result, clean_entry(glob_result))
    deep_update(result, clean_entry(exact_result))
    if _OVERWRITE_CACHE_KEY not in hass.data:
        hass.data[_OVERWRITE_CACHE_KEY] = {}
    hass.data[_OVERWRITE_CACHE_KEY][entity_id] = result
    return result
