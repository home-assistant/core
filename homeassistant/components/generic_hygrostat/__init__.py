"""The generic_hygrostat component."""

import logging

import probatio

from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_devices,
)
from homeassistant.helpers.typing import ConfigType

DOMAIN = "generic_hygrostat"

CONF_HUMIDIFIER = "humidifier"
CONF_SENSOR = "target_sensor"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_TARGET_HUMIDITY = "target_humidity"
CONF_MIN_DUR = "min_cycle_duration"
CONF_DRY_TOLERANCE = "dry_tolerance"
CONF_WET_TOLERANCE = "wet_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_STATE = "initial_state"
CONF_AWAY_HUMIDITY = "away_humidity"
CONF_AWAY_FIXED = "away_fixed"
CONF_STALE_DURATION = "sensor_stale_duration"


DEFAULT_TOLERANCE = 3
DEFAULT_NAME = "Generic Hygrostat"

HYGROSTAT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HUMIDIFIER): cv.entity_id,
        probatio.Required(CONF_SENSOR): cv.entity_id,
        probatio.Optional(CONF_DEVICE_CLASS): probatio.In(
            [HumidifierDeviceClass.HUMIDIFIER, HumidifierDeviceClass.DEHUMIDIFIER]
        ),
        probatio.Optional(CONF_MAX_HUMIDITY): probatio.Coerce(float),
        probatio.Optional(CONF_MIN_DUR): probatio.All(
            cv.time_period, cv.positive_timedelta
        ),
        probatio.Optional(CONF_MIN_HUMIDITY): probatio.Coerce(float),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(
            CONF_DRY_TOLERANCE, default=DEFAULT_TOLERANCE
        ): probatio.Coerce(float),
        probatio.Optional(
            CONF_WET_TOLERANCE, default=DEFAULT_TOLERANCE
        ): probatio.Coerce(float),
        probatio.Optional(CONF_TARGET_HUMIDITY): probatio.Coerce(float),
        probatio.Optional(CONF_KEEP_ALIVE): probatio.All(
            cv.time_period, cv.positive_timedelta
        ),
        probatio.Optional(CONF_INITIAL_STATE): cv.boolean,
        probatio.Optional(CONF_AWAY_HUMIDITY): probatio.Coerce(int),
        probatio.Optional(CONF_AWAY_FIXED): cv.boolean,
        probatio.Optional(CONF_STALE_DURATION): probatio.All(
            cv.time_period, cv.positive_timedelta
        ),
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.All(cv.ensure_list, [HYGROSTAT_SCHEMA])},
    extra=probatio.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Generic Hygrostat component."""
    if DOMAIN not in config:
        return True

    for hygrostat_conf in config[DOMAIN]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.HUMIDIFIER, DOMAIN, hygrostat_conf, config
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    def set_humidifier_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HUMIDIFIER: source_entity_id},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        # We use async_handle_source_entity_changes to track changes to the humidifer,
        # but not the humidity sensor because the generic_hygrostat adds itself to the
        # humidifier's device.
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_humidifier_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_HUMIDIFIER]
            ),
            source_entity_id_or_uuid=entry.options[CONF_HUMIDIFIER],
        )
    )

    async def async_sensor_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Handle entity registry update."""
        data = event.data
        if data["action"] != "update":
            return
        if "entity_id" not in data["changes"]:
            return

        # Entity_id changed, update the config entry
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SENSOR: data["entity_id"]},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.options[CONF_SENSOR], async_sensor_updated
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, (Platform.HUMIDIFIER,))
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            # Remove the generic_hygrostat config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, options[CONF_HUMIDIFIER]
            ):
                async_remove_helper_devices(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (Platform.HUMIDIFIER,)
    )
