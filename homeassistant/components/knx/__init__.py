"""The KNX integration."""

import contextlib
import logging
from pathlib import Path
from typing import Final

import voluptuous as vol
from xknx.exceptions import XKNXException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_EXPOSE,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_LOAD_HOURS,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    DATA_HASS_CONFIG,
    DOMAIN,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_SQLITE,
    KNX_TELEGRAM_DB_PATH_SQLITE,
    KNX_TELEGRAM_DB_RETENTION_DEFAULT,
    KNX_TELEGRAM_LOAD_HOURS_DEFAULT,
    SUPPORTED_PLATFORMS_UI,
    SUPPORTED_PLATFORMS_YAML,
)
from .expose import create_combined_knx_exposure
from .knx_module import KNXModule
from .project import STORAGE_KEY as PROJECT_STORAGE_KEY
from .schema import (
    BinarySensorSchema,
    ButtonSchema,
    ClimateSchema,
    CoverSchema,
    DateSchema,
    DateTimeSchema,
    EventSchema,
    ExposeSchema,
    FanSchema,
    LightSchema,
    NotifySchema,
    NumberSchema,
    SceneSchema,
    SelectSchema,
    SensorSchema,
    SwitchSchema,
    TextSchema,
    TimeSchema,
    WeatherSchema,
)
from .services import async_setup_services
from .storage.config_store import STORAGE_KEY as CONFIG_STORAGE_KEY
from .websocket import register_panel

_KNX_YAML_CONFIG: Final = "knx_yaml_config"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema(
                {
                    **EventSchema.SCHEMA,
                    **ExposeSchema.platform_node(),
                    **BinarySensorSchema.platform_node(),
                    **ButtonSchema.platform_node(),
                    **ClimateSchema.platform_node(),
                    **CoverSchema.platform_node(),
                    **DateSchema.platform_node(),
                    **DateTimeSchema.platform_node(),
                    **FanSchema.platform_node(),
                    **LightSchema.platform_node(),
                    **NotifySchema.platform_node(),
                    **NumberSchema.platform_node(),
                    **SceneSchema.platform_node(),
                    **SelectSchema.platform_node(),
                    **SensorSchema.platform_node(),
                    **SwitchSchema.platform_node(),
                    **TextSchema.platform_node(),
                    **TimeSchema.platform_node(),
                    **WeatherSchema.platform_node(),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start the KNX integration."""
    hass.data[DATA_HASS_CONFIG] = config
    if (conf := config.get(DOMAIN)) is not None:
        hass.data[_KNX_YAML_CONFIG] = dict(conf)

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    # `_KNX_YAML_CONFIG` is only set in async_setup.
    # It's None when reloading the integration or no `knx` key in configuration.yaml
    config = hass.data.pop(_KNX_YAML_CONFIG, None)
    if config is None:
        _conf = await async_integration_yaml_config(hass, DOMAIN)
        if not _conf or DOMAIN not in _conf:
            # generate defaults
            config = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
        else:
            config = _conf[DOMAIN]
    try:
        knx_module = KNXModule(hass, config, entry)
        await knx_module.start()
    except XKNXException as ex:
        raise ConfigEntryNotReady from ex

    hass.data[KNX_MODULE_KEY] = knx_module

    knx_module.ui_time_server_controller.start(
        knx_module.xknx, knx_module.config_store.get_time_server_config()
    )
    knx_module.ui_expose_controller.start(
        hass, knx_module.xknx, knx_module.config_store.get_exposes()
    )
    if CONF_KNX_EXPOSE in config:
        knx_module.yaml_exposures.extend(
            create_combined_knx_exposure(hass, knx_module.xknx, config[CONF_KNX_EXPOSE])
        )

    configured_platforms_yaml = {
        platform for platform in SUPPORTED_PLATFORMS_YAML if platform in config
    }
    await hass.config_entries.async_forward_entry_setups(
        entry,
        {
            # always forward sensor for system entities
            # (telegram counter, etc.)
            Platform.SENSOR,
            # forward all platforms that support UI entity
            # management
            *SUPPORTED_PLATFORMS_UI,
            # forward yaml-only managed platforms on demand
            *configured_platforms_yaml,
        },
    )

    await register_panel(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_data = {**entry.data}
        new_options = {**entry.options}
        new_data.pop("telegram_log_size", None)

        for key in (
            CONF_KNX_STATE_UPDATER,
            CONF_KNX_RATE_LIMIT,
            CONF_KNX_TELEGRAM_DB_LOAD_HOURS,
            CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
        ):
            if key in new_data:
                new_options[key] = new_data.pop(key)

        new_options.setdefault(
            CONF_KNX_TELEGRAM_DB_RETENTION_DAYS, KNX_TELEGRAM_DB_RETENTION_DEFAULT
        )
        new_options.setdefault(
            CONF_KNX_TELEGRAM_DB_LOAD_HOURS, KNX_TELEGRAM_LOAD_HOURS_DEFAULT
        )
        new_options.setdefault(CONF_KNX_STATE_UPDATER, CONF_KNX_DEFAULT_STATE_UPDATER)
        new_options.setdefault(CONF_KNX_RATE_LIMIT, CONF_KNX_DEFAULT_RATE_LIMIT)

        new_options[CONF_KNX_TELEGRAM_DB_BACKEND] = KNX_TELEGRAM_BACKEND_SQLITE

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=2, minor_version=2
        )
        _LOGGER.info("Migration to version 2 successful")

    if entry.version == 2 and entry.minor_version < 2:
        # version 2.2 introduced in 2026.8
        new_options = {**entry.options}
        if CONF_KNX_TELEGRAM_DB_BACKEND not in new_options:
            new_options[CONF_KNX_TELEGRAM_DB_BACKEND] = KNX_TELEGRAM_BACKEND_SQLITE
        hass.config_entries.async_update_entry(
            entry, options=new_options, minor_version=2
        )
        _LOGGER.info("Migration to version 2.2 successful")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the KNX platforms."""
    knx_module = hass.data.get(KNX_MODULE_KEY)
    if not knx_module:
        #  if not loaded directly return
        return True

    for exposure in knx_module.yaml_exposures:
        exposure.async_remove()
    for exposure in knx_module.service_exposures.values():
        exposure.async_remove()
    knx_module.ui_time_server_controller.stop()
    knx_module.ui_expose_controller.stop()

    configured_platforms_yaml = {
        platform
        for platform in SUPPORTED_PLATFORMS_YAML
        if platform in knx_module.config_yaml
    }
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        {
            # always unload system entities
            # (telegram counter, etc.)
            Platform.SENSOR,
            # unload all platforms that support UI entity
            # management
            *SUPPORTED_PLATFORMS_UI,
            # unload yaml-only managed platforms if configured
            *configured_platforms_yaml,
        },
    )
    if unload_ok:
        await knx_module.stop()
        hass.data.pop(DOMAIN)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""

    def remove_files(storage_dir: Path, knxkeys_filename: str | None) -> None:
        """Remove KNX files."""
        if knxkeys_filename is not None:
            with contextlib.suppress(FileNotFoundError):
                (storage_dir / knxkeys_filename).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / CONFIG_STORAGE_KEY).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / PROJECT_STORAGE_KEY).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / KNX_TELEGRAM_DB_PATH_SQLITE).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / f"{KNX_TELEGRAM_DB_PATH_SQLITE}-wal").unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / f"{KNX_TELEGRAM_DB_PATH_SQLITE}-shm").unlink()

        with contextlib.suppress(FileNotFoundError, OSError):
            (storage_dir / DOMAIN).rmdir()

    storage_dir = Path(hass.config.path(STORAGE_DIR))
    knxkeys_filename = entry.data.get(CONF_KNX_KNXKEY_FILENAME)
    await hass.async_add_executor_job(remove_files, storage_dir, knxkeys_filename)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    knx_module = hass.data[KNX_MODULE_KEY]
    if not device_entry.identifiers.isdisjoint(
        knx_module.interface_device.device_info["identifiers"]
    ):
        # can not remove interface device
        return False
    for entity in knx_module.config_store.get_entity_entries():
        if entity.device_id == device_entry.id:
            await knx_module.config_store.delete_entity(entity.entity_id)
    return True
