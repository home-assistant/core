"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.const import (CONF_PASSWORD, CONF_NAME)
from homeassistant.ais_dom import ais_global
import time
import voluptuous as vol
import logging

G_WIFI_NETWORKS = []
_LOGGER = logging.getLogger(__name__)


@callback
def configured_connections(hass):
    """Return a set of configured connections instances."""
    return set(entry.data.get(CONF_NAME)
               for entry in hass.config_entries.async_entries(DOMAIN))


def scan_for_wifi(hass, loop) -> []:
    global G_WIFI_NETWORKS
    _LOGGER.info('scan_for_wifi, no of try: ' + str(loop))
    # send scan request to frame
    if loop == 0:
        # reset the current status
        hass.services.call("script", "ais_scan_android_wifi_network")
    # wait
    time.sleep(4)
    # and check the answer
    wifi_networks = hass.states.get('input_select.ais_android_wifi_network')
    G_WIFI_NETWORKS = wifi_networks.attributes['options']
    return G_WIFI_NETWORKS


def connect_to_wifi(ssid, password) -> str:
    import requests
    from homeassistant.components import ais_ai_service as ais_ai_service
    # send add request to frame
    url = ais_ai_service.G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1")
    _LOGGER.info("connect_to_wifi: " + ssid + " pass: " + password)
    try:
        requests.post(url + '/command', json={"WifiConnectToSid": ssid, "WifiNetworkPass": password}, timeout=5)
    except Exception as e:
        _LOGGER.error("connect_to_wifi: " + str(e))


def check_wifi_connection(hass, loop) -> []:
    global G_WIFI_NETWORKS
    _LOGGER.info('check_wifi_connection, no of try: ' + str(loop))
    # wait
    time.sleep(4)
    # and check the answer
    net_info = hass.states.get('sensor.ais_android_current_network_info')
    ssid = net_info.attributes.get('ssid', '')
    return ssid

@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set('ais_wifi_service' for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class AisWiFilowHandler(config_entries.ConfigFlow):
    """AIS WiFi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start - confirmation from user"""
        errors = {}
        if user_input is not None:
            return await self.async_step_one(user_input=None)
        return self.async_show_form(
            step_id='confirm',
            errors=errors,
        )

    async def async_step_one(self, user_input=None):
        """Step one"""
        errors = {}
        if user_input is not None:
            return await self.async_step_search_wifi(user_input=None)
        return self.async_show_form(
            step_id='one',
            errors=errors,
        )

    async def async_step_search_wifi(self, user_input=None):
        """Step - scan the wifi"""
        errors = {}
        for x in range(0, 7):
            result = await self.hass.async_add_executor_job(scan_for_wifi, self.hass, x)
            _LOGGER.info("Szukam sieci WiFi: " + str(result))
            if len(result) > 1:
                return await self.async_step_connect_to_wifi(user_input=None)
            else:
                errors = {'base': 'search_failed'}
        #
        return self.async_show_form(
            step_id='one',
            errors=errors if errors else {},
        )

    async def async_step_connect_to_wifi(self, user_input=None):
        """Step four - connect to wifi"""
        wifi_network = self.hass.states.get('input_select.ais_android_wifi_network')
        networks = wifi_network.attributes['options']
        # remove empty option
        if networks[0] == ais_global.G_EMPTY_OPTION:
            networks.pop(0)

        errors = {}

        if len(networks) == 0:
            errors['general'] = 'wifi_error'
            return self.async_abort(reason='add_failed', description_placeholders={
                'error_info': "Nie udało się znaleść żadnej sieci WiFi o częstotliwości 2.4 Ghz "
                              "do której można by było dodać urządzenie."
            })

        if user_input is None:
            data_schema = vol.Schema({
                vol.Required('networks', default=networks[0]): vol.In(list(networks)),
                vol.Optional(CONF_PASSWORD): str,
            })

        else:
            password = ''
            if CONF_PASSWORD in user_input:
                password = user_input[CONF_PASSWORD]
            data_schema = vol.Schema({
                vol.Required('networks', default=user_input['networks']): vol.In(list(networks)),
                vol.Optional(CONF_PASSWORD, default=password): str,
            })

            # try to connect
            if errors == {}:
                # send a request to frame to add the new device
                network = user_input['networks']
                await self.hass.async_add_executor_job(
                    connect_to_wifi, network.split(';')[0], password)
                # request was correctly send, now check and wait for the answer
                for x in range(0, 7):
                    result = await self.hass.async_add_executor_job(check_wifi_connection, self.hass, x)
                    _LOGGER.info("Spawdzam połączenie z siecią WiFi: " + str(result))
                    if len(result) > 1:
                        # return await self.async_step_connect_to_wifi(user_input=None)
                        return self.async_create_entry(
                            title="Połączenie z WiFi",
                            data=user_input,
                        )
                    else:
                        errors = {'base': 'conn_failed'}

        return self.async_show_form(
            step_id='connect_to_wifi',
            errors=errors if errors else {},
            data_schema=data_schema)
