"""Implementation of a QS Cloud Interface and related config entries."""
import logging

import asyncio
import voluptuous as vol
import async_timeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_EMAIL, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from .qs import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

QSDOMAIN = '{}.cloud-hub'.format(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + '.{}'
QS_TOKEN_WEBHOOK = 'https://qwikswitch.com/api/v1/keys'
CONF_MASTERKEY = 'masterKey'
CONF_TOKEN = 'token'


class QSCloud():
    """QSCloud class."""

    def __init__(self, hass, name, token=None):
        """Init QScloud class."""
        self.token = token
        self.name = name
        self.hass = hass
        self._aio_session = async_get_clientsession(hass)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self.name, None, hass)

    def unload(self):
        """Remove this QS cloud instance."""
        pass

    async def get_token(self, email, masterkey):
        """Retrieve an access token."""
        _LOGGER.debug('Request token %s, %s***', email, masterkey[:2])
        with async_timeout.timeout(3):
            res = await self._aio_session.post(
                QS_TOKEN_WEBHOOK, data={
                    'email': email,
                    'masterKey': masterkey
                })
            data = (await res.json()) or {}
        self.token = data.get['rw']
        _LOGGER.debug('  got token %s', self.token)
        # {'ok': 1, 'r': 'f10b-56b7-dba4-0475', 'rw': 'ddb3-9f0b-81d2-0475'}


async def async_setup_entry(hass, config_entry, async_add_devices):
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
    return set((slugify(entry.data[CONF_EMAIL])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class QSCloudFlowHandler(data_entry_flow.FlowHandler):
    """Qwikswitch config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    qscloud = None  # type=QSCloud

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].lower()
            name = user_input[CONF_NAME]

            if email in configured_qscloud(self.hass):
                errors['base'] = 'name_exists'
                return

            self.qscloud = QSCloud(self.hass, name)
            try:
                token = self.qscloud.get_token(
                    email, user_input[CONF_MASTERKEY])
            except asyncio.TimeoutError:
                errors['base'] = 'timeout'
                return

            if token is None:
                errors['base'] = 'no_key'
                return

            return self.async_create_entry(
                title=name,
                data={CONF_EMAIL: email, CONF_TOKEN: token},
            )

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_MASTERKEY): str,
                vol.Optional(CONF_NAME, default='QS Cloud'): str,
            }),
            errors=errors,
        )
