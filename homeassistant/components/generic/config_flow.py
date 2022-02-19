"""Config flow for generic (IP Camera)."""
from __future__ import annotations

from functools import partial
import imghdr
import logging
from typing import Any

import av
import httpx
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.stream.const import SOURCE_TIMEOUT
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template as template_helper
from homeassistant.helpers.httpx_client import get_async_client

from .camera import generate_auth

# pylint: disable=unused-import
from .const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_RTSP_TRANSPORT,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DEFAULT_NAME,
    DOMAIN,
    FFMPEG_OPTION_MAP,
    GET_IMAGE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_DATA = {
    CONF_NAME: DEFAULT_NAME,
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
    CONF_FRAMERATE: 2,
    CONF_VERIFY_SSL: True,
}


class GenericIPCamConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for generic IP camera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _test_connection(self, info) -> tuple[bool, str | None, str]:
        """Verify that the camera data is valid before we add it."""
        unique_id = self.flow_id
        if unique_id in self._async_current_ids():
            return False, None, "unique_id_already_in_use"
        await self.async_set_unique_id(unique_id)
        fmt = None
        if url := info.get(CONF_STILL_IMAGE_URL):
            # First try getting a still image
            if not isinstance(url, template_helper.Template) and url:
                url = cv.template(url)
                url.hass = self.hass
            try:
                url = url.async_render(parse_result=False)
            except TemplateError as err:
                _LOGGER.error("Error parsing template %s: %s", url, err)
                return False, None, "template_error"
            verify_ssl = info.get(CONF_VERIFY_SSL)
            auth = generate_auth(info)
            try:
                async_client = get_async_client(self.hass, verify_ssl=verify_ssl)
                response = await async_client.get(
                    url, auth=auth, timeout=GET_IMAGE_TIMEOUT
                )
                response.raise_for_status()
                image = response.content
            except httpx.TimeoutException:
                _LOGGER.error("Timeout getting camera image from %s", url)
                return False, None, "unable_still_load"
            except (httpx.RequestError, httpx.HTTPStatusError) as err:
                _LOGGER.error("Error getting camera image from %s: %s", url, err)
                return False, None, "unable_still_load"

            if image is None:
                return False, None, "unable_still_load"
            fmt = imghdr.what(None, h=image)
            if fmt is None:
                # if imghdr can't figure it out, could be svg.
                if image.decode("utf-8").startswith("<svg"):
                    fmt = "svg+xml"
            _LOGGER.debug(
                "Still image at '%s' detected format: %s",
                info[CONF_STILL_IMAGE_URL],
                fmt,
            )
            if fmt not in ["png", "jpeg", "svg+xml"]:
                return False, None, "invalid_still_image"
            fmt = "image/" + fmt

        # Second level functionality is to get a stream.
        if stream_source := info.get(CONF_STREAM_SOURCE):
            try:
                # For RTSP streams, prefer TCP. This code is duplicated from
                # homeassistant.components.stream.__init__.py:create_stream()
                # It may be possible & better to call create_stream() directly.
                stream_options: dict[str, str] = {}
                if isinstance(stream_source, str) and stream_source[:7] == "rtsp://":
                    stream_options = {
                        "rtsp_flags": "prefer_tcp",
                        "stimeout": "5000000",
                    }
                if rtsp_transport := info.get(CONF_RTSP_TRANSPORT):
                    stream_options[
                        FFMPEG_OPTION_MAP[CONF_RTSP_TRANSPORT]
                    ] = rtsp_transport
                _LOGGER.debug("Attempting to open stream %s", stream_source)
                container = await self.hass.async_add_executor_job(
                    partial(
                        av.open,
                        stream_source,
                        options=stream_options,
                        timeout=SOURCE_TIMEOUT,
                    )
                )
                _ = container.streams.video[0]
            # pylint: disable=c-extension-no-member
            except av.error.FileNotFoundError:
                return False, None, "stream_no_route_to_host"
            except av.error.HTTPUnauthorizedError:  # pylint: disable=c-extension-no-member
                return False, None, "stream_unauthorised"
            except (KeyError, IndexError):
                return False, None, "stream_novideo"
            except PermissionError:
                return False, None, "stream_not_permitted"
            except OSError as err:
                if "No route to host" in str(err):
                    return False, None, "stream_no_route_to_host"
                if "Input/output error" in str(err):
                    return False, None, "stream_io_error"
                raise err
        return True, fmt, ""

    @staticmethod
    def build_schema(user_input):
        """Create schema for camera config setup."""
        spec = {
            vol.Optional(CONF_NAME, default=user_input[CONF_NAME]): str,
            vol.Optional(
                CONF_STILL_IMAGE_URL,
                description={
                    "suggested_value": user_input.get(CONF_STILL_IMAGE_URL, "")
                },
            ): str,
            vol.Optional(
                CONF_STREAM_SOURCE,
                description={"suggested_value": user_input.get(CONF_STREAM_SOURCE, "")},
            ): str,
            vol.Optional(
                CONF_RTSP_TRANSPORT, default=user_input.get(CONF_RTSP_TRANSPORT)
            ): vol.In([None, "tcp", "udp", "udp_multicast", "http"]),
            vol.Optional(
                CONF_AUTHENTICATION, default=user_input.get(CONF_AUTHENTICATION)
            ): vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
            vol.Optional(
                CONF_USERNAME,
                description={"suggested_value": user_input.get(CONF_USERNAME, "")},
            ): str,
            vol.Optional(
                CONF_PASSWORD,
                description={"suggested_value": user_input.get(CONF_PASSWORD, "")},
            ): str,
            vol.Optional(
                CONF_LIMIT_REFETCH_TO_URL_CHANGE,
                default=user_input.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE),
            ): bool,
            vol.Optional(
                CONF_FRAMERATE,
                description={"suggested_value": user_input.get(CONF_FRAMERATE, "")},
            ): int,
            vol.Optional(
                CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL)
            ): bool,
        }
        return vol.Schema(spec)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the start of the config flow."""
        errors = {}
        if user_input is not None:
            # Secondary validation because serialised vol can't seem to handle this complexity:
            if user_input.get(CONF_STILL_IMAGE_URL) in [None, ""] and user_input.get(
                CONF_STREAM_SOURCE
            ) in [None, ""]:
                errors["base"] = "no_still_image_or_stream_url"
            else:
                (res, still_format, errors["base"]) = await self._test_connection(
                    user_input
                )
                if res:
                    user_input[CONF_CONTENT_TYPE] = still_format
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )
        else:
            user_input = DEFAULT_DATA.copy()

        return self.async_show_form(
            step_id="user",
            data_schema=self.build_schema(user_input),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        # abort if we've already got this one.
        self._async_abort_entries_match(
            {CONF_STILL_IMAGE_URL: import_config[CONF_STILL_IMAGE_URL]}
        )
        res, still_format, err = await self._test_connection(import_config)
        import_config[CONF_CONTENT_TYPE] = still_format
        if res:
            return self.async_create_entry(
                title=import_config[CONF_NAME], data=import_config
            )
        _LOGGER.error(
            "Error importing generic IP camera platform config: unexpected error '%s'",
            err,
        )
        return self.async_abort(reason=err)
