"""Support for the Homely speech service."""
import asyncio
import logging
import re

import aiohttp
from aiohttp.hdrs import REFERER, USER_AGENT
import async_timeout
import voluptuous as vol
import yarl

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import requests, json, time

_LOGGER = logging.getLogger(__name__)

# Declare variables
DOMAIN = 'tts_homely'
SERVICE_FPT_TTS = 'say'

# config
CONF_API_KEY = "api_key"
CONF_SPEED = "speed"
CONF_VOICE_TYPE = 'voice_type'
ATTR_CREDENTIALS = 'credentials'
voice_list = {'nam_mien_bac': 'leminh', 'nu_mien_bac': 'banmai', 'nu_mien_nam': 'lannhi','nu_hue': 'ngoclam'}
DEFAULT_SPEED= '-1'
DEFAULT_VOICE='lannhi'

GOOGLE_SPEECH_URL = "https://translate.google.com/translate_tts"
FPT_SPEECH_URL = 'https://api.fpt.ai/hmi/tts/v5'
MESSAGE_SIZE = 148

SUPPORT_LANGUAGES = [
    'af', 'sq', 'ar', 'hy', 'bn', 'ca', 'zh', 'zh-cn', 'zh-tw', 'zh-yue',
    'hr', 'cs', 'da', 'nl', 'en', 'en-au', 'en-uk', 'en-us', 'eo', 'fi',
    'fr', 'de', 'el', 'hi', 'hu', 'is', 'id', 'it', 'ja', 'ko', 'la', 'lv',
    'mk', 'no', 'pl', 'pt', 'pt-br', 'ro', 'ru', 'sr', 'sk', 'es', 'es-es',
    'es-mx', 'es-us', 'sw', 'sv', 'ta', 'th', 'tr', 'vi', 'cy', 'uk', 'bg-BG'
]

DEFAULT_LANG = 'en'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
    vol.Optional(CONF_API_KEY, ATTR_CREDENTIALS): cv.string,
    vol.Optional(CONF_SPEED, ATTR_CREDENTIALS): cv.string,
    vol.Optional(CONF_VOICE_TYPE, ATTR_CREDENTIALS): cv.string,
})



async def async_get_engine(hass, config):
    """Set up Homely speech component."""    
    return HomelyProvider(hass, config)


class HomelyProvider(Provider):
    """The Homely speech API provider."""

    def __init__(self, hass, config):
        """Init Homely TTS service."""                 
        self.config = config
        if self.config.get(CONF_API_KEY): 
            self.api_key= self.config.get(CONF_API_KEY) 
        else: 
            self.api_key=''
        
        if self.config.get(CONF_SPEED):
            self.speed = self.config.get(CONF_SPEED)
        else:
            self.speed = DEFAULT_SPEED
            
        
        if self.config.get(CONF_VOICE_TYPE):
            self.voicetype = voice_list.get(self.config.get(CONF_VOICE_TYPE))
        else:
            self.voicetype = DEFAULT_VOICE
        self.hass = hass
        self._lang = self.config.get(CONF_LANG)
        self.headers = {
            REFERER: "http://translate.google.com/",
            USER_AGENT: ("Mozilla/5.0 (Windows NT 10.0; WOW64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/47.0.2526.106 Safari/537.36"),
            'api_key':self.api_key,
            'speed':self.speed,
            'prosody':'1',
            'voice': self.voicetype
        }
        _LOGGER.error(self.api_key)
        self.name = 'Homely'
        

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from google or FPT."""
        from gtts_token import gtts_token

        token = gtts_token.Token()
        websession = async_get_clientsession(self.hass)
        message_parts = self._split_message_to_parts(message)

        data = b''
        for idx, part in enumerate(message_parts):
            part_token = await self.hass.async_add_job(
                token.calculate_token, part)
            
            url_param = {
                'ie': 'UTF-8',
                'tl': language,
                'q': yarl.URL(part).raw_path,
                'tk': part_token,
                'total': len(message_parts),                
                'idx': idx,
                'client': 'tw-ob',
                'textlen': len(part),
            }
            

            try:
                with async_timeout.timeout(10):
                    
                    if self._lang =="vi" and self.api_key!='':
                        url_mp3 = requests.post(FPT_SPEECH_URL, data = part.encode('utf-8'), headers = self.headers).json()['async']
                        # time sleep in seconds
                        time_sleep = 0.5
                        # time_wait = 10 seconds/time_sleep
                        time_wait = 20
                        tcount = 0

                        #check status request
                        res_response = requests.get(url_mp3)
                        res_status = res_response.status_code
                        # Wait for hass request FPT Speech Synthesis to complete
                        while (res_status == 404 and tcount < time_wait):
                            time.sleep(time_sleep)
                            res_response = requests.get(url_mp3)
                            res_status = res_response.status_code
                            tcount += 1
                        # if error => msgbox_error
                        if tcount == time_wait:
                            msgbox_error = "Đã xảy ra lỗi. Vui lòng kiểm tra lại."
                            msgbox_error = msgbox_error.encode('utf-8')
                            url_error = requests.post(FPT_SPEECH_URL, data = msgbox_error, headers = self.headers).json()['async']
                            res_response = requests.get(url_error)
                        data += res_response.content
                    else:
                        
                        request = await websession.get(
                            GOOGLE_SPEECH_URL, params=url_param,
                            headers=self.headers
                        )
                        
                        if request.status != 200:
                            _LOGGER.error("Error %d on load URL %s",request.status, request.url)
                            return None, None
                        data += await request.read()

            except (asyncio.TimeoutError, aiohttp.ClientError):
                _LOGGER.error("Timeout for google speech")
                return None, None
        
        return 'mp3', data

    @staticmethod
    def _split_message_to_parts(message):
        """Split message into single parts."""
        if len(message) <= MESSAGE_SIZE:
            return [message]

        punc = "!()[]?.,;:"
        punc_list = [re.escape(c) for c in punc]
        pattern = '|'.join(punc_list)
        parts = re.split(pattern, message)

        def split_by_space(fullstring):
            """Split a string by space."""
            if len(fullstring) > MESSAGE_SIZE:
                idx = fullstring.rfind(' ', 0, MESSAGE_SIZE)
                return [fullstring[:idx]] + split_by_space(fullstring[idx:])
            return [fullstring]

        msg_parts = []
        for part in parts:
            msg_parts += split_by_space(part)

        return [msg for msg in msg_parts if len(msg) > 0]
