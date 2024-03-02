"""Constants and mock for the twinkly component tests."""


from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.twinkly.const import DEV_NAME

TEST_HOST = "test.twinkly.com"
TEST_ID = "twinkly_test_device_id"
TEST_UID = "4c8fccf5-e08a-4173-92d5-49bf479252a2"
TEST_NAME = "twinkly_test_device_name"
TEST_NAME_ORIGINAL = "twinkly_test_original_device_name"  # the original (deprecated) name stored in the conf
TEST_MODEL = "twinkly_test_device_model"


class ClientMock:
    """A mock of the ttls.client.Twinkly."""

    def __init__(self) -> None:
        """Create a mocked client."""
        self.is_offline = False
        self.state = True
        self.brightness = {"mode": "enabled", "value": 10}
        self.color = None
        self.movies = [{"id": 1, "name": "Rainbow"}, {"id": 2, "name": "Flare"}]
        self.current_movie = {}
        self.default_mode = "movie"
        self.mode = None
        self.version = "2.8.10"

        self.id = TEST_UID
        self.device_info = {
            "uuid": self.id,
            "device_name": TEST_NAME,
            "product_code": TEST_MODEL,
        }

    @property
    def host(self) -> str:
        """Get the mocked host."""
        return TEST_HOST

    async def get_details(self):
        """Get the mocked device info."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.device_info

    async def is_on(self) -> bool:
        """Get the mocked on/off state."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.state

    async def turn_on(self) -> None:
        """Set the mocked on state."""
        if self.is_offline:
            raise ClientConnectionError()
        self.state = True
        self.mode = self.default_mode

    async def turn_off(self) -> None:
        """Set the mocked off state."""
        if self.is_offline:
            raise ClientConnectionError()
        self.state = False

    async def get_brightness(self) -> int:
        """Get the mocked brightness."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.brightness

    async def set_brightness(self, brightness: int) -> None:
        """Set the mocked brightness."""
        if self.is_offline:
            raise ClientConnectionError()
        self.brightness = {"mode": "enabled", "value": brightness}

    def change_name(self, new_name: str) -> None:
        """Change the name of this virtual device."""
        self.device_info[DEV_NAME] = new_name

    async def set_static_colour(self, colour) -> None:
        """Set static color."""
        self.color = colour
        self.default_mode = "color"

    async def set_cycle_colours(self, colour) -> None:
        """Set static color."""
        self.color = colour
        self.default_mode = "movie"

    async def interview(self) -> None:
        """Interview."""

    async def get_saved_movies(self) -> dict:
        """Get saved movies."""
        return self.movies

    async def get_current_movie(self) -> dict:
        """Get current movie."""
        return self.current_movie

    async def set_current_movie(self, movie_id: int) -> dict:
        """Set current movie."""
        self.current_movie = {"id": movie_id}

    async def set_mode(self, mode: str) -> None:
        """Set mode."""
        if mode == "off":
            await self.turn_off()
        else:
            await self.turn_on()
            self.mode = mode

    async def get_firmware_version(self) -> dict:
        """Get firmware version."""
        return {"version": self.version}
