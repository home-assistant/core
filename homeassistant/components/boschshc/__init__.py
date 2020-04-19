"""The Bosch Smart Home Controller integration."""
import asyncio
import logging

from boschshcpy import SHCSession
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    ATTR_NAME,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
    SERVICE_TRIGGER_SCENARIO,
)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME, default="Bosch SHC"): cv.string,
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Required(CONF_SSL_CERTIFICATE): cv.isfile,
                vol.Required(CONF_SSL_KEY): cv.isfile,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    "binary_sensor",
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Bosch SHC component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)

    if not conf:
        return True

    configured_hosts = {
        entry.data.get("ip_address")
        for entry in hass.config_entries.async_entries(DOMAIN)
    }

    if conf[CONF_IP_ADDRESS] in configured_hosts:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Bosch SHC from a config entry."""
    data = entry.data

    _LOGGER.debug("Connecting to Bosch Smart Home Controller API")
    session = await hass.async_add_executor_job(
        SHCSession,
        data[CONF_IP_ADDRESS],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
    )

    shc_info = session.information
    if shc_info.version == "n/a":
        _LOGGER.error("Unable to connect to Bosch Smart Home Controller API")
        return False
    if shc_info.updateState.name == "UPDATE_AVAILABLE":
        _LOGGER.warning("Please check for software updates in the Bosch Smart Home App")

    hass.data[DOMAIN][entry.entry_id] = session

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, data[CONF_IP_ADDRESS])},
        manufacturer="Bosch",
        name=data[CONF_NAME],
        model="SmartHomeController",
        sw_version=shc_info.version,
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def stop_polling(event):
        """Stop polling service."""
        _LOGGER.debug("Stopping polling service of SHC")
        await hass.async_add_executor_job(session.stop_polling)

    async def start_polling(event):
        """Start polling service."""
        _LOGGER.debug("Starting polling service of SHC")
        await hass.async_add_executor_job(session.start_polling)
        session.reset_connection_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, stop_polling
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_polling)

    register_services(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    session: SHCSession = hass.data[DOMAIN][entry.entry_id]
    session.reset_connection_listener()
    _LOGGER.debug("Stopping polling service of SHC")
    await hass.async_add_executor_job(session.stop_polling)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def register_services(hass, entry):
    """Register services for the component."""
    service_scenario_trigger_schema = vol.Schema(
        {
            vol.Required(ATTR_NAME): vol.All(
                cv.string, vol.In(hass.data[DOMAIN][entry.entry_id].scenario_names)
            )
        }
    )

    async def scenario_service_call(call):
        """SHC Scenario service call."""
        name = call.data[ATTR_NAME]
        for scenario in hass.data[DOMAIN][entry.entry_id].scenarios:
            if scenario.name == name:
                _LOGGER.debug("Trigger scenario: %s (%s)", scenario.name, scenario.id)
                hass.async_add_executor_job(scenario.trigger)

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_SCENARIO,
        scenario_service_call,
        service_scenario_trigger_schema,
    )
