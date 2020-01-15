"""Support for HomematicIP Cloud devices."""
import logging
from pathlib import Path
from typing import Optional

from homematicip.aio.device import AsyncSwitchMeasuring
from homematicip.aio.group import AsyncHeatingGroup
from homematicip.aio.home import AsyncHome
from homematicip.base.helpers import handle_config
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import comp_entity_ids
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import configured_haps
from .const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from .device import HomematicipGenericDevice  # noqa: F401
from .hap import HomematicipAuth, HomematicipHAP  # noqa: F401

_LOGGER = logging.getLogger(__name__)

ATTR_ACCESSPOINT_ID = "accesspoint_id"
ATTR_ANONYMIZE = "anonymize"
ATTR_CLIMATE_PROFILE_INDEX = "climate_profile_index"
ATTR_CONFIG_OUTPUT_FILE_PREFIX = "config_output_file_prefix"
ATTR_CONFIG_OUTPUT_PATH = "config_output_path"
ATTR_DURATION = "duration"
ATTR_ENDTIME = "endtime"
ATTR_TEMPERATURE = "temperature"

DEFAULT_CONFIG_FILE_PREFIX = "hmip-config"

SERVICE_ACTIVATE_ECO_MODE_WITH_DURATION = "activate_eco_mode_with_duration"
SERVICE_ACTIVATE_ECO_MODE_WITH_PERIOD = "activate_eco_mode_with_period"
SERVICE_ACTIVATE_VACATION = "activate_vacation"
SERVICE_DEACTIVATE_ECO_MODE = "deactivate_eco_mode"
SERVICE_DEACTIVATE_VACATION = "deactivate_vacation"
SERVICE_DUMP_HAP_CONFIG = "dump_hap_config"
SERVICE_RESET_ENERGY_COUNTER = "reset_energy_counter"
SERVICE_SET_ACTIVE_CLIMATE_PROFILE = "set_active_climate_profile"

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

SCHEMA_ACTIVATE_ECO_MODE_WITH_DURATION = vol.Schema(
    {
        vol.Required(ATTR_DURATION): cv.positive_int,
        vol.Optional(ATTR_ACCESSPOINT_ID): vol.All(str, vol.Length(min=24, max=24)),
    }
)

SCHEMA_ACTIVATE_ECO_MODE_WITH_PERIOD = vol.Schema(
    {
        vol.Required(ATTR_ENDTIME): cv.datetime,
        vol.Optional(ATTR_ACCESSPOINT_ID): vol.All(str, vol.Length(min=24, max=24)),
    }
)

SCHEMA_ACTIVATE_VACATION = vol.Schema(
    {
        vol.Required(ATTR_ENDTIME): cv.datetime,
        vol.Required(ATTR_TEMPERATURE, default=18.0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=55)
        ),
        vol.Optional(ATTR_ACCESSPOINT_ID): vol.All(str, vol.Length(min=24, max=24)),
    }
)

SCHEMA_DEACTIVATE_ECO_MODE = vol.Schema(
    {vol.Optional(ATTR_ACCESSPOINT_ID): vol.All(str, vol.Length(min=24, max=24))}
)

SCHEMA_DEACTIVATE_VACATION = vol.Schema(
    {vol.Optional(ATTR_ACCESSPOINT_ID): vol.All(str, vol.Length(min=24, max=24))}
)

SCHEMA_SET_ACTIVE_CLIMATE_PROFILE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): comp_entity_ids,
        vol.Required(ATTR_CLIMATE_PROFILE_INDEX): cv.positive_int,
    }
)

SCHEMA_DUMP_HAP_CONFIG = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_OUTPUT_PATH): cv.string,
        vol.Optional(
            ATTR_CONFIG_OUTPUT_FILE_PREFIX, default=DEFAULT_CONFIG_FILE_PREFIX
        ): cv.string,
        vol.Optional(ATTR_ANONYMIZE, default=True): cv.boolean,
    }
)

SCHEMA_RESET_ENERGY_COUNTER = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): comp_entity_ids}
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the HomematicIP Cloud component."""
    hass.data[DOMAIN] = {}

    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in configured_haps(hass):
            hass.async_add_job(
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

    async def _async_activate_eco_mode_with_duration(service) -> None:
        """Service to activate eco mode with duration."""
        duration = service.data[ATTR_DURATION]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_absence_with_duration(duration)
        else:
            for hap in hass.data[DOMAIN].values():
                await hap.home.activate_absence_with_duration(duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_ECO_MODE_WITH_DURATION,
        _async_activate_eco_mode_with_duration,
        schema=SCHEMA_ACTIVATE_ECO_MODE_WITH_DURATION,
    )

    async def _async_activate_eco_mode_with_period(service) -> None:
        """Service to activate eco mode with period."""
        endtime = service.data[ATTR_ENDTIME]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_absence_with_period(endtime)
        else:
            for hap in hass.data[DOMAIN].values():
                await hap.home.activate_absence_with_period(endtime)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_ECO_MODE_WITH_PERIOD,
        _async_activate_eco_mode_with_period,
        schema=SCHEMA_ACTIVATE_ECO_MODE_WITH_PERIOD,
    )

    async def _async_activate_vacation(service) -> None:
        """Service to activate vacation."""
        endtime = service.data[ATTR_ENDTIME]
        temperature = service.data[ATTR_TEMPERATURE]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_vacation(endtime, temperature)
        else:
            for hap in hass.data[DOMAIN].values():
                await hap.home.activate_vacation(endtime, temperature)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_VACATION,
        _async_activate_vacation,
        schema=SCHEMA_ACTIVATE_VACATION,
    )

    async def _async_deactivate_eco_mode(service) -> None:
        """Service to deactivate eco mode."""
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.deactivate_absence()
        else:
            for hap in hass.data[DOMAIN].values():
                await hap.home.deactivate_absence()

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_ECO_MODE,
        _async_deactivate_eco_mode,
        schema=SCHEMA_DEACTIVATE_ECO_MODE,
    )

    async def _async_deactivate_vacation(service) -> None:
        """Service to deactivate vacation."""
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.deactivate_vacation()
        else:
            for hap in hass.data[DOMAIN].values():
                await hap.home.deactivate_vacation()

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_VACATION,
        _async_deactivate_vacation,
        schema=SCHEMA_DEACTIVATE_VACATION,
    )

    async def _set_active_climate_profile(service) -> None:
        """Service to set the active climate profile."""
        entity_id_list = service.data[ATTR_ENTITY_ID]
        climate_profile_index = service.data[ATTR_CLIMATE_PROFILE_INDEX] - 1

        for hap in hass.data[DOMAIN].values():
            if entity_id_list != "all":
                for entity_id in entity_id_list:
                    group = hap.hmip_device_by_entity_id.get(entity_id)
                    if group and isinstance(group, AsyncHeatingGroup):
                        await group.set_active_profile(climate_profile_index)
            else:
                for group in hap.home.groups:
                    if isinstance(group, AsyncHeatingGroup):
                        await group.set_active_profile(climate_profile_index)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_CLIMATE_PROFILE,
        _set_active_climate_profile,
        schema=SCHEMA_SET_ACTIVE_CLIMATE_PROFILE,
    )

    async def _async_dump_hap_config(service) -> None:
        """Service to dump the configuration of a Homematic IP Access Point."""
        config_path = (
            service.data.get(ATTR_CONFIG_OUTPUT_PATH) or hass.config.config_dir
        )
        config_file_prefix = service.data[ATTR_CONFIG_OUTPUT_FILE_PREFIX]
        anonymize = service.data[ATTR_ANONYMIZE]

        for hap in hass.data[DOMAIN].values():
            hap_sgtin = hap.config_entry.title

            if anonymize:
                hap_sgtin = hap_sgtin[-4:]

            file_name = f"{config_file_prefix}_{hap_sgtin}.json"
            path = Path(config_path)
            config_file = path / file_name

            json_state = await hap.home.download_configuration()
            json_state = handle_config(json_state, anonymize)

            config_file.write_text(json_state, encoding="utf8")

    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_HAP_CONFIG,
        _async_dump_hap_config,
        schema=SCHEMA_DUMP_HAP_CONFIG,
    )

    async def _async_reset_energy_counter(service):
        """Service to reset the energy counter."""
        entity_id_list = service.data[ATTR_ENTITY_ID]

        for hap in hass.data[DOMAIN].values():
            if entity_id_list != "all":
                for entity_id in entity_id_list:
                    device = hap.hmip_device_by_entity_id.get(entity_id)
                    if device and isinstance(device, AsyncSwitchMeasuring):
                        await device.reset_energy_counter()
            else:
                for device in hap.home.devices:
                    if isinstance(device, AsyncSwitchMeasuring):
                        await device.reset_energy_counter()

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_RESET_ENERGY_COUNTER,
        _async_reset_energy_counter,
        schema=SCHEMA_RESET_ENERGY_COUNTER,
    )

    def _get_home(hapid: str) -> Optional[AsyncHome]:
        """Return a HmIP home."""
        hap = hass.data[DOMAIN].get(hapid)
        if hap:
            return hap.home

        _LOGGER.info("No matching access point found for access point id %s", hapid)
        return None

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an access point from a config entry."""
    hap = HomematicipHAP(hass, entry)
    hapid = entry.data[HMIPC_HAPID].replace("-", "").upper()
    hass.data[DOMAIN][hapid] = hap

    if not await hap.async_setup():
        return False

    # Register hap as device in registry.
    device_registry = await dr.async_get_registry(hass)
    home = hap.home
    # Add the HAP name from configuration if set.
    hapname = home.label if not home.name else f"{home.name} {home.label}"
    device_registry.async_get_or_create(
        config_entry_id=home.id,
        identifiers={(DOMAIN, home.id)},
        manufacturer="eQ-3",
        name=hapname,
        model=home.modelType,
        sw_version=home.currentAPVersion,
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.data[HMIPC_HAPID])
    return await hap.async_reset()
