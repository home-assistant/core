"""Implementation of a QS Cloud Interface and related config entries."""
import logging

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_API_KEY, CONF_EMAIL, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from .qs import DOMAIN

_LOGGER = logging.getLogger(__name__)

QSDOMAIN = '{}.cloud-hub'.format(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + '.{}'
QS_TOKEN_WEBHOOK = "https://qwikswitch.com/api/v1/keys"
CONF_MASTERKEY = "masterKey"


class QSCloud():
    """QSCloud class."""

    key = None
    name = None
    entity_id = None

    def __init__(self, hass, config_entry):
        """Init QScloud class."""
        self.key = config_entry[CONF_API_KEY]
        self.name = config_entry.get(CONF_NAME, 'QS Cloud')
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self.name, None, hass)

    def unload(self):
        """Remove this QS cloud instance."""
        pass


async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    qsc = QSCloud(hass, config_entry.data)
    if QSDOMAIN not in hass.data:
        hass.data[QSDOMAIN] = {}
    hass.data[QSDOMAIN][slugify(qsc.name)] = qsc
    # hass.async_add_job(zone.async_update_ha_state())
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    name = slugify(config_entry.data[CONF_NAME])
    qsc = hass.data[QSDOMAIN].pop(name)
    await qsc.unload()
    return True


@callback
def configured_qscloud(hass):
    """Return a set of the configured entries."""
    return set((slugify(entry.data[CONF_NAME])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class QSCloudFlowHandler(data_entry_flow.FlowHandler):
    """Qwikswitch config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            # Try get a token

            if name not in configured_qscloud(self.hass):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors['base'] = 'name_exists'

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default='QS Cloud'): str,
                vol.Required(CONF_EMAIL): vol.Email,
                vol.Required(CONF_MASTERKEY): str,
            }),
            errors=errors,
        )
