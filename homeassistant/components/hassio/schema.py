"""Schema validation the hassio integration."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_ADDON,
    ATTR_ADDONS,
    ATTR_FOLDERS,
    ATTR_HOMEASSISTANT,
    ATTR_INPUT,
    ATTR_NAME,
    ATTR_PASSWORD,
    ATTR_SNAPSHOT,
    ATTR_WS_EVENT,
)

SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({vol.Required(ATTR_ADDON): cv.slug})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_RESTORE_FULL = vol.Schema(
    {vol.Required(ATTR_SNAPSHOT): cv.slug, vol.Optional(ATTR_PASSWORD): cv.string}
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)

SCHEMA_SNAPSHOT_FULL = vol.Schema(
    {vol.Optional(ATTR_NAME): cv.string, vol.Optional(ATTR_PASSWORD): cv.string}
)

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_FULL.extend(
    {
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)


SCHEMA_WEBSOCKET_EVENT = vol.Schema(
    {vol.Required(ATTR_WS_EVENT): cv.string},
    extra=vol.ALLOW_EXTRA,
)
