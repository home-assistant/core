"""A helper module for customization."""
import collections
from typing import Any, Dict, List
import fnmatch
import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, split_entity_id
import homeassistant.helpers.config_validation as cv

_OVERWRITE_KEY_FORMAT = '{}.overwrite'
_OVERWRITE_CACHE_KEY_FORMAT = '{}.overwrite_cache'

_CUSTOMIZE_SCHEMA_ENTRY = vol.Schema({
    vol.Required(CONF_ENTITY_ID): vol.All(
        cv.ensure_list_csv, vol.Length(min=1), [vol.Schema(str)], [vol.Lower])
}, extra=vol.ALLOW_EXTRA)


def _convert_old_config(inp: Any) -> List:
    if not isinstance(inp, dict):
        return cv.ensure_list(inp)
    if CONF_ENTITY_ID in inp:
        return [inp]  # sigle entry
    res = []

    inp = vol.Schema({cv.match_all: dict})(inp)
    for key, val in inp.items():
        val = dict(val)
        val[CONF_ENTITY_ID] = key
        res.append(val)
    return res


CUSTOMIZE_SCHEMA = vol.All(_convert_old_config, [_CUSTOMIZE_SCHEMA_ENTRY])


def set_customize(
        hass: HomeAssistant, domain: str, customize: List[Dict]) -> None:
    """Overwrite all current customize settings.

    Async friendly.
    """
    hass.data[_OVERWRITE_KEY_FORMAT.format(domain)] = customize
    hass.data[_OVERWRITE_CACHE_KEY_FORMAT.format(domain)] = {}


def get_overrides(hass: HomeAssistant, domain: str, entity_id: str) -> Dict:
    """Return a dictionary of overrides related to entity_id.

    Whole-domain overrides are of lowest priorities,
    then glob on entity ID, and finally exact entity_id
    matches are of highest priority.

    The lookups are cached.
    """
    cache_key = _OVERWRITE_CACHE_KEY_FORMAT.format(domain)
    if cache_key in hass.data and entity_id in hass.data[cache_key]:
        return hass.data[cache_key][entity_id]
    overwrite_key = _OVERWRITE_KEY_FORMAT.format(domain)
    if overwrite_key not in hass.data:
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

    for rule in hass.data[overwrite_key]:
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
    if cache_key not in hass.data:
        hass.data[cache_key] = {}
    hass.data[cache_key][entity_id] = result
    return result
