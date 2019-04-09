"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.const import (CONF_NAME, CONF_PASSWORD)
import voluptuous as vol
import logging
G_AUTH_URL = None
G_IOT_DEV_TO_ADD = []
_LOGGER = logging.getLogger(__name__)


def setUrl(url):
    global G_AUTH_URL
    G_AUTH_URL = url


def scan_for_new_device(hass, loop) -> []:
    global G_IOT_DEV_TO_ADD
    import time
    _LOGGER.info('scan_for_new_device, try: ' + str(loop))
    # send scan request to frame
    if loop == 0:
        hass.services.call("script", "ais_scan_iot_devices_in_network")
    # wait
    time.sleep(3)
    # and check the answer
    iot_dev = hass.states.get('input_select.ais_iot_devices_in_network')
    G_IOT_DEV_TO_ADD = iot_dev.attributes['options']
    return G_IOT_DEV_TO_ADD


def add_new_device(hass, loop, device, name, network, password, secure_android_id) -> str:
    import time
    import requests
    from homeassistant.components import ais_ai_service as ais_ai_service
    _LOGGER.info('loop: ' + str(loop))
    # send add request to frame
    if loop == 0:
        url = ais_ai_service.G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1")
        try:
            requests.post(
                url + '/command',
                json={"WifiConnectTheDevice": device, "ip": "127.0.0.1", "WifiNetworkPass": password,
                      "WifiNetworkSsid": network, "IotName": name, "bsssid": network,
                      "secureAndroidId": secure_android_id},
                timeout=2)
        except Exception as e:
            return 'nok ' + str(e)
        time.sleep(5)
    else:
        # wait
        time.sleep(3)
    # and check the answer
    if 'ok' == 'ok1':
        return 'ok'
    else:
        return 'nok'


@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set('spotify' for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class AisDomDeviceFlowHandler(config_entries.ConfigFlow):
    """Spotify config flow."""

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
        """Step one - plug in the device to power"""
        errors = {}
        if user_input is not None:
            return await self.async_step_two(user_input=None)
        return self.async_show_form(
            step_id='one',
            errors=errors,
        )

    async def async_step_two(self, user_input=None):
        """Step two - paring mode"""
        errors = {}
        if user_input is not None:
            return await self.async_step_search_iot(user_input=None)
        return self.async_show_form(
            step_id='two',
            errors=errors,
        )

    async def async_step_search_iot(self, user_input=None):
        """Step three - search the new device in network"""
        errors = {}
        for x in range(0, 5):
            result = await self.hass.async_add_executor_job(scan_for_new_device, self.hass, x)
            _LOGGER.info(str(result))
            if len(result) > 1:
                return await self.async_step_add_device(user_input=None)
            else:
                errors = {'base': 'search_failed'}
        #
        return self.async_show_form(
            step_id='two',
            errors=errors if errors else {},
        )

    async def async_step_add_device(self, user_input=None):
        """Step four - add new device"""
        from homeassistant.ais_dom import ais_global

        wifi_network = self.hass.states.get('input_select.ais_android_wifi_network')
        networks = wifi_network.attributes['options']
        # TODO ask for current network connection
        # /command_sync currWifiSsid
        curr_network = ["xxx (Twoje aktualne połączenie WiFi)"]
        networks = curr_network + networks

        # TODO ask for current network password
        # /command_sync currWifiPass
        curr_pass = "123456789"

        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default="Nowe inteligentne gniazdo"): str,
            vol.Required('networks', default=networks[0]): vol.In(list(networks)),
            vol.Required(CONF_PASSWORD, default=curr_pass): str,
        })
        errors = {}
        if user_input is not None:
            # validation

            # try to connect
            for x in range(0, 5):
                result = await self.hass.async_add_executor_job(
                    add_new_device, self.hass, x, G_IOT_DEV_TO_ADD[0], user_input[CONF_NAME],
                    user_input['networks'], user_input[CONF_PASSWORD], ais_global.G_AIS_SECURE_ANDROID_ID_DOM)
                _LOGGER.info(str(result))
                if result == 'ok':
                    return await self.async_step_init(user_input=None)
                else:
                    errors = {'base': 'add_failed'}
            #
        return self.async_show_form(
            step_id='add_device',
            errors=errors if errors else {},
            data_schema=data_schema,
            description_placeholders={
                'gate_id': ais_global.G_AIS_SECURE_ANDROID_ID_DOM, 'device_id': G_IOT_DEV_TO_ADD[0]},
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Dodano nowe urządzenie",
                data=user_input
            )

        return self.async_show_form(
            step_id='init',
            errors=errors,
            description_placeholders={
                'auth_url': G_AUTH_URL,
            },
        )



