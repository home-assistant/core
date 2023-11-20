"""Sveriges radio classes."""


import aiohttp
from defusedxml import ElementTree

from homeassistant.components.media_source.error import Unresolvable


class Channel:
    """Class for a channel."""

    def __init__(
        self,
        sveriges_radio,
        name=None,
        station_id=None,
        siteurl=None,
        color=None,
        image=None,
        url=None,
        **kwargs,
    ):
        """Init function for channel class."""
        self.sveriges_radio = sveriges_radio

        if not station_id:
            raise Unresolvable("No such channel")

        self.station_id = station_id
        self.name = name
        self.siteurl = siteurl
        self.color = color
        self.image = image
        self.url = url

    def __repr__(self):
        """Represent a channel."""

        return "Channel(%s)" % self.name


class SverigesRadio:
    """Class for Sveriges Radio API."""

    def __init__(self, session: aiohttp.ClientSession, user_agent: str) -> None:
        """Init function for Sveriges Radio."""
        self.session = session
        self.user_agent = user_agent

    async def call(self, method, payload):
        """Asynchronously call the API."""
        url = f"http://api.sr.se/api/v2/{method}"

        try:
            async with self.session.get(url, params=payload, timeout=8) as response:
                if response.status != 200:
                    return {}
                response_text = await response.text()
                return ElementTree.fromstring(response_text)
        except aiohttp.ClientError:
            # Handle network-related errors here
            return {}

    async def resolve_station(self, station_id):
        """Resolve whether a station is a channel or a podcast."""
        payload = {}
        channel_data = await self.call(f"channels/{station_id}", payload)
        podcast_data = await self.call(f"podfiles/{station_id}", payload)

        if channel_data != {}:
            channel_id = channel_data.find("channel").attrib.get("id")
            return await self.channel(channel_id)
        if podcast_data != {}:
            podcast_id = podcast_data.find("podfile").attrib.get("id")
            return await self.podcast(podcast_id)
        raise Unresolvable("No valid id.")

    async def channels(self):
        """Asynchronously get all channels."""
        payload = {}
        data = await self.call("channels", payload)

        channels = []
        for channel_data in data.find("channels"):
            station_id = channel_data.attrib.get("id")
            name = channel_data.attrib.get("name")
            siteurl = channel_data.find("siteurl").text
            color = channel_data.find("color").text
            image = channel_data.find("image").text
            url = channel_data.find("liveaudio/url").text

            channel = Channel(
                sveriges_radio=self,
                name=name,
                station_id=station_id,
                siteurl=siteurl,
                color=color,
                image=image,
                url=url,
            )

            channels.append(channel)

        return channels

    async def channel(self, station_id):
        """Asynchronously get a specific channel."""
        payload = {}
        data = await self.call(f"channels/{station_id}", payload)

        channel_data = data.find("channel")
        station_id = channel_data.attrib.get("id")
        name = channel_data.attrib.get("name")
        siteurl = channel_data.find("siteurl").text
        color = channel_data.find("color").text
        image = channel_data.find("image").text
        url = channel_data.find("liveaudio/url").text

        channel = Channel(
            sveriges_radio=self,
            name=name,
            station_id=station_id,
            siteurl=siteurl,
            color=color,
            image=image,
            url=url,
        )

        return channel

    async def programs(self):
        """Asynchronously get all programs that contains podcasts."""
        payload = {}
        data = await self.call("programs", payload)

        if data.find("pagination/nextpage") is None:
            return None

        programs = []
        for program_data in data.find("programs"):
            if program_data.find("haspod").text != "true":
                continue

            station_id = program_data.attrib.get("id")
            name = program_data.attrib.get("name")
            siteurl = program_data.find("programurl").text
            program_image = program_data.find("programimage").text

            program = Channel(
                sveriges_radio=self,
                name=name,
                station_id=station_id,
                siteurl=siteurl,
                image=program_image,
            )

            programs.append(program)

        return programs

    async def program(self, program_id):
        """Asynchronously get a program."""
        payload = {}
        data = await self.call(f"programs/{program_id}", payload)

        program_data = data.find("program")

        station_id = program_data.attrib.get("id")
        name = program_data.attrib.get("name")
        siteurl = program_data.find("programurl").text
        program_image = program_data.find("programimage").text

        program = Channel(
            sveriges_radio=self,
            name=name,
            station_id=station_id,
            siteurl=siteurl,
            image=program_image,
        )

        return program

    async def podcasts(self, program_id):
        """Asynchronously get all podcasts."""
        payload = {}
        data = await self.call(f"podfiles?programid=/{program_id}", payload)

        podcasts = []

        if not data:
            return podcasts

        for podcast_data in data.find("podfiles"):
            station_id = podcast_data.attrib.get("id")
            name = podcast_data.find("title").text
            url = podcast_data.find("url").text

            podcast = Channel(
                sveriges_radio=self,
                name=name,
                station_id=station_id,
                url=url,
                image="https://static-cdn.sr.se/images/86/2efa24a7-f80c-435d-ae1c-29d060cb645d.jpg?preset=api-default-square",
            )

            podcasts.append(podcast)

        return podcasts

    async def podcast(self, podcast_id):
        """Asynchronously get a podcast."""
        payload = {}
        data = await self.call(f"podfiles/{podcast_id}", payload)

        station_id = data.attrib.get("id")
        name = data.find("title").text
        url = data.find("url").text

        podcast = Channel(
            sveriges_radio=self,
            name=name,
            station_id=station_id,
            url=url,
            image="https://static-cdn.sr.se/images/86/2efa24a7-f80c-435d-ae1c-29d060cb645d.jpg?preset=api-default-square",
        )

        return podcast
