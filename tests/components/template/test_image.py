"""The tests for the Template image platform."""
from http import HTTPStatus
from io import BytesIO
from typing import Any

import httpx
from PIL import Image
import pytest
import respx

from homeassistant import setup
from homeassistant.components.input_text import (
    ATTR_VALUE as INPUT_TEXT_ATTR_VALUE,
    DOMAIN as INPUT_TEXT_DOMAIN,
    SERVICE_SET_VALUE as INPUT_TEXT_SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_PICTURE, CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from tests.common import assert_setup_component
from tests.typing import ClientSessionGenerator

_DEFAULT = object()
_TEST_IMAGE = "image.template_image"
_URL_INPUT_TEXT = "input_text.url"


@pytest.fixture
def imgbytes_jpg():
    """Image in RAM for testing."""
    buf = BytesIO()  # fake image in ram for testing.
    Image.new("RGB", (1, 1)).save(buf, format="jpeg")
    return bytes(buf.getbuffer())


@pytest.fixture
def imgbytes2_jpg():
    """Image in RAM for testing."""
    buf = BytesIO()  # fake image in ram for testing.
    Image.new("RGB", (1, 1), 100).save(buf, format="jpeg")
    return bytes(buf.getbuffer())


async def _assert_state(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    expected_state: str,
    expected_image: bytes | None,
    entity_id: str = _TEST_IMAGE,
    expected_content_type: str = "image/jpeg",
    expected_entity_picture: Any = _DEFAULT,
    expected_status: HTTPStatus = HTTPStatus.OK,
):
    """Verify image's state."""
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == expected_state
    if expected_entity_picture is _DEFAULT:
        expected_entity_picture = (
            f"/api/image_proxy/{entity_id}?token={attributes['access_token']}"
        )

    assert attributes.get(ATTR_ENTITY_PICTURE) == expected_entity_picture

    client = await hass_client()

    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.content_type == expected_content_type
    assert resp.status == expected_status
    body = await resp.read()
    assert body == expected_image


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_platform_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, imgbytes_jpg
) -> None:
    """Test configuring under the platform key does not work."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    with assert_setup_component(1, "image"):
        assert await setup.async_setup_component(
            hass,
            "image",
            {
                "image": {
                    "platform": "template",
                    "url": "{{ 'http://example.com' }}",
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_missing_optional_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, imgbytes_jpg
) -> None:
    """Test: missing optional template is ok."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": {
                        "url": "{{ 'http://example.com' }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1

    # Check the image is not refetched
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_multiple_configs(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    imgbytes_jpg,
    imgbytes2_jpg,
) -> None:
    """Test: multiple image entities get created."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/png"
    )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": [
                        {
                            "url": "{{ 'http://example.com' }}",
                        },
                        {
                            "url": "{{ 'http://example2.com' }}",
                        },
                    ]
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    await _assert_state(
        hass,
        hass_client,
        expected_state,
        imgbytes2_jpg,
        f"{_TEST_IMAGE}_2",
        expected_content_type="image/png",
    )


async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": {
                        "name": "a name",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("image") == []


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id configuration."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "b",
                    "image": {
                        "url": "http://example.com",
                        "unique_id": "a",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    ent_reg = async_get(hass)
    entry = ent_reg.async_get(_TEST_IMAGE)
    assert entry
    assert entry.unique_id == "b-a"


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_custom_entity_picture(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, imgbytes_jpg
) -> None:
    """Test custom entity picture."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": {
                        "url": "http://example.com",
                        "picture": "http://example2.com",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(
        hass,
        hass_client,
        expected_state,
        imgbytes_jpg,
        expected_entity_picture="http://example2.com",
    )


@respx.mock
async def test_template_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test handling template error."""
    respx.get("http://example.com").side_effect = httpx.TimeoutException

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": {
                        "url": "{{ no_such_variable.url }}",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await _assert_state(
        hass,
        hass_client,
        STATE_UNKNOWN,
        b"500: Internal Server Error",
        expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        expected_content_type="text/plain",
    )


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_templates_with_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    imgbytes_jpg,
    imgbytes2_jpg,
) -> None:
    """Test templates with values from other entities."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/png"
    )

    with assert_setup_component(1, "input_text"):
        assert await setup.async_setup_component(
            hass,
            "input_text",
            {
                "input_text": {
                    "url": {
                        "initial": "http://example.com",
                        "name": "url",
                    },
                }
            },
        )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "image": {
                        "url": f"{{{{ states('{_URL_INPUT_TEXT}') }}}}",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1

    # Check the image is not refetched
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1

    await hass.services.async_call(
        INPUT_TEXT_DOMAIN,
        INPUT_TEXT_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _URL_INPUT_TEXT, INPUT_TEXT_ATTR_VALUE: "http://example2.com"},
        blocking=True,
    )
    await hass.async_block_till_done()
    await _assert_state(
        hass,
        hass_client,
        expected_state,
        imgbytes2_jpg,
        expected_content_type="image/png",
    )


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_trigger_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    imgbytes_jpg,
    imgbytes2_jpg,
) -> None:
    """Test trigger based template image."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/png"
    )

    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "image": [
                        {
                            "url": "{{ trigger.event.data.url }}",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # No image is loaded, expect error
    await _assert_state(
        hass,
        hass_client,
        "unknown",
        b"500: Internal Server Error",
        expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        expected_content_type="text/plain",
    )

    hass.bus.async_fire("test_event", {"url": "http://example.com"})
    await hass.async_block_till_done()
    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1

    # Check the image is not refetched
    await _assert_state(hass, hass_client, expected_state, imgbytes_jpg)
    assert respx.get("http://example.com").call_count == 1

    hass.bus.async_fire("test_event", {"url": "http://example2.com"})
    await hass.async_block_till_done()
    await _assert_state(
        hass,
        hass_client,
        expected_state,
        imgbytes2_jpg,
        expected_content_type="image/png",
    )


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_trigger_image_custom_entity_picture(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, imgbytes_jpg
) -> None:
    """Test trigger based template image with custom entity picture."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "image": [
                        {
                            "url": "{{ trigger.event.data.url }}",
                            "picture": "http://example2.com",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # No image is loaded, expect error
    await _assert_state(
        hass,
        hass_client,
        "unknown",
        b"500: Internal Server Error",
        expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        expected_entity_picture="http://example2.com",
        expected_content_type="text/plain",
    )

    hass.bus.async_fire("test_event", {"url": "http://example.com"})
    await hass.async_block_till_done()
    expected_state = dt_util.utcnow().isoformat()
    await _assert_state(
        hass,
        hass_client,
        expected_state,
        imgbytes_jpg,
        expected_entity_picture="http://example2.com",
    )
