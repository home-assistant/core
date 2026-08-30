"""Test the MJPEG IP Camera camera platform."""

import aiohttp
import httpx
import pytest
import respx

from homeassistant.components.camera import async_get_image
from homeassistant.components.mjpeg.const import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

ENTITY_CAMERA = "camera.my_mjpeg_camera"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(TimeoutError, "timeout_getting_image", id="timeout"),
        pytest.param(aiohttp.ClientError, "error_getting_image", id="client_error"),
    ],
)
async def test_camera_image_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    exception: type[Exception],
    translation_key: str,
) -> None:
    """Test that a failed still image request raises instead of returning nothing."""
    aioclient_mock.get("http://example.com/still", exc=exception)

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_image(hass, ENTITY_CAMERA)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


@pytest.mark.usefixtures("init_integration")
async def test_camera_image(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a still image is returned."""
    aioclient_mock.get("http://example.com/still", content=b"image_bytes")

    image = await async_get_image(hass, ENTITY_CAMERA)

    assert image.content == b"image_bytes"


@pytest.fixture
def mock_digest_config_entry() -> MockConfigEntry:
    """Return a mocked config entry that uses digest authentication."""
    return MockConfigEntry(
        title="My MJPEG Camera",
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_PASSWORD: "supersecret",
            CONF_STILL_IMAGE_URL: "http://example.com/still",
            CONF_USERNAME: "frenck",
            CONF_VERIFY_SSL: True,
        },
    )


@respx.mock
@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(TimeoutError, "timeout_getting_image", id="timeout"),
        pytest.param(
            httpx.TimeoutException, "timeout_getting_image", id="httpx_timeout"
        ),
        pytest.param(httpx.HTTPError, "error_getting_image", id="http_error"),
    ],
)
async def test_digest_camera_image_error(
    hass: HomeAssistant,
    mock_digest_config_entry: MockConfigEntry,
    exception: type[Exception],
    translation_key: str,
) -> None:
    """Test that a failed digest image request raises instead of returning nothing."""
    mock_digest_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_digest_config_entry.entry_id)
    await hass.async_block_till_done()

    respx.get("http://example.com/still").mock(side_effect=exception("boom"))
    respx.get("https://example.com/mjpeg").mock(side_effect=exception("boom"))

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_image(hass, ENTITY_CAMERA)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
