"""Support for HomematicIP Cloud devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from .hap import HomematicIPConfigEntry, HomematicipHAP
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MigrationConfig:
    """Configuration for migrating a single entity class to the new unique_id format."""

    feature_id: str
    channel: int | None = None
    is_group: bool = False


UNIQUE_ID_MIGRATION_MAP: dict[str, _MigrationConfig] = {
    # binary_sensor
    "HomematicipCloudConnectionSensor": _MigrationConfig(
        "cloud_connection", is_group=True
    ),
    "HomematicipAccelerationSensor": _MigrationConfig("acceleration", channel=1),
    "HomematicipTiltVibrationSensor": _MigrationConfig("tilt_vibration", channel=1),
    "HomematicipMultiContactInterface": _MigrationConfig("contact"),
    "HomematicipContactInterface": _MigrationConfig("contact", channel=1),
    "HomematicipShutterContact": _MigrationConfig("shutter_contact", channel=1),
    "HomematicipMotionDetector": _MigrationConfig("motion", channel=1),
    "HomematicipPresenceDetector": _MigrationConfig("presence", channel=1),
    "HomematicipSmokeDetector": _MigrationConfig("smoke", channel=1),
    "HomematicipWaterDetector": _MigrationConfig("water", channel=1),
    "HomematicipStormSensor": _MigrationConfig("storm", channel=1),
    "HomematicipRainSensor": _MigrationConfig("rain", channel=1),
    "HomematicipSunshineSensor": _MigrationConfig("sunshine", channel=1),
    "HomematicipBatterySensor": _MigrationConfig("battery", channel=0),
    "HomematicipPluggableMainsFailureSurveillanceSensor": _MigrationConfig(
        "mains_failure", channel=1
    ),
    "HomematicipSecurityZoneSensorGroup": _MigrationConfig(
        "security_zone", is_group=True
    ),
    "HomematicipSecuritySensorGroup": _MigrationConfig("security", is_group=True),
    "HomematicipFullFlushLockControllerLocked": _MigrationConfig(
        "lock_locked", channel=1
    ),
    "HomematicipFullFlushLockControllerGlassBreak": _MigrationConfig(
        "glass_break", channel=1
    ),
    "HomematicipSmokeDetectorChamberDegraded": _MigrationConfig(
        "chamber_degraded", channel=1
    ),
    # sensor
    "HomematicipAccesspointDutyCycle": _MigrationConfig("duty_cycle", channel=0),
    "HomematicipHeatingThermostat": _MigrationConfig("valve_position", channel=1),
    "HomematicipHumiditySensor": _MigrationConfig("humidity", channel=1),
    "HomematicipTemperatureSensor": _MigrationConfig("temperature", channel=1),
    "HomematicipAbsoluteHumiditySensor": _MigrationConfig(
        "absolute_humidity", channel=1
    ),
    "HomematicipIlluminanceSensor": _MigrationConfig("illuminance", channel=1),
    "HomematicipPowerSensor": _MigrationConfig("power", channel=1),
    "HomematicipEnergySensor": _MigrationConfig("energy", channel=1),
    "HomematicipWindspeedSensor": _MigrationConfig("wind_speed", channel=1),
    "HomematicipTodayRainSensor": _MigrationConfig("today_rain", channel=1),
    "HomematicipPassageDetectorDeltaCounter": _MigrationConfig(
        "passage_counter", channel=1
    ),
    "HomematicipWaterFlowSensor": _MigrationConfig("water_flow"),
    "HomematicipWaterVolumeSensor": _MigrationConfig("water_volume"),
    "HomematicipWaterVolumeSinceOpenSensor": _MigrationConfig(
        "water_volume_since_open"
    ),
    "HomematicipTiltAngleSensor": _MigrationConfig("tilt_angle", channel=1),
    "HomematicipTiltStateSensor": _MigrationConfig("tilt_state", channel=1),
    "HomematicipFloorTerminalBlockMechanicChannelValve": _MigrationConfig(
        "ftb_valve_position"
    ),
    "HomematicpTemperatureExternalSensorCh1": _MigrationConfig(
        "temperature_external_ch1", channel=1
    ),
    "HomematicpTemperatureExternalSensorCh2": _MigrationConfig(
        "temperature_external_ch2", channel=1
    ),
    "HomematicpTemperatureExternalSensorDelta": _MigrationConfig(
        "temperature_external_delta", channel=1
    ),
    "HmipEsiIecPowerConsumption": _MigrationConfig("esi_iec_power", channel=1),
    "HmipEsiIecEnergyCounterHighTariff": _MigrationConfig(
        "esi_iec_energy_high", channel=1
    ),
    "HmipEsiIecEnergyCounterLowTariff": _MigrationConfig(
        "esi_iec_energy_low", channel=1
    ),
    "HmipEsiIecEnergyCounterInputSingleTariff": _MigrationConfig(
        "esi_iec_energy_input", channel=1
    ),
    "HmipEsiGasCurrentGasFlow": _MigrationConfig("esi_gas_flow", channel=1),
    "HmipEsiGasGasVolume": _MigrationConfig("esi_gas_volume", channel=1),
    "HmipEsiLedCurrentPowerConsumption": _MigrationConfig("esi_led_power", channel=1),
    "HmipEsiLedEnergyCounterHighTariff": _MigrationConfig(
        "esi_led_energy_high", channel=1
    ),
    "HomematicipSoilMoistureSensor": _MigrationConfig("soil_moisture", channel=1),
    "HomematicipSoilTemperatureSensor": _MigrationConfig("soil_temperature", channel=1),
    # light
    "HomematicipLight": _MigrationConfig("light", channel=1),
    "HomematicipLightHS": _MigrationConfig("light"),
    "HomematicipLightMeasuring": _MigrationConfig("light", channel=1),
    "HomematicipMultiDimmer": _MigrationConfig("dimmer"),
    "HomematicipDimmer": _MigrationConfig("dimmer", channel=1),
    "HomematicipNotificationLight": _MigrationConfig("notification_light"),
    "HomematicipNotificationLightV2": _MigrationConfig("notification_light"),
    "HomematicipColorLight": _MigrationConfig("color_light", channel=1),
    "HomematicipOpticalSignalLight": _MigrationConfig(
        "optical_signal_light", channel=1
    ),
    "HomematicipCombinationSignallingLight": _MigrationConfig(
        "combination_signalling_light", channel=1
    ),
    # switch
    "HomematicipMultiSwitch": _MigrationConfig("switch"),
    "HomematicipSwitch": _MigrationConfig("switch", channel=1),
    "HomematicipGroupSwitch": _MigrationConfig("switch", is_group=True),
    "HomematicipSwitchMeasuring": _MigrationConfig("switch", channel=1),
    # cover
    "HomematicipBlindModule": _MigrationConfig("blind", channel=1),
    "HomematicipMultiCoverShutter": _MigrationConfig("shutter"),
    "HomematicipCoverShutter": _MigrationConfig("shutter", channel=1),
    "HomematicipMultiCoverSlats": _MigrationConfig("slats"),
    "HomematicipCoverSlats": _MigrationConfig("slats", channel=1),
    "HomematicipGarageDoorModule": _MigrationConfig("garage_door", channel=1),
    "HomematicipCoverShutterGroup": _MigrationConfig("shutter", is_group=True),
    # climate
    "HomematicipHeatingGroup": _MigrationConfig("climate", is_group=True),
    # weather
    "HomematicipWeatherSensor": _MigrationConfig("weather", channel=1),
    "HomematicipWeatherSensorPro": _MigrationConfig("weather", channel=1),
    "HomematicipHomeWeather": _MigrationConfig("home_weather", is_group=True),
    # valve
    "HomematicipWateringValve": _MigrationConfig("watering"),
    # lock
    "HomematicipDoorLockDrive": _MigrationConfig("lock", channel=1),
    # button
    "HomematicipGarageDoorControllerButton": _MigrationConfig(
        "garage_button", channel=1
    ),
    "HomematicipFullFlushLockControllerButton": _MigrationConfig(
        "lock_opener_button", channel=1
    ),
    # event
    "HomematicipDoorBellEvent": _MigrationConfig("doorbell", channel=1),
    # alarm_control_panel
    "HomematicipAlarmControlPanelEntity": _MigrationConfig("alarm", is_group=True),
    # siren
    "HomematicipMP3Siren": _MigrationConfig("siren", channel=1),
}

# Sorted by length descending so longer class names match before shorter ones
# (e.g., "HomematicipSwitchMeasuring" before "HomematicipSwitch")
_SORTED_CLASS_NAMES = sorted(UNIQUE_ID_MIGRATION_MAP, key=len, reverse=True)

_CHANNEL_RE = re.compile(r"^Channel(\d+)_(.+)$")
_NOTIFICATION_LIGHT_RE = re.compile(r"^(Top|Bottom)_(.+)$")

_NOTIFICATION_LIGHT_CHANNEL_MAP = {"Top": 2, "Bottom": 3}


def _migrate_unique_id(old_unique_id: str) -> str | None:
    """Convert an old-format unique_id to the new format.

    Old formats:
      {ClassName}_{device_id}
      {ClassName}_Channel{N}_{device_id}
      {ClassName}_{Top|Bottom}_{device_id}  (NotificationLight only)

    New format:
      {device_id}_{channel}_{feature_id}    (device entities)
      {device_id}_{feature_id}              (group/home entities)
    """
    # Find the matching class name (longest first)
    matched_class: str | None = None
    for class_name in _SORTED_CLASS_NAMES:
        prefix = class_name + "_"
        if old_unique_id.startswith(prefix):
            matched_class = class_name
            break

    if matched_class is None:
        return None

    config = UNIQUE_ID_MIGRATION_MAP[matched_class]
    remainder = old_unique_id[len(matched_class) + 1 :]

    # Parse remainder to extract channel and device_id
    channel: int | None = None
    device_id: str

    # Check for Channel{N}_{rest} pattern
    channel_match = _CHANNEL_RE.match(remainder)
    if channel_match:
        channel = int(channel_match.group(1))
        device_id = channel_match.group(2)
    elif matched_class in (
        "HomematicipNotificationLight",
        "HomematicipNotificationLightV2",
    ):
        # Check for Top/Bottom pattern
        notif_match = _NOTIFICATION_LIGHT_RE.match(remainder)
        if notif_match:
            channel = _NOTIFICATION_LIGHT_CHANNEL_MAP[notif_match.group(1)]
            device_id = notif_match.group(2)
        else:
            device_id = remainder
            channel = config.channel
    else:
        device_id = remainder
        channel = config.channel

    # Build new unique_id
    if config.is_group:
        return f"{device_id}_{config.feature_id}"

    if channel is not None:
        return f"{device_id}_{channel}_{config.feature_id}"

    _LOGGER.warning(
        "Cannot determine channel for unique_id: %s",
        old_unique_id,
    )
    return None


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=""): vol.Any(cv.string),
                        vol.Required(CONF_ACCESSPOINT): cv.string,
                        vol.Required(CONF_AUTHTOKEN): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Migrate the config entry from version 1 to version 2."""
    if config_entry.version > 2:
        return False

    if config_entry.version == 1:
        _LOGGER.debug("Migrating HomematicIP Cloud config entry to version 2")

        # Remove obsolete entities before the bulk unique_id rewrite.
        # After rewrite, old-format patterns would no longer be matchable.
        # HomematicipAccesspointStatus* entities are always obsolete (removed
        # in firmware 2.2.12+). HomematicipBatterySensor_{hapid} entities for
        # access points are also obsolete. Those legacy access point battery
        # entities do not belong to a device registry device, unlike real
        # device battery sensors, so we can safely remove them before rewrite.
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entry in entries:
            if entry.unique_id.startswith("HomematicipAccesspointStatus"):
                _LOGGER.debug(
                    "Removing obsolete access point status entity: %s",
                    entry.entity_id,
                )
                entity_registry.async_remove(entry.entity_id)
                continue

            if (
                entry.unique_id.startswith("HomematicipBatterySensor_")
                and entry.device_id is None
            ):
                _LOGGER.debug(
                    "Removing obsolete access point battery entity: %s",
                    entry.entity_id,
                )
                entity_registry.async_remove(entry.entity_id)

        @callback
        def _update_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            new_unique_id = _migrate_unique_id(entity_entry.unique_id)
            if new_unique_id is None:
                # Some entities (e.g. HmipSmokeDetectorSensor) already use
                # stable non-class-name unique_ids and don't need migration.
                # Only warn if the ID looks like an old class-name format.
                if any(
                    entity_entry.unique_id.startswith(cls + "_")
                    for cls in _SORTED_CLASS_NAMES
                ):
                    _LOGGER.warning(
                        "Could not migrate unique_id for %s: %s",
                        entity_entry.entity_id,
                        entity_entry.unique_id,
                    )
                else:
                    _LOGGER.debug(
                        "Skipping unique_id %s (already stable format)",
                        entity_entry.unique_id,
                    )
                return None
            _LOGGER.debug(
                "Migrating %s: %s -> %s",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, config_entry.entry_id, _update_unique_id)

        hass.config_entries.async_update_entry(config_entry, version=2)
        _LOGGER.info("Migration to version 2 successful")

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomematicIP Cloud component."""
    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in {
            entry.data[HMIPC_HAPID]
            for entry in hass.config_entries.async_entries(DOMAIN)
        }:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={
                        HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                        HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                        HMIPC_NAME: conf[CONF_NAME],
                    },
                )
            )

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomematicIPConfigEntry) -> bool:
    """Set up an access point from a config entry."""

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if entry.unique_id is None:
        new_data = dict(entry.data)

        hass.config_entries.async_update_entry(
            entry, unique_id=new_data[HMIPC_HAPID], data=new_data
        )

    hap = HomematicipHAP(hass, entry)

    entry.runtime_data = hap
    if not await hap.async_setup():
        return False

    _async_remove_obsolete_entities(hass, entry, hap)

    # Register on HA stop event to gracefully shutdown HomematicIP Cloud connection
    hap.reset_connection_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, hap.shutdown
    )

    # Register hap as device in registry.
    device_registry = dr.async_get(hass)

    home = hap.home
    hapname = home.label if home.label != entry.unique_id else f"Home-{home.label}"

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, home.id)},
        manufacturer="eQ-3",
        # Add the name from config entry.
        name=hapname,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomematicIPConfigEntry
) -> bool:
    """Unload a config entry."""
    hap = entry.runtime_data
    assert hap.reset_connection_listener is not None
    hap.reset_connection_listener()

    return await hap.async_reset()


@callback
def _async_remove_obsolete_entities(
    hass: HomeAssistant, entry: HomematicIPConfigEntry, hap: HomematicipHAP
):
    """Remove obsolete entities from entity registry."""

    if hap.home.currentAPVersion < "2.2.12":
        return

    entity_registry = er.async_get(hass)
    er_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for er_entry in er_entries:
        if er_entry.unique_id.startswith("HomematicipAccesspointStatus"):
            entity_registry.async_remove(er_entry.entity_id)
            continue

        # For v2+ config entries, battery sensor cleanup already happened
        # during migration in async_migrate_entry. This is a safety net for
        # any edge case where the migration didn't run.
        for hapid in hap.home.accessPointUpdateStates:
            if er_entry.unique_id == f"HomematicipBatterySensor_{hapid}":
                entity_registry.async_remove(er_entry.entity_id)
