"""Constants and mock for the twkinly component tests."""

from uuid import uuid4

from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.twinkly.const import DEV_NAME

TEST_HOST = "test.twinkly.com"
TEST_ID = "twinkly_test_device_id"
TEST_NAME = "twinkly_test_device_name"
TEST_NAME_ORIGINAL = "twinkly_test_original_device_name"  # the original (deprecated) name stored in the conf
TEST_MODEL = "twinkly_test_device_model"


class ClientMock:
    """A mock of the twinkly_client.TwinklyClient."""

    def __init__(self) -> None:
        """Create a mocked client."""
        self.is_offline = False
        self.is_on = True
        self.brightness = 10

        self.id = str(uuid4())
        self.device_info = {
            "uuid": self.id,
            "device_name": self.id,  # we make sure that entity id is different for each test
            "product_code": TEST_MODEL,
        }

    @property
    def host(self) -> str:
        """Get the mocked host."""
        return TEST_HOST

    async def get_device_info(self):
        """Get the mocked device info."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.device_info

    async def get_is_on(self) -> bool:
        """Get the mocked on/off state."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.is_on

    async def set_is_on(self, is_on: bool) -> None:
        """Set the mocked on/off state."""
        if self.is_offline:
            raise ClientConnectionError()
        self.is_on = is_on

    async def get_brightness(self) -> int:
        """Get the mocked brightness."""
        if self.is_offline:
            raise ClientConnectionError()
        return self.brightness

    async def set_brightness(self, brightness: int) -> None:
        """Set the mocked brightness."""
        if self.is_offline:
            raise ClientConnectionError()
        self.brightness = brightness

    def change_name(self, new_name: str) -> None:
        """Change the name of this virtual device."""
        self.device_info[DEV_NAME] = new_name
