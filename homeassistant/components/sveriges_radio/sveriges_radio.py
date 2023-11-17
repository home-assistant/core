"""Sveriges radio classes."""

from datetime import datetime
import json
import re

import aiohttp
import requests

from homeassistant.components.media_source.error import Unresolvable


class Song:
    """Class for a song."""

    def __init__(
        self,
        artist=None,
        title=None,
        description=None,
        composer=None,
        conductor=None,
        **kwargs,
    ):
        """Init function for song class."""

        self.artist = artist.encode("utf-8")
        self.title = title.encode("utf-8")
        self.description = description.encode("utf-8")
        self.composer = composer.encode("utf-8")
        self.conductor = conductor.encode("utf-8")

    def __repr__(self):
        """Represent a song."""
        return f"Song({self.artist} - {self.title})"


class Episode:
    """Class for an episode."""

    def __init__(self, title=None, starttimeutc=None, endtimeutc=None, **kwargs):
        """Init function for episode class."""

        self.title = title.encode("utf-8")
        self.starttimeutc = starttimeutc
        self.endtimeutc = endtimeutc

    def __repr__(self):
        """Represent an episode."""
        return "Episode(%s)" % self.title

    @staticmethod
    def json_to_datetime(date):
        """Temporary method to get date and time from the json file."""

        match = re.match(r"/Date\((\d+)\)/", date)
        if not match:
            return None
        return datetime.fromtimestamp(int(match.group(1)) / 1000.0)

    @property
    def starttime(self):
        """The starting time of an episode."""

        return self.json_to_datetime(self.starttimeutc)

    @property
    def endtime(self):
        """The ending time of an episode."""
        return self.json_to_datetime(self.endtimeutc)


class Playlist:
    """Class for a playlist."""

    def __init__(self, now=None, next_song=None, content=Song):
        """Init function for playlist class."""

        self.now = content(**now) if now else None
        self.next_song = content(**next) if next_song else None

    def __repr__(self):
        """Represent a playlist."""

        return f"Playlist({self.now}, {self.next})"


class Channel:
    """Class for a channel."""

    def __init__(
        self,
        name=None,
        station_id=None,
        siteurl=None,
        color=None,
        image=None,
        url=None,
        **kwargs,
    ):
        """Init function for channel class."""

        if not station_id:
            raise Unresolvable("No such channel")

        self.station_id = station_id
        self.name = name.encode("utf-8")
        self.siteurl = siteurl
        self.color = color
        self.image = image
        self.url = url

    def __repr__(self):
        """Represent a channel."""

        return "Channel(%s)" % self.name

    @property
    def song(self):
        """Current song of the channel."""

        payload = {"channelid": self.station_id}
        response = SverigesRadio.call("/playlists/rightnow", payload)
        if not response:
            return Playlist()

        playlist = response.get("playlist")
        if not playlist:
            return Playlist()

        song = playlist.get("song")
        nextsong = playlist.get("nextsong")

        return Playlist(now=song, next=nextsong)

    @property
    def program(self):
        """Current program of the channel."""

        payload = {"channelid": self.station_id}
        response = SverigesRadio.call("/scheduledepisodes/rightnow", payload)
        if not response:
            return Playlist()

        channel = response.get("channel")
        if not channel:
            return Playlist()

        currentepisode = channel.get("currentscheduledepisode")
        nextepisode = channel.get("nextscheduledepisode")

        return Playlist(now=currentepisode, next=nextepisode, content=Episode)


class SverigesRadio:
    """Class for sveriges radio API."""

    user_agent: str

    session: aiohttp.client.ClientSession | None = None

    @classmethod
    def call(cls, method, payload):
        """Call the API."""

        url = "http://api.sr.se/api/v2/%s" % method

        payload["format"] = "json"

        response = requests.get(url, params=payload, timeout=8)
        if response.status_code != 200:
            return {}

        return json.loads(response.text)

    @classmethod
    def channels(cls):
        """Get all channels."""

        payload = {"size": 500}
        data = cls.call("/channels", payload)
        channels = data.get("channels")
        return [Channel(**channel) for channel in channels]

    @classmethod
    def channel(cls, station_id):
        """Get a specific channel."""

        data = cls.call("/channels/%s" % station_id)
        return Channel(**data.get("channel", {}))

    @classmethod
    def schedule(cls, channelid=None, programid=None):
        """Get the schedule of a specific channel."""

        payload = {"size": 500, "channelid": channelid, "programid": programid}
        data = cls.call("/scheduledepisodes", payload)
        if not data:
            return []
        schedule = data.get("schedule")
        return [Episode(**episode) for episode in schedule]
