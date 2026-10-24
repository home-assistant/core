"""The tests for the Template image platform."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from io import BytesIO
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiofiles.os
import httpx2
from PIL import Image
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    assert_setup_component,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant.typing import ClientSessionGenerator
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import image
from homeassistant.components.input_text import (
    ATTR_VALUE as INPUT_TEXT_ATTR_VALUE,
    DOMAIN as INPUT_TEXT_DOMAIN,
    SERVICE_SET_VALUE as INPUT_TEXT_SERVICE_SET_VALUE,
)
from homeassistant.components.template import DOMAIN
from homeassistant.components.template.image import DEFAULT_NAME, ImageExtraStoredData
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    CONF_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.core_config import Config
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_attributes_template,
    assert_extra_template_attributes,
    assert_state_and_attributes,
    async_trigger,
    make_test_trigger,
    setup_entity,
)

_DEFAULT = object()
_TEST_IMAGE = "image.template_image"
_URL_INPUT_TEXT = "input_text.url"

TEST_STATE_ENTITY_ID = "sensor.test_state"

TEST_IMAGE = TemplatePlatformSetup(
    image.DOMAIN,
    "test_template_image",
    make_test_trigger(TEST_STATE_ENTITY_ID, _TEST_IMAGE, _URL_INPUT_TEXT),
)


@pytest.fixture(autouse=True)
def images_cache_dir(tmp_path: Path) -> Generator[Path]:
    """Keep the image cache out of the shared testing config directory."""
    cache_dir = tmp_path / ".cache"
    with patch.object(
        Config, "cache_path", lambda _, *path: str(cache_dir.joinpath(*path))
    ):
        yield cache_dir / DOMAIN / "images"


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


def _image_bytes(image_format: str) -> bytes:
    """Return a 1x1 image in the given format."""
    buf = BytesIO()
    Image.new("RGB", (1, 1), 100).save(buf, format=image_format)
    return bytes(buf.getbuffer())


_CACHED_JPEG = _image_bytes("jpeg")


def _write_cache(
    images_cache_dir: Path,
    content: bytes,
    *,
    content_type: str = "image/jpeg",
    image_url: str = "http://example2.com",
    image_last_updated: str = "2021-07-13T00:00:00+00:00",
) -> None:
    """Write a cached image with its metadata header."""
    images_cache_dir.mkdir(parents=True)
    header = json_dumps(
        {
            "image_url": image_url,
            "image_last_updated": image_last_updated,
            "content_type": content_type,
        }
    )
    (images_cache_dir / f"{TEST_IMAGE.entity_id}.bin").write_bytes(
        header.encode() + b"\n" + content
    )


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
@pytest.mark.freeze_time("2024-07-09 00:00:00+00:00")
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    imgbytes_jpg,
) -> None:
    """Test the config flow."""

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "http://example.com",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("image.my_template")
    assert state is not None
    assert state.state == "2024-07-09T00:00:00+00:00"


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
            DOMAIN,
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
            DOMAIN,
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
            DOMAIN,
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


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id configuration."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            DOMAIN,
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

    entry = entity_registry.async_get(_TEST_IMAGE)
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
            DOMAIN,
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
    respx.get("http://example.com").side_effect = httpx2.TimeoutException

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            DOMAIN,
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
            DOMAIN,
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
        DOMAIN,
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
        DOMAIN,
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


@respx.mock
async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for image template."""

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "http://example.com",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("image.mock_title_my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_extra_template_attributes(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test extra attributes."""
    await assert_extra_template_attributes(
        hass,
        TEST_IMAGE,
        style,
        {
            "url": "{{ 'http://example.com' }}",
        },
    )


@pytest.mark.parametrize("attribute", list(image.ImageEntityStateAttribute))
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_blocked_template_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: image.ImageEntityStateAttribute,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked extra attributes."""
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        0,
        {
            "url": "{{ 'http://example.com' }}",
            "attributes": {str(attribute): "{{ 'does not matter' }}"},
        },
    )
    assert (
        f"Unsupported attribute(s) found for {DEFAULT_NAME}: {attribute}" in caplog.text
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes as a single template."""
    await assert_attributes_template(
        hass,
        TEST_IMAGE,
        style,
        {
            "url": "{{ 'http://example.com' }}",
        },
        caplog,
    )


@pytest.mark.parametrize("attribute", list(image.ImageEntityStateAttribute))
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template_with_blocked_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: image.ImageEntityStateAttribute,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked attributes for a single attributes template."""
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        {
            "url": "{{ 'http://example.com' }}",
            "attributes": f"{{{{ dict({attribute}='does not matter') }}}}",
        },
    )

    await async_trigger(hass, "sensor.test_extra_attributes", "anything")

    error = f"Unsupported attribute(s) found for {TEST_IMAGE.entity_id}: {attribute}"
    assert error in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("cached_image", "content_type"),
    [
        pytest.param(_image_bytes("jpeg"), "image/jpeg", id="jpeg"),
        pytest.param(_image_bytes("png"), "image/png", id="png"),
        pytest.param(
            b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml", id="svg"
        ),
    ],
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_restore_state(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    cached_image: bytes,
    content_type: str,
    imgbytes_jpg: bytes,
) -> None:
    """Test restoring trigger template image."""
    _write_cache(images_cache_dir, cached_image, content_type=content_type)

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example2.com",
    }

    fake_state = State(
        TEST_IMAGE.entity_id,
        "2021-07-13T00:00:00+00:00",
    )
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        cached_image,
        entity_id=TEST_IMAGE.entity_id,
        expected_content_type=content_type,
    )

    await async_trigger(hass, "sensor.test_state", "http://example.com")

    await _assert_state(
        hass,
        hass_client,
        "2026-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
    assert respx.get("http://example.com").call_count == 1


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("saved_state", "initial_state"),
    [
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        (STATE_UNKNOWN, STATE_UNKNOWN),
    ],
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_restore_bad_state_does_not_restore(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    saved_state: str,
    initial_state: str,
    imgbytes_jpg: bytes,
    imgbytes2_jpg: bytes,
) -> None:
    """Test restore state does not restore."""

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example2.com",
    }

    fake_state = State(TEST_IMAGE.entity_id, saved_state)
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    assert_state_and_attributes(
        hass,
        TEST_IMAGE,
        initial_state,
    )

    await async_trigger(hass, "sensor.test_state", "http://example.com")

    await _assert_state(
        hass,
        hass_client,
        "2026-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
    assert respx.get("http://example.com").call_count == 1


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_saving_state(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
    hass_storage: dict[str, Any],
) -> None:
    """Test restore saved state."""

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example.com",
    }

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == TEST_IMAGE.entity_id

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == saved_extra_data

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    header, _, content = (
        (images_cache_dir / f"{TEST_IMAGE.entity_id}.bin").read_bytes().partition(b"\n")
    )
    assert json_loads_object(header) == {
        "image_url": "http://example.com",
        "image_last_updated": "2021-07-13T00:00:00+00:00",
        "content_type": "image/jpeg",
    }
    assert content == imgbytes_jpg


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("saved_extra_data"),
    [
        pytest.param(
            {
                "image_last_update": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
                },
                "image_url": "http://example.com",
            },
            id="missing_image_last_updated",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__ty": "<class 'datetime.datetime'>",
                    "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
                },
                "image_url": "http://example.com",
            },
            id="missing_type",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
                },
                "image_ur": "http://example.com",
            },
            id="missing_image_url",
        ),
        pytest.param(
            {
                "image_last_updated": "2021-07-13T00:00:00+00:00",
                "image_url": "http://example.com",
            },
            id="image_last_updated_not_dict",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'str'>",
                    "isoformat": "2021-07-13T00:00:00+00:00",
                },
                "image_url": "http://example.com",
            },
            id="unknown_type",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": 123,
                },
                "image_url": "http://example.com",
            },
            id="isoformat_not_str",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": "not a datetime",
                },
                "image_url": "http://example.com",
            },
            id="isoformat_unparsable",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": "2021-13-45T00:00:00+00:00",
                },
                "image_url": "http://example.com",
            },
            id="isoformat_invalid_date",
        ),
        pytest.param(
            {
                "image_last_updated": {
                    "__type": "<class 'datetime.datetime'>",
                    "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
                },
                "image_url": 5,
            },
            id="image_url_not_str",
        ),
    ],
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_restore_bad_extra_data_does_not_restore(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    saved_extra_data: dict,
    imgbytes_jpg: bytes,
) -> None:
    """Test restore state does not restore with bad extra data."""

    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )

    fake_state = State(TEST_IMAGE.entity_id, "2021-07-13T00:00:00+00:00")
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    assert_state_and_attributes(
        hass,
        TEST_IMAGE,
        STATE_UNKNOWN,
    )

    await async_trigger(hass, "sensor.test_state", "http://example.com")

    await _assert_state(
        hass,
        hass_client,
        "2026-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
    assert respx.get("http://example.com").call_count == 1


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param(
            ImageExtraStoredData(
                image_last_updated=datetime(2021, 7, 13, tzinfo=UTC),
                image_url="http://example.com",
            ),
            id="populated",
        ),
        pytest.param(
            ImageExtraStoredData(image_last_updated=None, image_url=None),
            id="empty",
        ),
    ],
)
def test_extra_stored_data_round_trip(extra_data: ImageExtraStoredData) -> None:
    """Test extra stored data survives serialization to restore state."""
    assert (
        ImageExtraStoredData.from_dict(
            json_loads_object(json_dumps(extra_data.as_dict()))
        )
        == extra_data
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
async def test_stale_cache_removed_at_stop(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test a previous image is not kept when the current image was never fetched."""
    _write_cache(images_cache_dir, imgbytes_jpg)
    cache_file = images_cache_dir / f"{TEST_IMAGE.entity_id}.bin"

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert not cache_file.exists()


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "cache_file_content",
    [
        pytest.param(
            b'{"image_url":"http://example2.com",'
            b'"image_last_updated":"2021-07-12T00:00:00+00:00",'
            b'"content_type":"image/jpeg"}\n' + _CACHED_JPEG,
            id="different_last_updated",
        ),
        pytest.param(
            b'{"image_url":"http://example3.com",'
            b'"image_last_updated":"2021-07-13T00:00:00+00:00",'
            b'"content_type":"image/jpeg"}\n' + _CACHED_JPEG,
            id="different_url",
        ),
        pytest.param(
            b'{"image_url":"http://example2.com",'
            b'"image_last_updated":"2021-07-13T00:00:00+00:00",'
            b'"content_type":"text/plain"}\n' + _CACHED_JPEG,
            id="invalid_content_type",
        ),
        pytest.param(
            b'{"image_url":"http://example2.com",'
            b'"image_last_updated":"not a datetime",'
            b'"content_type":"image/jpeg"}\n' + _CACHED_JPEG,
            id="invalid_last_updated",
        ),
        pytest.param(
            b'{"image_url":"http://example2.com","content_type":"image/jpeg"}\n'
            + _CACHED_JPEG,
            id="missing_key",
        ),
        pytest.param(_CACHED_JPEG, id="no_header"),
        pytest.param(
            b'{"image_url":"http://example2.com",'
            b'"image_last_updated":"2021-07-13T00:00:00+00:00",'
            b'"content_type":"image/jpeg"}\n',
            id="empty_content",
        ),
    ],
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_restore_mismatched_cache_not_restored(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    cache_file_content: bytes,
    imgbytes_jpg: bytes,
    imgbytes2_jpg: bytes,
) -> None:
    """Test a cached image that doesn't match the restored state is not used."""
    images_cache_dir.mkdir(parents=True)
    (images_cache_dir / f"{TEST_IMAGE.entity_id}.bin").write_bytes(cache_file_content)
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/jpeg"
    )

    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example2.com",
    }
    fake_state = State(TEST_IMAGE.entity_id, "2021-07-13T00:00:00+00:00")
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    # The restored URL is fetched instead of serving the cached bytes.
    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes2_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
    assert respx.get("http://example2.com").call_count == 1


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_cache_cleared_while_saving(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test the image being saved is not affected by an update during the write."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")
    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )

    entity = hass.data[image.DATA_COMPONENT].get_entity(TEST_IMAGE.entity_id)
    makedirs = aiofiles.os.makedirs

    async def _clear_cache_then_makedirs(*args: Any, **kwargs: Any) -> None:
        entity._cached_image = None
        await makedirs(*args, **kwargs)

    with patch("aiofiles.os.makedirs", _clear_cache_then_makedirs):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    cache_file = images_cache_dir / f"{TEST_IMAGE.entity_id}.bin"
    assert list(images_cache_dir.iterdir()) == [cache_file]
    assert cache_file.read_bytes().partition(b"\n")[2] == imgbytes_jpg


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_cache_write_error_does_not_block_removal(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    imgbytes_jpg: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed cache write is logged and the entity is still removed."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")
    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )

    entity = hass.data[image.DATA_COMPONENT].get_entity(TEST_IMAGE.entity_id)
    with patch("aiofiles.open", side_effect=OSError("No space left on device")):
        await entity.async_remove()

    assert hass.states.get(TEST_IMAGE.entity_id) is None
    assert "Unable to save image cache" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_cache_read_error_does_not_block_setup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes2_jpg: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreadable cache is logged and the restored URL is fetched instead."""
    # Opening a directory raises IsADirectoryError, an OSError.
    (images_cache_dir / f"{TEST_IMAGE.entity_id}.bin").mkdir(parents=True)
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/jpeg"
    )

    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example2.com",
    }
    fake_state = State(TEST_IMAGE.entity_id, "2021-07-13T00:00:00+00:00")
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes2_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
    assert "Unable to read image cache" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_overlapping_cache_dumps(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
    imgbytes2_jpg: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a second cache dump waits for the one in progress."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")
    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )

    entity = hass.data[image.DATA_COMPONENT].get_entity(TEST_IMAGE.entity_id)
    makedirs = aiofiles.os.makedirs
    first_dump_started = asyncio.Event()
    release_first_dump = asyncio.Event()
    makedirs_calls = 0

    async def _makedirs(*args: Any, **kwargs: Any) -> None:
        nonlocal makedirs_calls
        makedirs_calls += 1
        if makedirs_calls == 1:
            first_dump_started.set()
            await release_first_dump.wait()
        await makedirs(*args, **kwargs)

    with patch("aiofiles.os.makedirs", _makedirs):
        first_dump = hass.async_create_task(entity.async_dump_cache())
        await first_dump_started.wait()

        entity._cached_image = image.Image("image/jpeg", imgbytes2_jpg)
        second_dump = hass.async_create_task(entity.async_dump_cache())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        # The second dump must not touch the temp file while the first is writing.
        assert makedirs_calls == 1

        release_first_dump.set()
        await first_dump
        await second_dump

    cache_file = images_cache_dir / f"{TEST_IMAGE.entity_id}.bin"
    assert list(images_cache_dir.iterdir()) == [cache_file]
    assert cache_file.read_bytes().partition(b"\n")[2] == imgbytes2_jpg
    assert "Unable to save image cache" not in caplog.text


@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_cache_follows_registry_id_across_rename(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test the cached image is restored after disabling, renaming and re-enabling."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    hass.states.async_set(TEST_STATE_ENTITY_ID, "http://example.com")
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id="image.my_template",
    )
    registry_id = entity_registry.async_get("image.my_template").id

    entity_registry.async_update_entity(
        "image.my_template", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert list(images_cache_dir.iterdir()) == [images_cache_dir / f"{registry_id}.bin"]

    entity_registry.async_update_entity(
        "image.my_template", new_entity_id="image.renamed"
    )
    entity_registry.async_update_entity("image.renamed", disabled_by=None)
    # The URL source is gone, so only the cache can provide the image.
    hass.states.async_remove(TEST_STATE_ENTITY_ID)
    await hass.config_entries.async_reload(template_config_entry.entry_id)
    await hass.async_block_till_done()

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id="image.renamed",
    )
    assert respx.get("http://example.com").call_count == 1


@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_cache_deleted_with_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test the cached image is deleted when the entity is deleted."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "http://example.com",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id="image.my_template",
    )
    entity = hass.data[image.DATA_COMPONENT].get_entity("image.my_template")
    await entity.async_dump_cache()
    assert list(images_cache_dir.iterdir()) == [
        images_cache_dir / f"{entity_registry.async_get('image.my_template').id}.bin"
    ]

    entity_registry.async_remove("image.my_template")
    await hass.async_block_till_done()

    assert hass.states.get("image.my_template") is None
    assert list(images_cache_dir.iterdir()) == []


@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_orphaned_cache_pruned_once_at_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test cache files that can't be restored are pruned at integration setup."""
    registered = entity_registry.async_get_or_create(
        image.DOMAIN, DOMAIN, "registered_image"
    )
    mock_restore_cache(hass, (State("image.unregistered", "2026-01-01T00:00:00"),))

    images_cache_dir.mkdir(parents=True)
    # Files of restorable entities are kept even after a long shutdown.
    expired = (dt_util.utcnow() - timedelta(days=30)).timestamp()
    kept = [
        images_cache_dir / f"{registered.id}.bin",
        images_cache_dir / "image.unregistered.bin",
    ]
    for path in (
        *kept,
        images_cache_dir / "0123456789abcdef0123456789abcdef.bin",
        images_cache_dir / "image.removed.bin",
        images_cache_dir / "image.failed_write.tmp",
    ):
        path.write_bytes(imgbytes_jpg)
        os.utime(path, (expired, expired))

    # No template image is configured, the cache is still pruned.
    assert await setup.async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert sorted(images_cache_dir.iterdir()) == sorted(kept)

    # Later setups, such as reloads, don't prune again.
    orphan = images_cache_dir / "image.removed.bin"
    orphan.write_bytes(imgbytes_jpg)
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "http://example.com",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    assert sorted(images_cache_dir.iterdir()) == sorted([*kept, orphan])


async def test_cache_prune_error_does_not_block_setup(
    hass: HomeAssistant,
    images_cache_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreadable cache directory is logged and the image still loads."""
    images_cache_dir.parent.mkdir(parents=True)
    # Listing a file as a directory raises NotADirectoryError, an OSError.
    images_cache_dir.write_bytes(b"")

    await setup_entity(
        hass,
        TEST_IMAGE,
        ConfigurationStyle.MODERN,
        1,
        config={"url": "{{ 'http://example.com' }}"},
    )

    assert hass.states.get(TEST_IMAGE.entity_id) is not None
    assert "Unable to prune image cache" in caplog.text


@pytest.mark.parametrize(
    "disabled_by", [None, er.RegistryEntryDisabler.USER], ids=["enabled", "disabled"]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_cache_deleted_with_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test the cached image is deleted when the template helper is deleted."""
    respx.get("http://example.com").respond(
        stream=imgbytes_jpg, content_type="image/jpeg"
    )
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "image",
            "url": "http://example.com",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes_jpg,
        entity_id="image.my_template",
    )
    entity = hass.data[image.DATA_COMPONENT].get_entity("image.my_template")
    await entity.async_dump_cache()
    entity_registry.async_update_entity("image.my_template", disabled_by=disabled_by)
    await hass.async_block_till_done()
    assert list(images_cache_dir.iterdir()) == [
        images_cache_dir / f"{entity_registry.async_get('image.my_template').id}.bin"
    ]

    await hass.config_entries.async_remove(template_config_entry.entry_id)
    await hass.async_block_till_done()

    assert list(images_cache_dir.iterdir()) == []


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_url_changed_during_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes_jpg: bytes,
) -> None:
    """Test an image downloaded for a previous URL is not kept."""
    download_started = asyncio.Event()
    release_download = asyncio.Event()

    async def _slow_download(request: httpx2.Request) -> httpx2.Response:
        download_started.set()
        await release_download.wait()
        return httpx2.Response(
            200, content=imgbytes_jpg, headers={"content-type": "image/jpeg"}
        )

    respx.get("http://example.com").mock(side_effect=_slow_download)
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")

    client = await hass_client()
    # Not tracked by hass, so async_trigger doesn't wait for the paused download.
    request = asyncio.create_task(
        client.get(f"/api/image_proxy/{TEST_IMAGE.entity_id}")
    )
    await download_started.wait()
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example2.com")
    release_download.set()
    resp = await request

    # The request still gets the image it asked for.
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == imgbytes_jpg
    entity = hass.data[image.DATA_COMPONENT].get_entity(TEST_IMAGE.entity_id)
    assert entity._cached_image is None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert not (images_cache_dir / f"{TEST_IMAGE.entity_id}.bin").exists()


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("outdated_status", "expected_status", "expected_content_type"),
    [
        pytest.param(HTTPStatus.OK, HTTPStatus.OK, "image/png", id="outdated_succeeds"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "text/plain",
            id="outdated_fails",
        ),
    ],
)
@respx.mock
@pytest.mark.freeze_time("2021-07-13 00:00:00+00:00")
async def test_outdated_download_keeps_current_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    style: ConfigurationStyle,
    outdated_status: HTTPStatus,
    expected_status: HTTPStatus,
    expected_content_type: str,
    imgbytes2_jpg: bytes,
) -> None:
    """Test a download for a previous URL finishing last keeps the current image."""
    download_started = asyncio.Event()
    release_download = asyncio.Event()
    outdated_image = _image_bytes("png")

    async def _slow_download(request: httpx2.Request) -> httpx2.Response:
        download_started.set()
        await release_download.wait()
        return httpx2.Response(
            outdated_status,
            content=outdated_image,
            headers={"content-type": "image/png"},
        )

    respx.get("http://example.com").mock(side_effect=_slow_download)
    respx.get("http://example2.com").respond(
        stream=imgbytes2_jpg, content_type="image/jpeg"
    )
    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example.com")

    client = await hass_client()
    # Not tracked by hass, so async_trigger doesn't wait for the paused download.
    outdated_request = asyncio.create_task(
        client.get(f"/api/image_proxy/{TEST_IMAGE.entity_id}")
    )
    await download_started.wait()
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "http://example2.com")
    resp = await client.get(f"/api/image_proxy/{TEST_IMAGE.entity_id}")
    assert resp.content_type == "image/jpeg"
    assert await resp.read() == imgbytes2_jpg

    release_download.set()
    resp = await outdated_request
    # The outdated image is served with its own content type.
    assert resp.status == expected_status
    assert resp.content_type == expected_content_type

    entity = hass.data[image.DATA_COMPONENT].get_entity(TEST_IMAGE.entity_id)
    assert entity._cached_image == image.Image("image/jpeg", imgbytes2_jpg)
    resp = await client.get(f"/api/image_proxy/{TEST_IMAGE.entity_id}")
    assert resp.content_type == "image/jpeg"
    assert await resp.read() == imgbytes2_jpg


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@respx.mock
@pytest.mark.freeze_time("2026-07-13 00:00:00+00:00")
async def test_restore_cache_after_unique_id_added(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    style: ConfigurationStyle,
    images_cache_dir: Path,
    imgbytes2_jpg: bytes,
) -> None:
    """Test the cache saved under the entity_id is restored once a unique_id is set."""
    _write_cache(images_cache_dir, imgbytes2_jpg)
    saved_extra_data = {
        "image_last_updated": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2021, 7, 13, 0, 0, 0, tzinfo=UTC).isoformat(),
        },
        "image_url": "http://example2.com",
    }
    fake_state = State(TEST_IMAGE.entity_id, "2021-07-13T00:00:00+00:00")
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))

    await setup_entity(
        hass,
        TEST_IMAGE,
        style,
        1,
        config={
            "default_entity_id": TEST_IMAGE.entity_id,
            "unique_id": "now_registered",
            "url": "{{ states('sensor.test_state') if 'sensor.test_state' | has_value else none }}",
        },
    )
    assert entity_registry.async_get(TEST_IMAGE.entity_id) is not None

    # example2.com isn't mocked, the image comes from the cache.
    await _assert_state(
        hass,
        hass_client,
        "2021-07-13T00:00:00+00:00",
        imgbytes2_jpg,
        entity_id=TEST_IMAGE.entity_id,
    )
