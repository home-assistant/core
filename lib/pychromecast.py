"""
Collection of methods to control a Chromecast via Python.

Functionality is currently limited to starting and quiting applications.

Interaction with running applications is not supported.

So what can it do? It can open YouTube movies and playlists.
"""
import xml.etree.ElementTree as ET
from collections import namedtuple

import requests


# Retrieved from https://clients3.google.com/cast/chromecast/device/config
APP_ID_HOME = "00000000-0000-0000-0000-000000000000"
# APP_ID_CHROMECAST = "ChromeCast" # shows white screen with error ??
APP_ID_YOUTUBE = "YouTube"
APP_ID_NETFLIX = "Netflix"
APP_ID_TICTACTOE = "TicTacToe"
APP_ID_GOOGLE_MUSIC = "GoogleMusic"
APP_ID_PLAY_MOVIES = "PlayMovies"



def start_app(host, app_id, data=None):
    """ Starts an application. 

        If your TV is not on will turn it on unless app_id == APP_ID_HOME. """

    if data is None:
        data = {"":""}

    _requests.post(_craft_url(host, app_id), data=data)

def quit_app(host, app_id=None):
    """ Quits specified application if it is running.
        If no app_id specified will quit current running app. """

    if not app_id:
        app_id = get_app_status(host).name

    _requests.delete(_craft_url(host, app_id))

def play_youtube_video(host, video_id):
    """ Starts the YouTube app if it is not running and plays
        specified video. """

    start_app(host, APP_ID_YOUTUBE, {"v": video_id})

def play_youtube_playlist(host, playlist_id):
    """ Starts the YouTube app if it is not running and plays
        specified playlist. """

    start_app(host, APP_ID_YOUTUBE, {"listType":"playlist", "list":playlist_id})

def get_device_status(host):
    """ Returns the device status as a named tuple. """

    try:
        status_el = ET.fromstring(_requests.get(format_base_url.format(host) + "/ssdp/device-desc.xml").text)
        device_info_el = status_el.find(XML_NS_UPNP_DEVICE + "device")
        api_version_el = status_el.find(XML_NS_UPNP_DEVICE + "specVersion")

    except requests.exceptions.RequestException as e:
        # If the host is incorrect and thus triggers a RequestException reraise it
        raise e
    
    except:
        raise PyChromecastException("Error parsing device status XML")
    

    friendly_name = _read_xml_element(device_info_el, XML_NS_UPNP_DEVICE, "friendlyName", "Unknown Chromecast")
    model_name = _read_xml_element(device_info_el, XML_NS_UPNP_DEVICE, "modelName", "Unknown model name")
    manufacturer = _read_xml_element(device_info_el, XML_NS_UPNP_DEVICE, "manufacturer", "Unknown manufacturer")

    api_version = (int(_read_xml_element(api_version_el, XML_NS_UPNP_DEVICE, "major", -1)), 
                    int(_read_xml_element(api_version_el, XML_NS_UPNP_DEVICE, "minor", -1)))

    return DeviceStatus(friendly_name, model_name, manufacturer, api_version)

def get_app_status(host, app_id=None):
    """ Returns the status of the specified app or else the current running app. """
    # /apps/ will redirect to the active app
    url = format_app_path.format(host, app_id) if app_id else format_base_url.format(host) + "/apps/"

    try:
        status_el = ET.fromstring(_requests.get(url).text)
        options = status_el.find(XML_NS_DIAL + "options").attrib

    except requests.exceptions.RequestException as e:
        # If the host is incorrect and thus triggers a RequestException reraise it
        raise e

    except:
        raise PyChromecastException("Error parsing app status XML")

    name = _read_xml_element(status_el, XML_NS_DIAL, "name", "Unknown application")
    state = _read_xml_element(status_el, XML_NS_DIAL, "state", "unknown")

    return AppStatus(name, state, options)



class PyChromecast(object):
    """ Class to connect to a ChromeCast. """

    def __init__(self, host, app_id=None):
        self.host = host

        self.device = get_device_status(host)

        self.app_id = app_id

    @property
    def app_id(self):
        return self._app_id

    @app_id.setter
    def app_id(self, value):
        self._app_id = value
        
        self.refresh_app_status()

        # There is always an app active on the Chromecast.
        # So if app_id was none get_app_status retrieved the status
        # from the current active app, let's update self._app_id
        if not value:
            self._app_id = self.app.name

    def refresh_app_status(self):
        self.app = get_app_status(self.host, self._app_id)

    def start_app(self, data=None):
        # data parameter has to contain atleast 1 key or else some apps won't show
        start_app(self.host, self.app_id, data)
        self.refresh_app_status()

    def quit_app(self):
        quit_app(host, self.app_id)

    def __str__(self):
        return "PyChromecast({}, {}, {}, {}, api={}.{})".format(self.host, self.friendly_name, self.model_name, self.manufacturer, self.api_version[0], self.api_version[1])




XML_NS_UPNP_DEVICE = "{urn:schemas-upnp-org:device-1-0}"
XML_NS_DIAL = "{urn:dial-multiscreen-org:schemas:dial}"

format_base_url = "http://{}:8008"
format_app_path = format_base_url + "/apps/{}"

_requests = requests.Session()
_requests.headers['content-type'] = 'application/json'

DeviceStatus = namedtuple("DeviceStatus", ["friendly_name","model_name","manufacturer","api_version"])
AppStatus = namedtuple("AppStatus", ["name","state","options"])

def _craft_url(host, app_id=None):
    """ Helper method to create a ChromeCast url given a host and an optional app_id. """
    return format_app_path.format(host, app_id) if app_id else format_base_url.format(host)

def _read_xml_element(element, xml_ns, tag_name, default=""):
    """ Helper method to read text from an element. """
    try:
        return element.find(xml_ns + tag_name).text
    except:
        return default

class PyChromecastException(Exception):
    """ Base exception for PyChromecast. """
    pass
