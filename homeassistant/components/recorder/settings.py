"""Recorder settings that are configured from the UI."""

from typing import Any, Final, TypedDict, cast

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entityfilter import INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_AUTO_PURGE,
    CONF_AUTO_REPACK,
    CONF_COMMIT_INTERVAL,
    CONF_DB_MAX_RETRIES,
    CONF_DB_RETRY_WAIT,
    CONF_EVENT_TYPES,
    CONF_PURGE_KEEP_DAYS,
    DEFAULT_COMMIT_INTERVAL,
    DEFAULT_DB_MAX_RETRIES,
    DEFAULT_DB_RETRY_WAIT,
    DOMAIN,
)

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1

YAML_BREAKS_IN_HA_VERSION: Final = "2027.6.0"

DATA_SETTINGS_STORE: HassKey[RecorderSettingsStore] = HassKey(f"{DOMAIN}_settings")


class RecorderSettings(TypedDict):
    """Recorder settings that can be configured from the UI."""

    auto_purge: bool
    auto_repack: bool
    purge_keep_days: int
    commit_interval: int
    db_max_retries: int
    db_retry_wait: int
    include: dict[str, list[str]]
    exclude: dict[str, list[str]]


class _RecorderSettingsStoreData(TypedDict):
    """Data structure for recorder settings storage."""

    settings: RecorderSettings
    yaml_migration_done: bool


EXCLUDE_SCHEMA: Final = INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER.extend(
    {
        probatio.Optional(CONF_EVENT_TYPES, default=[]): probatio.All(
            probatio.EnsureList(), [cv.string]
        )
    }
)

DEFAULT_SETTINGS: Final = RecorderSettings(
    auto_purge=True,
    auto_repack=True,
    purge_keep_days=10,
    commit_interval=DEFAULT_COMMIT_INTERVAL,
    db_max_retries=DEFAULT_DB_MAX_RETRIES,
    db_retry_wait=DEFAULT_DB_RETRY_WAIT,
    include=INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER({}),
    exclude=EXCLUDE_SCHEMA({}),
)

# The settings the recorder only reads when it starts
RESTART_REQUIRED_SETTINGS: Final = (CONF_COMMIT_INTERVAL, CONF_INCLUDE, CONF_EXCLUDE)

SETTINGS_SCHEMA_DICT: Final[dict[Any, Any]] = {
    probatio.Optional(CONF_AUTO_PURGE): cv.boolean,
    probatio.Optional(CONF_AUTO_REPACK): cv.boolean,
    probatio.Optional(CONF_PURGE_KEEP_DAYS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1)
    ),
    probatio.Optional(CONF_COMMIT_INTERVAL): cv.positive_int,
    probatio.Optional(CONF_DB_MAX_RETRIES): cv.positive_int,
    probatio.Optional(CONF_DB_RETRY_WAIT): cv.positive_int,
    probatio.Optional(CONF_INCLUDE): INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    probatio.Optional(CONF_EXCLUDE): EXCLUDE_SCHEMA,
}


def _validate_exclude(exclude: dict[str, list[str]]) -> dict[str, list[str]]:
    """Reject excluding state changed events, which the entity filters handle."""
    if EVENT_STATE_CHANGED in exclude[CONF_EVENT_TYPES]:
        raise probatio.Invalid(
            "State change events cannot be excluded", path=[CONF_EVENT_TYPES]
        )
    return exclude


class RecorderSettingsStore:
    """Persist the recorder settings that are configured from the UI."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store = Store[_RecorderSettingsStoreData](
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
        )
        self.settings = DEFAULT_SETTINGS.copy()
        # The settings the running recorder was started with
        self.started_settings = self.settings
        self.yaml_migration_done = False

    async def async_load(self) -> None:
        """Load the settings from disk."""
        if (data := await self._store.async_load()) is None:
            return
        # Merged with the defaults so settings added later get their default
        self.settings = DEFAULT_SETTINGS | data["settings"]
        self.yaml_migration_done = data["yaml_migration_done"]

    async def async_update(self, changes: dict[str, Any]) -> None:
        """Update and persist settings."""
        self.settings = cast(RecorderSettings, self.settings | changes)
        await self._store.async_save(
            {"settings": self.settings, "yaml_migration_done": self.yaml_migration_done}
        )

    @property
    def restart_required(self) -> bool:
        """Return whether settings the recorder reads at start have changed."""
        return any(
            self.settings[key] != self.started_settings[key]
            for key in RESTART_REQUIRED_SETTINGS
        )


async def async_get_settings(
    hass: HomeAssistant, yaml_settings: dict[str, Any]
) -> RecorderSettings:
    """Load the settings, migrating the YAML settings on first start.

    Once migrated, the YAML settings are ignored and a repair issue asks the
    user to remove them.
    """
    store = hass.data[DATA_SETTINGS_STORE] = RecorderSettingsStore(hass)
    await store.async_load()

    if not store.yaml_migration_done:
        # Nothing is stored until there are settings to keep
        store.yaml_migration_done = True
        if yaml_settings:
            await store.async_update(yaml_settings)
            _async_create_yaml_issue(hass, "deprecated_yaml", yaml_settings)
    elif yaml_settings:
        _async_create_yaml_issue(
            hass, "yaml_still_present_after_migration", yaml_settings
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "deprecated_yaml")
        ir.async_delete_issue(hass, DOMAIN, "yaml_still_present_after_migration")

    store.started_settings = store.settings
    return store.settings


@callback
def async_get_entity_filter_conf(hass: HomeAssistant) -> dict[str, Any]:
    """Return the include and exclude filters the running recorder uses."""
    settings = hass.data[DATA_SETTINGS_STORE].started_settings
    return {CONF_INCLUDE: settings[CONF_INCLUDE], CONF_EXCLUDE: settings[CONF_EXCLUDE]}


@callback
def _async_create_yaml_issue(
    hass: HomeAssistant, issue_id: str, yaml_settings: dict[str, Any]
) -> None:
    """Create a repair issue listing the YAML options to remove."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=YAML_BREAKS_IN_HA_VERSION,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
        translation_placeholders={
            "options": ", ".join(f"`{key}`" for key in sorted(yaml_settings))
        },
    )


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder settings websocket API."""
    websocket_api.async_register_command(hass, ws_get_settings)
    websocket_api.async_register_command(hass, ws_update_settings)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "recorder/settings/get"})
@callback
def ws_get_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the recorder settings."""
    store = hass.data[DATA_SETTINGS_STORE]
    connection.send_result(
        msg["id"],
        {
            "settings": store.settings,
            "default": DEFAULT_SETTINGS,
            "restart_required": store.restart_required,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "recorder/settings/update",
        **SETTINGS_SCHEMA_DICT,
        probatio.Optional(CONF_EXCLUDE): probatio.All(
            EXCLUDE_SCHEMA, _validate_exclude
        ),
    }
)
@websocket_api.async_response
async def ws_update_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update the recorder settings.

    The commit interval and the include and exclude filters are only read
    when the recorder starts, so a change to them is applied on the next
    restart, which ``restart_required`` reports.
    """
    msg_id = msg.pop("id")
    msg.pop("type")
    store = hass.data[DATA_SETTINGS_STORE]
    await store.async_update(msg)
    settings = store.settings

    instance = get_instance(hass)
    instance.auto_purge = settings[CONF_AUTO_PURGE]
    instance.auto_repack = settings[CONF_AUTO_REPACK]
    instance.keep_days = settings[CONF_PURGE_KEEP_DAYS]
    instance.db_max_retries = settings[CONF_DB_MAX_RETRIES]
    instance.db_retry_wait = settings[CONF_DB_RETRY_WAIT]

    connection.send_result(
        msg_id, {"settings": settings, "restart_required": store.restart_required}
    )
