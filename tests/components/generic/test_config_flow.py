"""Test The generic (IP Camera) config flow."""

import errno
from unittest.mock import patch

import av
import httpx
import pytest
import respx

from homeassistant import config_entries, data_entry_flow, setup
import homeassistant.components.generic
from homeassistant.components.generic.const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_RTSP_TRANSPORT,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)

from tests.common import MockConfigEntry

TESTDATA = {
    CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
    CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_USERNAME: "fred_flintstone",
    CONF_PASSWORD: "bambam",
    CONF_FRAMERATE: 5,
    CONF_VERIFY_SSL: False,
}

TESTDATA_YAML = {
    CONF_NAME: "Yaml Defined Name",
    **TESTDATA,
}


@respx.mock
async def test_form(hass, fakeimg_png, mock_av_open, user_flow):
    """Test the form with a normal set of settings."""

    with mock_av_open as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "http://127.0.0.1/testurl/1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
        CONF_RTSP_TRANSPORT: None,
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/png",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1


@respx.mock
async def test_form_only_stillimage(hass, fakeimg_png, user_flow):
    """Test we complete ok if the user wants still images only."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    data = TESTDATA.copy()
    data.pop(CONF_STREAM_SOURCE)
    result2 = await hass.config_entries.flow.async_configure(
        user_flow["flow_id"],
        data,
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "http://127.0.0.1/testurl/1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_RTSP_TRANSPORT: None,
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: "image/png",
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()
    assert respx.calls.call_count == 1


@respx.mock
async def test_form_rtsp_mode(hass, fakeimg_png, mock_av_open, user_flow):
    """Test we complete ok if the user enters a stream url."""
    with mock_av_open as mock_setup:
        data = TESTDATA
        data[CONF_RTSP_TRANSPORT] = "tcp"
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"], data
        )
    assert "errors" not in result2, f"errors={result2['errors']}"
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "http://127.0.0.1/testurl/1"
    assert result2["options"] == {
        CONF_STILL_IMAGE_URL: "http://127.0.0.1/testurl/1",
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
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


async def test_form_only_stream(hass, mock_av_open):
    """Test we complete ok if the user wants stream only."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = TESTDATA.copy()
    data.pop(CONF_STILL_IMAGE_URL)
    with mock_av_open as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            data,
        )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "http://127.0.0.1/testurl/2"
    assert result2["options"] == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_STREAM_SOURCE: "http://127.0.0.1/testurl/2",
        CONF_RTSP_TRANSPORT: "tcp",
        CONF_USERNAME: "fred_flintstone",
        CONF_PASSWORD: "bambam",
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
        CONF_CONTENT_TYPE: None,
        CONF_FRAMERATE: 5,
        CONF_VERIFY_SSL: False,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1


async def test_form_still_and_stream_not_provided(hass, user_flow):
    """Test we show a suitable error if neither still or stream URL are provided."""
    result2 = await hass.config_entries.flow.async_configure(
        user_flow["flow_id"],
        {
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_FRAMERATE: 5,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "no_still_image_or_stream_url"}


@respx.mock
async def test_form_image_timeout(hass, mock_av_open, user_flow):
    """Test we handle invalid image timeout."""
    respx.get("http://127.0.0.1/testurl/1").side_effect = [
        httpx.TimeoutException,
    ]

    with mock_av_open:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "unable_still_load"}


@respx.mock
async def test_form_stream_invalidimage(hass, mock_av_open, user_flow):
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=b"invalid")
    with mock_av_open:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "invalid_still_image"}


@respx.mock
async def test_form_stream_invalidimage2(hass, mock_av_open, user_flow):
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(content=None)
    with mock_av_open:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "unable_still_load"}


@respx.mock
async def test_form_stream_invalidimage3(hass, mock_av_open, user_flow):
    """Test we handle invalid image when a stream is specified."""
    respx.get("http://127.0.0.1/testurl/1").respond(content=bytes([0xFF]))
    with mock_av_open:
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"still_image_url": "invalid_still_image"}


@respx.mock
async def test_form_stream_file_not_found(hass, fakeimg_png, user_flow):
    """Test we handle file not found."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=av.error.FileNotFoundError(0, 0),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_file_not_found"}


@respx.mock
async def test_form_stream_http_not_found(hass, fakeimg_png, user_flow):
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=av.error.HTTPNotFoundError(0, 0),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_http_not_found"}


@respx.mock
async def test_form_stream_timeout(hass, fakeimg_png, user_flow):
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=av.error.TimeoutError(0, 0),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "timeout"}


@respx.mock
async def test_form_stream_unauthorised(hass, fakeimg_png, user_flow):
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=av.error.HTTPUnauthorizedError(0, 0),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_unauthorised"}


@respx.mock
async def test_form_stream_novideo(hass, fakeimg_png, user_flow):
    """Test we handle invalid stream."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open", side_effect=KeyError()
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_no_video"}


@respx.mock
async def test_form_stream_permission_error(hass, fakeimgbytes_png, user_flow):
    """Test we handle permission error."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=PermissionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_not_permitted"}


@respx.mock
async def test_form_no_route_to_host(hass, fakeimg_png, user_flow):
    """Test we handle no route to host."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=OSError(errno.EHOSTUNREACH, "No route to host"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_no_route_to_host"}


@respx.mock
async def test_form_stream_io_error(hass, fakeimg_png, user_flow):
    """Test we handle no io error when setting up stream."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=OSError(errno.EIO, "Input/output error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"stream_source": "stream_io_error"}


@respx.mock
async def test_form_oserror(hass, fakeimg_png, user_flow):
    """Test we handle OS error when setting up stream."""
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=OSError("Some other OSError"),
    ), pytest.raises(OSError):
        await hass.config_entries.flow.async_configure(
            user_flow["flow_id"],
            TESTDATA,
        )


@respx.mock
async def test_options_template_error(hass, fakeimgbytes_png, mock_av_open):
    """Test the options flow with a template error."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    respx.get("http://127.0.0.1/testurl/2").respond(stream=fakeimgbytes_png)
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_entry = MockConfigEntry(
        title="Test Camera",
        domain=DOMAIN,
        data={},
        options=TESTDATA,
    )

    with mock_av_open:
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        # try updating the still image url
        data = TESTDATA.copy()
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/2"
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=data,
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        result3 = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result3["step_id"] == "init"

        # verify that an invalid template reports the correct UI error.
        data[CONF_STILL_IMAGE_URL] = "http://127.0.0.1/testurl/{{1/0}}"
        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input=data,
        )
        assert result4.get("type") == data_entry_flow.RESULT_TYPE_FORM
        assert result4["errors"] == {"still_image_url": "template_error"}


# These below can be deleted after deprecation period is finished.
@respx.mock
async def test_import(hass, fakeimg_png, mock_av_open):
    """Test configuration.yaml import used during migration."""
    with mock_av_open:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
        )
        # duplicate import should be aborted
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Yaml Defined Name"
    await hass.async_block_till_done()
    # Any name defined in yaml should end up as the entity id.
    assert hass.data["camera"].get_entity("camera.yaml_defined_name")
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT


@respx.mock
async def test_import_invalid_still_image(hass, mock_av_open):
    """Test configuration.yaml import used during migration."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=b"invalid")
    with mock_av_open:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


@respx.mock
async def test_import_other_error(hass, fakeimgbytes_png):
    """Test that non-specific import errors are raised."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)
    with patch(
        "homeassistant.components.generic.config_flow.av.open",
        side_effect=OSError("other error"),
    ), pytest.raises(OSError):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TESTDATA_YAML
        )


# These above can be deleted after deprecation period is finished.


@respx.mock
async def test_unload_entry(hass, fakeimg_png, mock_av_open):
    """Test unloading the generic IP Camera entry."""
    with mock_av_open:
        mock_entry = MockConfigEntry(domain=DOMAIN, data=TESTDATA)
        mock_entry.add_to_hass(hass)
        assert await homeassistant.components.generic.async_setup_entry(
            hass, mock_entry
        )
        await hass.async_block_till_done()
        assert await homeassistant.components.generic.async_unload_entry(
            hass, mock_entry
        )
        await hass.async_block_till_done()
