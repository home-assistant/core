import requests
import json
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
    STATE_PAUSED
)

API_BASEURL = "https://api.smartthings.com/v1"
API_DEVICES = API_BASEURL + "/devices/"
COMMAND_POWER_ON = "{'commands': [{'component': 'main','capability': 'switch','command': 'on'}]}"
COMMAND_POWER_OFF = "{'commands': [{'component': 'main','capability': 'switch','command': 'off'}]}"
COMMAND_REFRESH = "{'commands':[{'component': 'main','capability': 'refresh','command': 'refresh'}]}"
COMMAND_PAUSE = "{'commands':[{'component': 'main','capability': 'mediaPlayback','command': 'pause'}]}"
COMMAND_MUTE = "{'commands':[{'component': 'main','capability': 'audioMute','command': 'mute'}]}"
COMMAND_UNMUTE = "{'commands':[{'component': 'main','capability': 'audioMute','command': 'unmute'}]}"
COMMAND_PLAY = "{'commands':[{'component': 'main','capability': 'mediaPlayback','command': 'play'}]}"
COMMAND_STOP = "{'commands':[{'component': 'main','capability': 'mediaPlayback','command': 'stop'}]}"
COMMAND_REWIND = "{'commands':[{'component': 'main','capability': 'mediaPlayback','command': 'rewind'}]}"
COMMAND_FAST_FORWARD = "{'commands':[{'component': 'main','capability': 'mediaPlayback','command': 'fastForward'}]}"

CONTROLLABLE_SOURCES = ["bluetooth", "wifi"]


class SoundbarApi:

    @staticmethod
    def device_update(self):
        API_KEY = self._api_key
        REQUEST_HEADERS = {"Authorization": "Bearer " + API_KEY}
        DEVICE_ID = self._device_id
        API_DEVICE = API_DEVICES + DEVICE_ID
        API_DEVICE_STATUS = API_DEVICE + "/states"
        API_COMMAND = API_DEVICE + "/commands"
        cmdurl = requests.post(API_COMMAND, data=COMMAND_REFRESH, headers=REQUEST_HEADERS)
        resp = requests.get(API_DEVICE_STATUS, headers=REQUEST_HEADERS)
        data = resp.json()
        device_volume = data['main']['volume']['value']
        device_volume = min(int(device_volume) / self._max_volume, 1)
        switch_state = data['main']['switch']['value']
        playback_state = data['main']['playbackStatus']['value']
        device_source = data['main']['inputSource']['value']
        device_all_sources = json.loads(data['main']['supportedInputSources']['value'])
        device_muted = data['main']['mute']['value'] != "unmuted"

        if switch_state == "on":
            if device_source in CONTROLLABLE_SOURCES:
                if playback_state == "playing":
                    self._state = STATE_PLAYING
                elif playback_state == "paused":
                    self._state = STATE_PAUSED
                else:
                    self._state = STATE_IDLE
            else:
                self._state = STATE_IDLE
        else:
            self._state = STATE_OFF
        self._volume = device_volume
        self._source_list = device_all_sources if type(device_all_sources) is list else device_all_sources["value"]
        self._muted = device_muted
        self._source = device_source
        if self._state in [STATE_PLAYING, STATE_PAUSED]:
            self._media_title = data['main']['trackDescription']['value']
        else:
            self._media_title = None

    @staticmethod
    def send_command(self, argument, cmdtype):
        API_KEY = self._api_key
        REQUEST_HEADERS = {"Authorization": "Bearer " + API_KEY}
        DEVICE_ID = self._device_id
        API_DEVICES = API_BASEURL + "/devices/"
        API_DEVICE = API_DEVICES + DEVICE_ID
        API_COMMAND = API_DEVICE + "/commands"

        if cmdtype == "setvolume":  # sets volume
            API_COMMAND_DATA = "{'commands':[{'component': 'main','capability': 'audioVolume','command': 'setVolume','arguments': "
            volume = int(argument * self._max_volume)
            API_COMMAND_ARG = "[{}]}}]}}".format(volume)
            API_FULL = API_COMMAND_DATA + API_COMMAND_ARG
            cmdurl = requests.post(API_COMMAND, data=API_FULL, headers=REQUEST_HEADERS)
        elif cmdtype == "stepvolume":  # steps volume up or down
            if argument == "up":
                API_COMMAND_DATA = "{'commands':[{'component': 'main','capability': 'audioVolume','command': 'volumeUp'}]}"
                cmdurl = requests.post(API_COMMAND, data=API_COMMAND_DATA, headers=REQUEST_HEADERS)
            else:
                API_COMMAND_DATA = "{'commands':[{'component': 'main','capability': 'audioVolume','command': 'volumeDown'}]}"
                cmdurl = requests.post(API_COMMAND, data=API_COMMAND_DATA, headers=REQUEST_HEADERS)
        elif cmdtype == "audiomute":  # mutes audio
            if self._muted == False:
                cmdurl = requests.post(API_COMMAND, data=COMMAND_MUTE, headers=REQUEST_HEADERS)
            else:
                cmdurl = requests.post(API_COMMAND, data=COMMAND_UNMUTE, headers=REQUEST_HEADERS)
        elif cmdtype == "switch_off":  # turns off
            cmdurl = requests.post(API_COMMAND, data=COMMAND_POWER_OFF, headers=REQUEST_HEADERS)
        elif cmdtype == "switch_on":  # turns on
            cmdurl = requests.post(API_COMMAND, data=COMMAND_POWER_ON, headers=REQUEST_HEADERS)
        elif cmdtype == "play":  # play
            cmdurl = requests.post(API_COMMAND, data=COMMAND_PLAY, headers=REQUEST_HEADERS)
        elif cmdtype == "pause":  # pause
            cmdurl = requests.post(API_COMMAND, data=COMMAND_PAUSE, headers=REQUEST_HEADERS)
        elif cmdtype == "selectsource":  # changes source
            API_COMMAND_DATA = "{'commands':[{'component': 'main','capability': 'mediaInputSource','command': 'setInputSource', 'arguments': "
            API_COMMAND_ARG = "['{}']}}]}}".format(argument)
            API_FULL = API_COMMAND_DATA + API_COMMAND_ARG
            cmdurl = requests.post(API_COMMAND, data=API_FULL, headers=REQUEST_HEADERS)
        self.async_schedule_update_ha_state()
