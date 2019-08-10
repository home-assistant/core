"""Support for SimpliSafe alarm systems."""
import asyncio
import logging
from datetime import timedelta

from simplipy import API
from simplipy.errors import InvalidCredentialsError, SimplipyError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import verify_domain_control

from .config_flow import configured_instances
from .const import DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"
ATTR_SYSTEM_ID = "system_id"

CONF_ACCOUNTS = "accounts"

DATA_LISTENER = "listener"

SERVICE_REMOVE_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SYSTEM_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string,
    }
)

SERVICE_SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SYSTEM_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL): cv.string,
        vol.Required(ATTR_PIN_VALUE): cv.string,
    }
)

ACCOUNT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ACCOUNTS): vol.All(
                    cv.ensure_list, [ACCOUNT_CONFIG_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_save_refresh_token(hass, config_entry, token):
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TOKEN: token}
    )


async def async_register_base_station(hass, system, config_entry_id):
    """Register a new bridge."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, system.serial)},
        manufacturer="SimpliSafe",
        model=system.version,
        name=system.address,
    )


async def async_setup(hass, config):
    """Set up the SimpliSafe component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    for account in conf[CONF_ACCOUNTS]:
        if account[CONF_USERNAME] in configured_instances(hass):
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: account[CONF_USERNAME],
                    CONF_PASSWORD: account[CONF_PASSWORD],
                    CONF_CODE: account.get(CONF_CODE),
                    CONF_SCAN_INTERVAL: account[CONF_SCAN_INTERVAL],
                },
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up SimpliSafe as config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await API.login_via_token(config_entry.data[CONF_TOKEN], websession)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except SimplipyError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady

    _async_save_refresh_token(hass, config_entry, api.refresh_token)

    systems = await api.get_systems()
    simplisafe = SimpliSafe(hass, config_entry, systems)
    await simplisafe.async_update()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = simplisafe

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, "alarm_control_panel"
        )
    )

    async def refresh(event_time):
        """Refresh data from the SimpliSafe account."""
        await simplisafe.async_update()
        _LOGGER.debug("Updated data for all SimpliSafe systems")
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
    )

    # Register the base station for each system:
    for system in systems.values():
        hass.async_create_task(
            async_register_base_station(hass, system, config_entry.entry_id)
        )

    @_verify_domain_control
    async def remove_pin(call):
        """Remove a PIN."""
        system = systems[int(call.data[ATTR_SYSTEM_ID])]
        await system.remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])

    @_verify_domain_control
    async def set_pin(call):
        """Set a PIN."""
        system = systems[int(call.data[ATTR_SYSTEM_ID])]
        await system.set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])

    for service, method, schema in [
        ("remove_pin", remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        ("set_pin", set_pin, SERVICE_SET_PIN_SCHEMA),
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    return True


async def async_unload_entry(hass, entry):
    """Unload a SimpliSafe config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "alarm_control_panel")

    hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
    remove_listener()

    return True


class SimpliSafe:
    """Define a SimpliSafe API object."""

    def __init__(self, hass, config_entry, systems):
        """Initialize."""
        self._config_entry = config_entry
        self._hass = hass
        self.last_event_data = {}
        self.systems = systems

    async def _update_system(self, system):
        """Update a system."""
        try:
            await system.update()
            latest_event = await system.get_latest_event()
        except SimplipyError as err:
            _LOGGER.error(
                'SimpliSafe error while updating "%s": %s', system.address, err
            )
            return
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error('Unknown error while updating "%s": %s', system.address, err)
            return

        self.last_event_data[system.system_id] = latest_event

        if system.api.refresh_token_dirty:
            _async_save_refresh_token(
                self._hass, self._config_entry, system.api.refresh_token
            )

    async def async_update(self):
        """Get updated data from SimpliSafe."""
        tasks = [self._update_system(system) for system in self.systems.values()]

        await asyncio.gather(*tasks)
