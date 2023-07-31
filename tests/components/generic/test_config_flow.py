"""Test The generic (IP Camera) config flow."""
import contextlib
import errno
from http import HTTPStatus
import os.path
from unittest.mock import AsyncMock, PropertyMock, patch

import httpx
import pytest
import respx

from homeassistant import config_entries
from homeassistant.components.camera import async_get_image
from homeassistant.components.generic.config_flow import slug
from homeassistant.components.generic.const import (
    CONF_CONFIRMED_OK,
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DOMAIN,
)
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
)
from homeassistant.components.stream.worker import StreamWorkerError
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

TESTDATA = {
    CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
    CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_USERNAME: "fred_flintstone",
    CONF_PASSWORD: "bambam",
    CONF_FRAMERATE: 5,
    CONF_VERIFY_SSL: False,
}

TESTDATA_OPTIONS = {
    CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
    **TESTDATA,
}

TESTDATA_YAML = {
    CONF_NAME: "Yaml Defined Name",
    **TESTDATA,
}


@respx.mock
async def test_form(
    hass: HomeAssistant,
    fakeimgbytes_png,
    hass_client: ClientSessionGenerator,
    user_flow,
    mock_create_stream,
) -> None:
    """Test the form with a normal set of settings."""

    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    with mock_create_stream as mock_setup, patch(
        "homeassistant.components.generic.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        client = await hass_client()
        preview_id = result1["flow_id"]
        # Check the preview image works.
        resp = await client.get(f"/api/generic/preview_flow_image/{preview_id}?t=1")
        assert resp.status == HTTPStatus.OK
        assert await resp.read() == fakeimgbytes_png
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127_0_0_1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/png",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()
    # Check that the preview image is disabled after.
    resp = await client.get(f"/api/generic/preview_flow_image/{preview_id}")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@respx.mock
async def test_form_only_stillimage(
    hass: HomeAssistant, fakeimg_png, user_flow
) -> None:
    """Test we complete ok if the user wants still images only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    with patch("homeassistant.components.generic.async_setup_entry", return_value=True):
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        await hass.async_block_till_done()
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127_0_0_1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/png",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    assert respx.calls.call_count == 1


@respx.mock
async def test_form_reject_still_preview(
    hass: HomeAssistant, fakeimgbytes_png, mock_create_stream, user_flow
) -> None:
    """Test we go back to the config screen if the user rejects the still preview."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    with mock_create_stream:
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "user_confirm_still"
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        user_input={CONF_CONFIRMED_OK: False},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"


@respx.mock
async def test_form_still_preview_cam_off(
    hass: HomeAssistant,
    fakeimg_png,
    mock_create_stream,
    user_flow,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test camera errors are triggered during preview."""
    with patch(
        "homeassistant.components.generic.camera.GenericCamera.is_on",
        new_callable=PropertyMock(return_value=False),
    ), mock_create_stream:
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        preview_id = result1["flow_id"]
        # Try to view the image, should be unavailable.
        client = await hass_client()
        resp = await client.get(f"/api/generic/preview_flow_image/{preview_id}?t=1")
    assert resp.status == HTTPStatus.SERVICE_UNAVAILABLE


@respx.mock
async def test_form_only_stillimage_gif(
    hass: HomeAssistant, fakeimg_gif, user_flow
) -> None:
    """Test we complete ok if the user wants a gif."""
    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    with patch("homeassistant.components.generic.async_setup_entry", return_value=True):
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["options"][CONF_CONTENT_TYPE] == "image/gif"


@respx.mock
async def test_form_only_svg_whitespace(
    hass: HomeAssistant, fakeimgbytes_svg, user_flow
) -> None:
    """Test we complete ok if svg starts with whitespace, issue #68889."""
    fakeimgbytes_wspace_svg = bytes("  \n ", encoding="utf-8") + fakeimgbytes_svg
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_wspace_svg)
    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    with patch("homeassistant.components.generic.async_setup_entry", return_value=True):
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY


@respx.mock
@pytest.mark.parametrize(
    "image_file",
    [
        ("sample1_animate.png"),
        ("sample2_jpeg_odd_header.jpg"),
        ("sample3_jpeg_odd_header.jpg"),
        ("sample4_K5-60mileAnim-320x240.gif"),
        ("sample5_webp.webp"),
    ],
)
async def test_form_only_still_sample(
    hass: HomeAssistant, user_flow, image_file
) -> None:
    """Test various sample images #69037."""
    image_path = os.path.join(os.path.dirname(__file__), image_file)
    with open(image_path, "rb") as image:
        respx.get("http://127.0.0.1/testurl/1").respond(stream=image.read())
    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    with patch("homeassistant.components.generic.async_setup_entry", return_value=True):
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY


@respx.mock
@pytest.mark.parametrize(
    ("template", "url", "expected_result", "expected_errors"),
    [
        # Test we can handle templates in strange parts of the url, #70961.
        (
            "http://localhost:812{{3}}/static/icons/favicon-apple-180x180.png",
            "http://localhost:8123/static/icons/favicon-apple-180x180.png",
            "user_confirm_still",
            None,
        ),
        (
            "{% if 1 %}https://bla{% else %}https://yo{% endif %}",
            "https://bla/",
            "user_confirm_still",
            None,
        ),
        (
            "http://{{example.org",
            "http://example.org",
            "user",
            {"still_image_url": "template_error"},
        ),
        (
            "invalid1://invalid:4\\1",
            "invalid1://invalid:4%5c1",
            "user",
            {"still_image_url": "malformed_url"},
        ),
        (
            "relative/urls/are/not/allowed.jpg",
            "relative/urls/are/not/allowed.jpg",
            "user",
            {"still_image_url": "relative_url"},
        ),
    ],
)
async def test_still_template(
    hass: HomeAssistant,
    user_flow,
    fakeimgbytes_png,
    template,
    url,
    expected_result,
    expected_errors,
) -> None:
    """Test we can handle various templates."""
    with contextlib.suppress(httpx.InvalidURL):
        # There is no need to mock the request if its an
        # invalid url because we will never make the request
        respx.get(url).respond(stream=fakeimgbytes_png)
    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    data[CONF_STILL_IMAGE_URL] = template
    with patch("homeassistant.components.generic.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        await hass.async_block_till_done()
    assert result2["step_id"] == expected_result
    assert result2.get("errors") == expected_errors


@respx.mock
async def test_form_rtsp_mode(
    hass: HomeAssistant, fakeimg_png, user_flow, mock_create_stream
) -> None:
    """Test we complete ok if the user enters a stream url."""
    data = TESTDATA.copy()
    data[CONF_RTSP_TRANSPORT] = "tcp"
    data[CONF_STREAM_SOURCE] = "rtsp://127.0.0.1/testurl/2"
    with mock_create_stream as mock_setup, patch(
        "homeassistant.components.generic.async_setup_entry", return_value=True
    ):
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"], data
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127_0_0_1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_STREAM_SOURCE: "rtsp://127.0.0.1/testurl/2",
        CONF_RTSP_TRANSPORT: "tcp",
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/png",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1


async def test_form_only_stream(
    hass: HomeAssistant, fakeimgbytes_jpg, user_flow, mock_create_stream
) -> None:
    """Test we complete ok if the user wants stream only."""
    data = TESTDATA.copy()
    data.pop(CONF_STILL_IMAGE_URL)
    data[CONF_STREAM_SOURCE] = "rtsp://user:pass@127.0.0.1/testurl/2"
    with mock_create_stream as mock_setup:
        result1 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            data,
        )
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "user_confirm_still"
        result3 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={CONF_CONFIRMED_OK: True},
        )
        await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "127_0_0_1"
    assert result3["options"] == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_STREAM_SOURCE: "rtsp://user:pass@127.0.0.1/testurl/2",
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/jpeg",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.generic.camera.GenericCamera.async_camera_image",
        return_value=fakeimgbytes_jpg,
    ):
        image_obj = await async_get_image(hass, "camera.127_0_0_1")
        assert image_obj.content == fakeimgbytes_jpg
    assert len(mock_setup.mock_calls) == 1


async def test_form_still_and_stream_not_provided(
    hass: HomeAssistant, user_flow
) -> None:
    """Test we show a suitable error if neither still or stream URL are provided."""
    result2 = await hass.config_entries.flow.async_configure(
        user_flow["flow_id"],
        {
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_FRAMERATE: 5,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "no_still_image_or_stream_url"}


@respx.mock
async def test_form_image_timeout(
    hass: HomeAssistant, user_flow, mock_create_stream
) -> None:
    """Test we handle invalid image timeout."""
    respx.get("http://127.0.0.1/testurl/1").side_effect = [
        httpx.TimeoutException,
    ]

    with mock_create_stream:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "unable_still_load"}


@respx.mock
async def test_form_stream_invalidimage(
    hass: HomeAssistant, user_flow, mock_create_stream
) -> None:
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=b"invalid")
    with mock_create_stream:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "invalid_still_image"}


@respx.mock
async def test_form_stream_invalidimage2(
    hass: HomeAssistant, user_flow, mock_create_stream
) -> None:
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(content=None)
    with mock_create_stream:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "unable_still_load"}


@respx.mock
async def test_form_stream_invalidimage3(
    hass: HomeAssistant, user_flow, mock_create_stream
) -> None:
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(content=bytes([0xFF]))
    with mock_create_stream:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "invalid_still_image"}


@respx.mock
async def test_form_stream_timeout(hass: HomeAssistant, fakeimg_png, user_flow) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.generic.config_flow.create_stream"
    ) as create_stream:
        create_stream.return_value.start = AsyncMock()
        create_stream.return_value.add_provider.return_value.part_recv = AsyncMock()
        create_stream.return_value.add_provider.return_value.part_recv.return_value = (
            False
        )
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "timeout"}


@respx.mock
async def test_form_stream_worker_error(
    hass: HomeAssistant, fakeimg_png, user_flow
) -> None:
    """Test we handle a StreamWorkerError and pass the message through."""
    with patch(
        "homeassistant.components.generic.config_flow.create_stream",
        side_effect=StreamWorkerError("Some message"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "Some message"}


@respx.mock
async def test_form_stream_permission_error(
    hass: HomeAssistant, fakeimgbytes_png, user_flow
) -> None:
    """Test we handle permission error."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    with patch(
        "homeassistant.components.generic.config_flow.create_stream",
        side_effect=PermissionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_not_permitted"}


@respx.mock
async def test_form_no_route_to_host(
    hass: HomeAssistant, fakeimg_png, user_flow
) -> None:
    """Test we handle no route to host."""
    with patch(
        "homeassistant.components.generic.config_flow.create_stream",
        side_effect=OSError(errno.EHOSTUNREACH, "No route to host"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_no_route_to_host"}


@respx.mock
async def test_form_stream_io_error(
    hass: HomeAssistant, fakeimg_png, user_flow
) -> None:
    """Test we handle no io error when setting up stream."""
    with patch(
        "homeassistant.components.generic.config_flow.create_stream",
        side_effect=OSError(errno.EIO, "Input/output error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_io_error"}


@respx.mock
async def test_form_oserror(hass: HomeAssistant, fakeimg_png, user_flow) -> None:
    """Test we handle OS error when setting up stream."""
    with patch(
        "homeassistant.components.generic.config_flow.create_stream",
        side_effect=OSError("Some other OSError"),
    ), pytest.raises(OSError):
        await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )


@respx.mock
async def test_options_template_error(
    hass: HomeAssistant, fakeimgbytes_png, mock_create_stream
) -> None:
    """Test the options flow with a template error."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    respx.get("http://127.0.0.1/testurl/2").respond(stream=fakeimgbytes_png)

    mock_entry = MockConfigEntry(
        title="Test Camera",
        domain=DOMAIN,
        data={},
        options=TESTDATA,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # try updating the still image url
    data = TESTDATA.copy()
    data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/2"
    with mock_create_stream:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=data,
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "confirm_still"

        result2a = await hass.config_entries.options.async_configure(
            result2["flow_id"], user_input={CONF_CONFIRMED_OK: True}
        )
        assert result2a["type"] == FlowResultType.CREATE_ENTRY

        result3 = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "init"

        # verify that an invalid template reports the correct UI error.
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/{{1/0}}"
        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input=data,
        )
        assert result4.get("type") == FlowResultType.FORM
        assert result4["errors"] == {"still_image_url": "template_error"}

        # verify that an invalid template reports the correct UI error.
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/1"
        data[CONF_STREAM_SOURCE] = "http://127.0.0.2/testurl/{{1/0}}"
        result5 = await hass.config_entries.options.async_configure(
            result4["flow_id"],
            user_input=data,
        )

        assert result5.get("type") == FlowResultType.FORM
        assert result5["errors"] == {"stream_source": "template_error"}

        # verify that an relative stream url is rejected.
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/1"
        data[CONF_STREAM_SOURCE] = "relative/stream.mjpeg"
        result6 = await hass.config_entries.options.async_configure(
            result5["flow_id"],
            user_input=data,
        )
        assert result6.get("type") == FlowResultType.FORM
        assert result6["errors"] == {"stream_source": "relative_url"}

        # verify that an malformed stream url is rejected.
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/1"
        data[CONF_STREAM_SOURCE] = "http://example.com:45:56"
        result7 = await hass.config_entries.options.async_configure(
            result6["flow_id"],
            user_input=data,
        )
    assert result7.get("type") == FlowResultType.FORM
    assert result7["errors"] == {"stream_source": "malformed_url"}


async def test_slug(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test that the slug function generates an error in case of invalid template.

    Other paths in the slug function are already tested by other tests.
    """
    result = slug(hass, "http://127.0.0.2/testurl/{{1/0}}")
    assert result is None
    assert "Syntax error in" in caplog.text

    result = slug(hass, "http://example.com:999999999999/stream")
    assert result is None
    assert "Syntax error in" in caplog.text


@respx.mock
async def test_options_only_stream(
    hass: HomeAssistant, fakeimgbytes_png, mock_create_stream
) -> None:
    """Test the options flow without a still_image_url."""
    respx.get("http://127.0.0.1/testurl/2").respond(stream=fakeimgbytes_png)
    data = TESTDATA.copy()
    data.pop(CONF_STILL_IMAGE_URL)

    mock_entry = MockConfigEntry(
        title="Test Camera",
        domain=DOMAIN,
        data={},
        options=data,
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # try updating the config options
    with mock_create_stream:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=data,
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "confirm_still"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={CONF_CONFIRMED_OK: True}
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_CONTENT_TYPE] == "image/jpeg"


# These below can be deleted after deprecation period is finished.
@respx.mock
async def test_import(hass: HomeAssistant, fakeimg_png) -> None:
    """Test configuration.yaml import used during migration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
    )
    # duplicate import should be aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yaml Defined Name"
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_generic"
    )
    assert issue.translation_key == "deprecated_yaml"

    # Any name defined in yaml should end up as the entity id.
    assert hass.states.get("camera.yaml_defined_name")
    assert result2["type"] == FlowResultType.ABORT


# These above can be deleted after deprecation period is finished.


async def test_unload_entry(hass: HomeAssistant, fakeimg_png) -> None:
    """Test unloading the generic IP Camera entry."""
    mock_entry = MockConfigEntry(domain=DOMAIN, options=TESTDATA)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is config_entries.ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_reload_on_title_change(hass: HomeAssistant) -> None:
    """Test the integration gets reloaded when the title is updated."""

    test_data = TESTDATA_OPTIONS
    test_data[CONF_CONTENT_TYPE] = "image/png"
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="54321", options=test_data, title="My Title"
    )
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is config_entries.ConfigEntryState.LOADED
    assert hass.states.get("camera.my_title").attributes["friendly_name"] == "My Title"

    hass.config_entries.async_update_entry(mock_entry, title="New Title")
    assert mock_entry.title == "New Title"
    await hass.async_block_till_done()

    assert hass.states.get("camera.my_title").attributes["friendly_name"] == "New Title"


async def test_migrate_existing_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that existing ids are migrated for issue #70568."""

    test_data = TESTDATA_OPTIONS.copy()
    test_data[CONF_CONTENT_TYPE] = "image/png"
    old_unique_id = "54321"
    entity_id = "camera.sample_camera"

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=old_unique_id, options=test_data, title="My Title"
    )
    new_unique_id = mock_entry.entry_id
    mock_entry.add_to_hass(hass)

    entity_entry = entity_registry.async_get_or_create(
        "camera",
        DOMAIN,
        old_unique_id,
        suggested_object_id="sample camera",
        config_entry=mock_entry,
    )
    assert entity_entry.entity_id == entity_id
    assert entity_entry.unique_id == old_unique_id

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry.unique_id == new_unique_id


@respx.mock
async def test_use_wallclock_as_timestamps_option(
    hass: HomeAssistant, fakeimg_png, mock_create_stream
) -> None:
    """Test the use_wallclock_as_timestamps option flow."""

    mock_entry = MockConfigEntry(
        title="Test Camera",
        domain=DOMAIN,
        data={},
        options=TESTDATA,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    with patch(
        "homeassistant.components.generic.async_setup_entry", return_value=True
    ), mock_create_stream:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USE_WALLCLOCK_AS_TIMESTAMPS: True, **TESTDATA},
        )
    assert result2["type"] == FlowResultType.FORM
    # Test what happens if user rejects the preview
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={CONF_CONFIRMED_OK: False}
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "init"
    with patch(
        "homeassistant.components.generic.async_setup_entry", return_value=True
    ), mock_create_stream:
        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input={CONF_USE_WALLCLOCK_AS_TIMESTAMPS: True, **TESTDATA},
        )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "confirm_still"
    result5 = await hass.config_entries.options.async_configure(
        result4["flow_id"],
        user_input={CONF_CONFIRMED_OK: True},
    )
    assert result5["type"] == FlowResultType.CREATE_ENTRY
