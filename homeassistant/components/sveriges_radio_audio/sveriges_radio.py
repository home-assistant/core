"""Python file for handling API calls."""


from typing import Union
from xml.etree.ElementTree import ElementTree

import aiohttp
import defusedxml
import requests
from requests import Response

api_url = "http://api.sr.se/api/v2/channels"


class sveriges_radio:
    """Class handling API calls."""

    session: aiohttp.client.ClientSession | None = None
    user_agent: str
    response: Response | None

    def __init__(self, session, user_agent, response):
        """Initiate a Sveriges Radio instance."""
        self.session = session
        self.user_agent = user_agent
        self.response = response

    def get_sr_channel(self, channels: ElementTree, station: Union[str, int]):
        """Return specific channel based on parameters."""
        # Function takes either the name in form of a string or int as the station id
        if isinstance(station, str):
            return channels.find("*[@name='%s']" % station)
        return channels.find("*[@id='%s']" % station)

    def get_sr_audio(self, channel: ElementTree):
        """Return the audio file url."""
        url_element = channel.find("liveaudio/url")
        if url_element is None:
            return ""
        return url_element.text

    async def call_sr_api(self):
        """Call the API."""
        response_sr = requests.get(api_url, timeout=3)
        # if response.status_code != 200:
        #    print("error")
        # else:
        #    print(response.status_code)
        self.response = response_sr
        return response_sr

    def get_sr_channels(self, response_sr: Response):
        """Return all channels from Sveriges Radio."""
        text = defusedxml.lxml.fromstring(response_sr.text)
        return text.find("channels")
