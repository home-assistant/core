"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.const import (CONF_NAME, CONF_PASSWORD, CONF_TYPE)
from homeassistant.ais_dom import ais_global
import time
import voluptuous as vol
import logging

G_IOT_DEV_TO_ADD = []
_LOGGER = logging.getLogger(__name__)


def scan_for_new_device(hass, loop) -> []:
    global G_IOT_DEV_TO_ADD
    _LOGGER.info('scan_for_new_device, no of try: ' + str(loop))
    # send scan request to frame
    if loop == 0:
        hass.services.call("script", "ais_scan_iot_devices_in_network")
    # wait
    time.sleep(3)
    # and check the answer
    iot_dev = hass.states.get('input_select.ais_iot_devices_in_network')
    G_IOT_DEV_TO_ADD = iot_dev.attributes['options']
    return G_IOT_DEV_TO_ADD


def add_new_device(device, name, network, password, secure_android_id, set_option_30, ais_req_id) -> str:
    import requests
    from homeassistant.components import ais_ai_service as ais_ai_service
    # send add request to frame
    url = ais_ai_service.G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1")
    try:
        requests.post(
            url + '/command',
            json={"WifiConnectTheDevice": device, "ip": "127.0.0.1", "WifiNetworkPass": password,
                  "WifiNetworkSsid": network, "IotName": name, "bsssid": network,
                  "secureAndroidId": secure_android_id, "SetOption30": set_option_30, "IotAisReqId": ais_req_id},
            timeout=3)
    except Exception as e:
        return 'nok ' + str(e)

    return 'ok'


def check_the_answer(hass, loop, ais_req_id) -> str:
    # and check the answer from global
    answer_from_frame = ais_global.get_ais_gate_req_answer(ais_req_id)
    if answer_from_frame is not None:
        return answer_from_frame

    # no answer... wait before return
    time.sleep(3)
    return None

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
            _LOGGER.info("Wykryte urządzenia: " + str(result))
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
        # types
        dev_group = ["Przełączniki", "Światła"]
        wifi_network = self.hass.states.get('input_select.ais_android_wifi_network')
        networks = wifi_network.attributes['options']
        # curr network info
        curr_network = []
        if ais_global.GLOBAL_MY_WIFI_SSID is not None:
            curr_network = [ais_global.GLOBAL_MY_WIFI_SSID + " (Twoje aktualne połączenie WiFi)"]
        networks = curr_network + networks
        curr_pass = ais_global.GLOBAL_MY_WIFI_PASS

        errors = {}

        if user_input is None:
            data_schema = vol.Schema({
                vol.Required(CONF_NAME, default="Nowe inteligentne gniazdo"): str,
                vol.Required(CONF_TYPE, default="Przełączniki"): vol.In(list(dev_group)),
                vol.Required('networks', default=networks[0]): vol.In(list(networks)),
                vol.Required(CONF_PASSWORD, default=curr_pass): str,
                vol.Required('confirm_key'): bool,
            })

        else:
            # validations
            if not user_input['confirm_key']:
                errors['confirm_key'] = 'confirm_error'
            if len(user_input[CONF_NAME]) > 32:
                errors['name'] = 'name_error'

            data_schema = vol.Schema({
                vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                vol.Required(CONF_TYPE, default=user_input[CONF_TYPE]): vol.In(list(dev_group)),
                vol.Required('networks', default=user_input['networks']): vol.In(list(networks)),
                vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                vol.Required('confirm_key', default=user_input['confirm_key']): bool,
            })

            # try to connect
            if errors == {}:
                # relays are announced as a switch and PWM as a light (default)
                set_option_30 = 0
                if user_input[CONF_TYPE] != "Przełączniki":
                    set_option_30 = 1
                # unique req_id
                ais_req_id = int(round(time.time() * 1000))
                _LOGGER.info("add_new_device -> ais_req_id: " + str(ais_req_id))
                ais_global.set_ais_gate_req(str(ais_req_id), None)
                # send a request to frame to add the new device
                result = await self.hass.async_add_executor_job(
                    add_new_device, G_IOT_DEV_TO_ADD[0], user_input[CONF_NAME], user_input['networks'],
                    user_input[CONF_PASSWORD], ais_global.G_AIS_SECURE_ANDROID_ID_DOM, set_option_30, ais_req_id)
                # request was correctly send, now check and wait for the answer
                if result == 'ok':
                    for x in range(0, 7):
                        result = await self.hass.async_add_executor_job(check_the_answer, self.hass, x, ais_req_id)
                        # we have answer that all was OK
                        if result is not None:
                            if result == 'ok':
                                return await self.async_step_init(user_input=None)
                            else:
                                return self.async_abort(reason='add_failed', description_placeholders={
                                    'error_info': result,
                                })
                # abort without answer - timeout
                return self.async_abort(reason='add_failed', description_placeholders={
                    'error_info': "Timeout 21",
                })

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
            errors=errors
        )



