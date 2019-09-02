"""Support for HomematicIP Cloud devices."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

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

ATTR_DURATION = "duration"
ATTR_ENDTIME = "endtime"
ATTR_TEMPERATURE = "temperature"
ATTR_ACCESSPOINT_ID = "accesspoint_id"

SERVICE_ACTIVATE_ECO_MODE_WITH_DURATION = "activate_eco_mode_with_duration"
SERVICE_ACTIVATE_ECO_MODE_WITH_PERIOD = "activate_eco_mode_with_period"
SERVICE_ACTIVATE_VACATION = "activate_vacation"
SERVICE_DEACTIVATE_ECO_MODE = "deactivate_eco_mode"
SERVICE_DEACTIVATE_VACATION = "deactivate_vacation"

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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

    async def _async_activate_eco_mode_with_duration(service):
        """Service to activate eco mode with duration."""
        duration = service.data[ATTR_DURATION]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_absence_with_duration(duration)
        else:
            for hapid in hass.data[DOMAIN]:
                home = hass.data[DOMAIN][hapid].home
                await home.activate_absence_with_duration(duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_ECO_MODE_WITH_DURATION,
        _async_activate_eco_mode_with_duration,
        schema=SCHEMA_ACTIVATE_ECO_MODE_WITH_DURATION,
    )

    async def _async_activate_eco_mode_with_period(service):
        """Service to activate eco mode with period."""
        endtime = service.data[ATTR_ENDTIME]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_absence_with_period(endtime)
        else:
            for hapid in hass.data[DOMAIN]:
                home = hass.data[DOMAIN][hapid].home
                await home.activate_absence_with_period(endtime)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_ECO_MODE_WITH_PERIOD,
        _async_activate_eco_mode_with_period,
        schema=SCHEMA_ACTIVATE_ECO_MODE_WITH_PERIOD,
    )

    async def _async_activate_vacation(service):
        """Service to activate vacation."""
        endtime = service.data[ATTR_ENDTIME]
        temperature = service.data[ATTR_TEMPERATURE]
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.activate_vacation(endtime, temperature)
        else:
            for hapid in hass.data[DOMAIN]:
                home = hass.data[DOMAIN][hapid].home
                await home.activate_vacation(endtime, temperature)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_VACATION,
        _async_activate_vacation,
        schema=SCHEMA_ACTIVATE_VACATION,
    )

    async def _async_deactivate_eco_mode(service):
        """Service to deactivate eco mode."""
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.deactivate_absence()
        else:
            for hapid in hass.data[DOMAIN]:
                home = hass.data[DOMAIN][hapid].home
                await home.deactivate_absence()

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_ECO_MODE,
        _async_deactivate_eco_mode,
        schema=SCHEMA_DEACTIVATE_ECO_MODE,
    )

    async def _async_deactivate_vacation(service):
        """Service to deactivate vacation."""
        hapid = service.data.get(ATTR_ACCESSPOINT_ID)

        if hapid:
            home = _get_home(hapid)
            if home:
                await home.deactivate_vacation()
        else:
            for hapid in hass.data[DOMAIN]:
                home = hass.data[DOMAIN][hapid].home
                await home.deactivate_vacation()

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_VACATION,
        _async_deactivate_vacation,
        schema=SCHEMA_DEACTIVATE_VACATION,
    )

    def _get_home(hapid: str):
        """Return a HmIP home."""
        hap = hass.data[DOMAIN][hapid]
        if hap:
            return hap.home
        return None

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
    hapname = home.label if not home.name else "{} {}".format(home.label, home.name)
    device_registry.async_get_or_create(
        config_entry_id=home.id,
        identifiers={(DOMAIN, home.id)},
        manufacturer="eQ-3",
        name=hapname,
        model=home.modelType,
        sw_version=home.currentAPVersion,
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.data[HMIPC_HAPID])
    return await hap.async_reset()
