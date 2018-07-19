# -*- coding: utf-8 -*-
"""
Support for AIS knowledge

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
import voluptuous as vol
from homeassistant.ais_dom import ais_global
from homeassistant.helpers import config_validation as cv
from homeassistant.components import ais_cloud
aisCloud = ais_cloud.AisCloudWS()
# DEPENDENCIES = ['http']

DOMAIN = 'ais_knowledge_service'
SERVICE_ASK = 'ask'
ATTR_TEXT = 'text'
ATTR_SAY_IT = 'say_it'
SERVICE_ASK_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): cv.string,
    vol.Optional(ATTR_SAY_IT): cv.boolean,
})
_LOGGER = logging.getLogger(__name__)
GKS_URL = 'https://kgsearch.googleapis.com/v1/entities:search'
G_GKS_KEY = None


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})
    yield from get_key_async(hass)

    @asyncio.coroutine
    def ask(service):
        """ask service about info"""
        yield from _process_ask_async(hass, service)

    # register services
    hass.services.async_register(
        DOMAIN, SERVICE_ASK, ask, schema=SERVICE_ASK_SCHEMA)

    return True


@asyncio.coroutine
def _process_ask_async(hass, call):
    import requests
    global G_GKS_KEY
    """Ask the service about text."""
    query = call.data[ATTR_TEXT]
    full_message = ""
    if G_GKS_KEY is None:
        try:
            ws_resp = aisCloud.key("kgsearch")
            json_ws_resp = ws_resp.json()
            G_GKS_KEY = json_ws_resp["key"]
        except:
            yield from hass.services.async_call(
                'ais_ai_service', 'say_it', {
                    "text": "Nie udało się wykonać, sprawdz połączenie z Intenetem"
                })
            return

    req = requests.get(
        GKS_URL,
        params={'query': query,
                'limit': 1,
                'indent': True,
                'key': G_GKS_KEY,
                'languages': 'pl'
                })
    try:
        response = req.json()
        element = response['itemListElement'][0]
        result = element['result']
        full_message = result['detailedDescription']['articleBody']

        if (ATTR_SAY_IT in call.data):
            yield from hass.services.async_call(
                'ais_ai_service',
                'say_it', {
                    "text": full_message
                })
    except Exception as e:
        full_message = "Brak wyników"
        yield from hass.services.async_call(
            'ais_ai_service',
            'say_it', {
                "text": full_message
            })


@asyncio.coroutine
def get_key_async(hass):
    def load():
        global G_GKS_KEY
        try:
            ws_resp = aisCloud.key("kgsearch")
            json_ws_resp = ws_resp.json()
            G_GKS_KEY = json_ws_resp["key"]
        except:
            ais_global.G_OFFLINE_MODE = True


    yield from hass.async_add_job(load)
