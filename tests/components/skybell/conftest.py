"""Configure pytest for Skybell tests."""
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from aiohttp.client import ClientError
from aioskybell.helpers.const import BASE_URL, USERS_ME_URL
import pytest

from homeassistant.components.skybell.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

USERNAME = "user"
PASSWORD = "password"
USER_ID = "1234567890abcdef12345678"
DEVICE_ID = "012345670123456789abcdef"

CONF_DATA = {
    CONF_EMAIL: USERNAME,
    CONF_PASSWORD: PASSWORD,
}


@pytest.fixture()
def invalid_auth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Return invalid auth."""
    return aioclient_mock.post(
        f"{BASE_URL}login/",
        text=load_fixture("skybell/login_401.json"),
        status=HTTPStatus.UNAUTHORIZED,
    )


@pytest.fixture()
def internal_server_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Return internal server error."""
    return aioclient_mock.post(
        f"{BASE_URL}login/",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


@pytest.fixture()
def cannot_connect(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Return internal server error."""
    return aioclient_mock.post(
        f"{BASE_URL}login/",
        text="{}",
        exc=ClientError,
    )


@pytest.fixture()
def auth_exception(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Return invalid authorization error."""
    return aioclient_mock.get(
        USERS_ME_URL,
        text=load_fixture("skybell/login_401.json"),
        status=HTTPStatus.UNAUTHORIZED,
    )


@pytest.fixture()
def not_ready(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Return internal server error."""
    return aioclient_mock.get(
        USERS_ME_URL,
        text="{}",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create fixture for adding config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=USER_ID, data=CONF_DATA)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture()
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    return create_entry(hass)


def patch_skybell_devices() -> None:
    """Patch Skybell devices."""
    mocked_skybell = AsyncMock()
    mocked_skybell.user_id = USER_ID
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_get_devices",
        return_value=[mocked_skybell],
    )


def patch_skybell() -> None:
    """Patch Skybell."""
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_send_request",
        return_value={"id": USER_ID},
    )


def patch_cache() -> None:
    """Patch Skybell cache."""
    return patch("aioskybell.utils.async_save_cache")


async def set_aioclient_responses(aioclient_mock: AiohttpClientMocker) -> None:
    """Set AioClient responses."""
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/info/",
        text=load_fixture("skybell/device_info.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        text=load_fixture("skybell/device_settings.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/activities/",
        text=load_fixture("skybell/activities.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}devices/",
        text=load_fixture("skybell/device.json"),
    )
    aioclient_mock.get(
        USERS_ME_URL,
        text=load_fixture("skybell/me.json"),
    )
    aioclient_mock.post(
        f"{BASE_URL}login/",
        text=load_fixture("skybell/login.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/activities/1234567890ab1234567890ac/video/",
        text=load_fixture("skybell/video.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/avatar/",
        text=load_fixture("skybell/avatar.json"),
    )
    aioclient_mock.get(
        f"https://v3-production-devices-avatar.s3.us-west-2.amazonaws.com/{DEVICE_ID}.jpg",
    )
    aioclient_mock.get(
        f"https://skybell-thumbnails-stage.s3.amazonaws.com/{DEVICE_ID}/1646859244793-951{DEVICE_ID}_{DEVICE_ID}.jpeg",
    )


@pytest.fixture
async def connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Fixture for good connection responses."""
    await set_aioclient_responses(aioclient_mock)


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Skybell integration in Home Assistant."""
    config_entry = create_entry(hass)

    if not skip_setup:
        with patch_cache(), patch(
            "homeassistant.core.Config.path",
            return_value="tests/components/skybell/fixtures/cache.pickle",
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
