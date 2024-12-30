import json
import sys
from typing import Any, Dict, Iterable, Optional, Sequence
import typing

import six

from ..exceptions import PyiCloudNoDevicesException


class FindMyiPhoneServiceManager(object):
    """ The 'Find my iPhone' iCloud service

    This connects to iCloud and return phone data including the near-realtime
    latitude and longitude.

    """

    def __init__(self, service_root: str, session:Any, params: Dict[str, Any]):
        self.session = session
        self.params = params
        self._service_root = service_root
        self._fmip_endpoint = '%s/fmipservice/client/web' % self._service_root
        self._fmip_refresh_url = '%s/refreshClient' % self._fmip_endpoint
        self._fmip_sound_url = '%s/playSound' % self._fmip_endpoint
        self._fmip_message_url = '%s/sendMessage' % self._fmip_endpoint
        self._fmip_lost_url = '%s/lostDevice' % self._fmip_endpoint

        self._devices:Dict[str, AppleDevice] = {}
        self.refresh_client()

    def refresh_client(self) -> None:
        """ Refreshes the FindMyiPhoneService endpoint,

        This ensures that the location data is up-to-date.

        """
        req = self.session.post(
            self._fmip_refresh_url,
            params=self.params,
            data=json.dumps(
                {
                    'clientContext': {
                        'fmly': True,
                        'shouldLocate': True,
                        'selectedDevice': 'all',
                    }
                }
            )
        )
        self.response = req.json()

        for device_info in self.response['content']:
            device_id = device_info['id']
            if device_id not in self._devices:
                self._devices[device_id] = AppleDevice(
                    device_info,
                    self.session,
                    self.params,
                    manager=self,
                    sound_url=self._fmip_sound_url,
                    lost_url=self._fmip_lost_url,
                    message_url=self._fmip_message_url,
                )
            else:
                self._devices[device_id].update(device_info)

        if not self._devices:
            raise PyiCloudNoDevicesException()

    def __getitem__(self, key: Any) -> "AppleDevice":
        if isinstance(key, int):
            if six.PY3:
                key = list(self.keys())[key] # type: ignore[operator]
            else:
                key = self.keys()[key]
        return self._devices[key]

    def __getattr__(self, attr: str) -> "AppleDevice":
        return typing.cast(AppleDevice, getattr(self._devices, attr))

    def __unicode__(self) -> str:
        return six.text_type(self._devices)

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self) -> str:
        return six.text_type(self)
    

class AppleDevice(object):
    def __init__(
        self, content:Dict[str,Any], session:Any, params:Dict[str, Any], manager: FindMyiPhoneServiceManager,
        sound_url:Optional[str]=None, lost_url:Optional[str]=None, message_url:Optional[str]=None
    ):
        self.content = content
        self.manager = manager
        self.session = session
        self.params = params

        self.sound_url = sound_url
        self.lost_url = lost_url
        self.message_url = message_url

    def update(self, data: Dict[str, Any]) -> None:
        self.content = data

    def location(self) -> Any:
        self.manager.refresh_client()
        return self.content['location']

    def status(self, additional:Sequence[str]=[]) -> Dict[str, Any]:
        """ Returns status information for device.

        This returns only a subset of possible properties.
        """
        self.manager.refresh_client()
        fields = ['batteryLevel', 'deviceDisplayName', 'deviceStatus', 'name']
        fields += additional
        properties: Dict[str, Any] = {}
        for field in fields:
            properties[field] = self.content.get(field)
        return properties

    def play_sound(self, subject:str='Find My iPhone Alert') -> None:
        """ Send a request to the device to play a sound.

        It's possible to pass a custom message by changing the `subject`.
        """
        data = json.dumps({
            'device': self.content['id'],
            'subject': subject,
            'clientContext': {
                'fmly': True
            }
        })
        self.session.post(
            self.sound_url,
            params=self.params,
            data=data
        )

    def display_message(
        self, subject:str='Find My iPhone Alert', message:str="This is a note",
        sounds:bool=False
    ) -> None:
        """ Send a request to the device to play a sound.

        It's possible to pass a custom message by changing the `subject`.
        """
        data = json.dumps(
            {
                'device': self.content['id'],
                'subject': subject,
                'sound': sounds,
                'userText': True,
                'text': message
            }
        )
        self.session.post(
            self.message_url,
            params=self.params,
            data=data
        )

    def lost_device(
        self, number:str,
        text:str='This iPhone has been lost. Please call me.',
        newpasscode:str=""
    ) -> None:
        """ Send a request to the device to trigger 'lost mode'.

        The device will show the message in `text`, and if a number has
        been passed, then the person holding the device can call
        the number without entering the passcode.
        """
        data = json.dumps({
            'text': text,
            'userText': True,
            'ownerNbr': number,
            'lostModeEnabled': True,
            'trackingEnabled': True,
            'device': self.content['id'],
            'passcode': newpasscode
        })
        self.session.post(
            self.lost_url,
            params=self.params,
            data=data
        )

    @property
    def data(self) -> Dict[str, Any]:
        return self.content

    def __getitem__(self, key: str) -> Any:
        return self.content[key]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.content, attr)

    def __unicode__(self) -> str:
        display_name = self['deviceDisplayName']
        name = self['name']
        return '%s: %s' % (
            display_name,
            name,
        )

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self) -> str:
        return '<AppleDevice(%s)>' % str(self)
