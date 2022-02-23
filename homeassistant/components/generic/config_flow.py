"""Config flow for generic (IP Camera)."""
from __future__ import annotations

from errno import EHOSTUNREACH, EIO
from functools import partial
import imghdr
import logging
from typing import Any

import av
from httpx import HTTPStatusError, RequestError, TimeoutException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.stream.const import SOURCE_TIMEOUT
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.data_entry_flow import FlowResult
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

SUPPORTED_IMAGE_TYPES = ["png", "jpeg", "svg+xml"]


def build_schema(user_input):
    """Create schema for camera config setup."""
    spec = {
        vol.Optional(
            CONF_STILL_IMAGE_URL,
            description={"suggested_value": user_input.get(CONF_STILL_IMAGE_URL, "")},
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
            default=user_input.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE, False),
        ): bool,
        vol.Optional(
            CONF_FRAMERATE,
            description={"suggested_value": user_input.get(CONF_FRAMERATE, "")},
        ): int,
        vol.Optional(
            CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
        ): bool,
    }
    return vol.Schema(spec)


def check_for_existing(hass, options, ignore_entry_id=None):
    """Check whether an existing entry is using the same URLs."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.entry_id != ignore_entry_id
            and entry.options[CONF_STILL_IMAGE_URL] == options[CONF_STILL_IMAGE_URL]
            and entry.options[CONF_STREAM_SOURCE] == options[CONF_STREAM_SOURCE]
        ):
            return True
    return False


async def async_test_connection(
    hass, info
) -> tuple[dict[str, str], str | None, str | None]:
    """Verify that the connection data is valid before we add it."""
    errors: dict[str, str] = {}
    fmt = None
    if url := info.get(CONF_STILL_IMAGE_URL):
        # First try getting a still image
        if not isinstance(url, template_helper.Template) and url:
            url = cv.template(url)
            url.hass = hass
        try:
            url = url.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", url, err)
            return (
                {CONF_STILL_IMAGE_URL: "template_error"},
                None,
                None,
            )
        verify_ssl = info.get(CONF_VERIFY_SSL)
        auth = generate_auth(info)
        try:
            async_client = get_async_client(hass, verify_ssl=verify_ssl)
            response = await async_client.get(url, auth=auth, timeout=GET_IMAGE_TIMEOUT)
            response.raise_for_status()
            image = response.content
        except (
            RequestError,
            HTTPStatusError,
            TimeoutException,
        ) as err:
            _LOGGER.error("Error getting camera image from %s: %s", url, err)
            return {"base": "unable_still_load"}, None, None

        if image is None:
            return {"base": "unable_still_load"}, None, None
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
        if fmt not in SUPPORTED_IMAGE_TYPES:
            return {"base": "invalid_still_image"}, None, None
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
                stream_options[FFMPEG_OPTION_MAP[CONF_RTSP_TRANSPORT]] = rtsp_transport
            _LOGGER.debug("Attempting to open stream %s", stream_source)
            container = await hass.async_add_executor_job(
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
            return {CONF_STREAM_SOURCE: "stream_no_route_to_host"}, None, None
        except av.error.HTTPUnauthorizedError:  # pylint: disable=c-extension-no-member
            return {CONF_STREAM_SOURCE: "stream_unauthorised"}, None, None
        except (KeyError, IndexError):
            return {CONF_STREAM_SOURCE: "stream_novideo"}, None, None
        except PermissionError:
            return {CONF_STREAM_SOURCE: "stream_not_permitted"}, None, None
        except OSError as err:
            if err.errno == EHOSTUNREACH:
                return {CONF_STREAM_SOURCE: "stream_no_route_to_host"}, None, None
            if err.errno == EIO:  # input/output error
                return {CONF_STREAM_SOURCE: "stream_io_error"}, None, None
            raise err
    name = info.get(CONF_NAME, url or stream_source)
    return errors, fmt, name


class GenericIPCamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for generic IP camera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GenericOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GenericOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        errors = {}
        if user_input:
            # Secondary validation because serialised vol can't seem to handle this complexity:
            if not user_input.get(CONF_STILL_IMAGE_URL) and not user_input.get(
                CONF_STREAM_SOURCE
            ):
                errors["base"] = "no_still_image_or_stream_url"
            else:
                (errors, still_format, name) = await async_test_connection(
                    self.hass, user_input
                )
                if not errors and name:
                    user_input[CONF_CONTENT_TYPE] = still_format
                    await self.async_set_unique_id(self.flow_id)
                    return self.async_create_entry(
                        title=name, data={}, options=user_input
                    )
        else:
            user_input = DEFAULT_DATA.copy()

        return self.async_show_form(
            step_id="user",
            data_schema=build_schema(user_input),
            errors=errors,
        )

    async def async_step_import(self, import_config) -> FlowResult:
        """Handle config import from yaml."""
        # abort if we've already got this one.
        if check_for_existing(self.hass, import_config):
            return self.async_abort(reason="already_exists")
        errors, still_format, name = await async_test_connection(
            self.hass, import_config
        )
        if not errors and name:
            import_config[CONF_CONTENT_TYPE] = still_format
            await self.async_set_unique_id(self.flow_id)
            return self.async_create_entry(title=name, data={}, options=import_config)
        _LOGGER.error(
            "Error importing generic IP camera platform config: unexpected error '%s'",
            errors.values,
        )
        return self.async_abort(reason="unknown")


class GenericOptionsFlowHandler(OptionsFlow):
    """Handle Generic IP Camera options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Generic IP Camera options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Generic IP Camera options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, still_format, name = await async_test_connection(
                self.hass, user_input
            )
            if not errors:
                if check_for_existing(
                    self.hass,
                    user_input,
                    ignore_entry_id=self.config_entry.entry_id,
                ):
                    errors = {
                        CONF_STILL_IMAGE_URL: "already_configured",
                        CONF_STREAM_SOURCE: "already_configured",
                    }

                if not errors:
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME, name),
                        data={
                            CONF_AUTHENTICATION: user_input.get(CONF_AUTHENTICATION),
                            CONF_STREAM_SOURCE: user_input.get(CONF_STREAM_SOURCE),
                            CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                            CONF_STILL_IMAGE_URL: user_input.get(CONF_STILL_IMAGE_URL),
                            CONF_CONTENT_TYPE: still_format,
                            CONF_USERNAME: user_input.get(CONF_USERNAME),
                            CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                        },
                    )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(user_input or self.config_entry.options),
            errors=errors,
        )
