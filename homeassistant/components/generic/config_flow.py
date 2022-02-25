"""Config flow for generic (IP Camera)."""
from __future__ import annotations

from errno import EHOSTUNREACH, EIO
from functools import partial
import imghdr
import logging
from typing import Any

from async_timeout import timeout
import av
from httpx import HTTPStatusError, RequestError, TimeoutException
import voluptuous as vol

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
        vol.Required(
            CONF_LIMIT_REFETCH_TO_URL_CHANGE,
            default=user_input.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE, False),
        ): bool,
        vol.Required(
            CONF_FRAMERATE,
            description={"suggested_value": user_input.get(CONF_FRAMERATE, 2)},
        ): int,
        vol.Required(
            CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
        ): bool,
    }
    return vol.Schema(spec)


def get_image_type(image):
    """Get the format of downloaded bytes that could be an image."""
    fmt = imghdr.what(None, h=image)
    if fmt is None:
        # if imghdr can't figure it out, could be svg.
        try:
            if image.decode("utf-8").startswith("<svg"):
                return "svg+xml"
        except UnicodeDecodeError:
            return None
    return fmt


async def async_test_still(hass, info) -> tuple[dict[str, str], str | None]:
    """Verify that the still image is valid before we create an entity."""
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
            return {CONF_STILL_IMAGE_URL: "template_error"}, None
        verify_ssl = info.get(CONF_VERIFY_SSL)
        auth = generate_auth(info)
        try:
            async_client = get_async_client(hass, verify_ssl=verify_ssl)
            async with timeout(GET_IMAGE_TIMEOUT):
                response = await async_client.get(
                    url, auth=auth, timeout=GET_IMAGE_TIMEOUT
                )
                response.raise_for_status()
                image = response.content
        except (
            TimeoutError,
            RequestError,
            HTTPStatusError,
            TimeoutException,
        ) as err:
            _LOGGER.error(
                "Error getting camera image from %s: %s", url, type(err).__name__
            )
            return {CONF_STILL_IMAGE_URL: "unable_still_load"}, None

        if not image:
            return {CONF_STILL_IMAGE_URL: "unable_still_load"}, None
        fmt = get_image_type(image)
        _LOGGER.debug(
            "Still image at '%s' detected format: %s",
            info[CONF_STILL_IMAGE_URL],
            fmt,
        )
        if fmt not in SUPPORTED_IMAGE_TYPES:
            return {CONF_STILL_IMAGE_URL: "invalid_still_image"}, None
        return {}, "image/" + fmt
    return {}, None


async def async_test_stream(hass, info) -> dict[str, str]:
    """Verify that the stream is valid before we create an entity."""
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
        except (av.error.FileNotFoundError):
            return {CONF_STREAM_SOURCE: "stream_file_not_found"}
        except (av.error.HTTPNotFoundError):
            return {CONF_STREAM_SOURCE: "stream_http_not_found"}
        except (av.error.TimeoutError):
            return {CONF_STREAM_SOURCE: "timeout"}
        except av.error.HTTPUnauthorizedError:  # pylint: disable=c-extension-no-member
            return {CONF_STREAM_SOURCE: "stream_unauthorised"}
        except (KeyError, IndexError):
            return {CONF_STREAM_SOURCE: "stream_novideo"}
        except PermissionError:
            return {CONF_STREAM_SOURCE: "stream_not_permitted"}
        except OSError as err:
            if err.errno == EHOSTUNREACH:
                return {CONF_STREAM_SOURCE: "stream_no_route_to_host"}
            if err.errno == EIO:  # input/output error
                return {CONF_STREAM_SOURCE: "stream_io_error"}
            raise err
    return {}


class GenericIPCamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for generic IP camera."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GenericOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GenericOptionsFlowHandler(config_entry)

    def check_for_existing(self, options):
        """Check whether an existing entry is using the same URLs."""
        return any(
            entry.options[CONF_STILL_IMAGE_URL] == options[CONF_STILL_IMAGE_URL]
            and entry.options[CONF_STREAM_SOURCE] == options[CONF_STREAM_SOURCE]
            for entry in self._async_current_entries()
        )

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
                errors, still_format = await async_test_still(self.hass, user_input)
                errors = errors | await async_test_stream(self.hass, user_input)
                still_url = user_input.get(CONF_STILL_IMAGE_URL)
                stream_url = user_input.get(CONF_STREAM_SOURCE)
                name = user_input.get(
                    CONF_NAME, still_url or stream_url or DEFAULT_NAME
                )

                if not errors:
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
        if self.check_for_existing(import_config):
            return self.async_abort(reason="already_exists")
        errors, still_format = await async_test_still(self.hass, import_config)
        errors = errors | await async_test_stream(self.hass, import_config)
        still_url = import_config.get(CONF_STILL_IMAGE_URL)
        stream_url = import_config.get(CONF_STREAM_SOURCE)
        name = import_config.get(CONF_NAME, still_url or stream_url or DEFAULT_NAME)

        if not errors:
            import_config[CONF_CONTENT_TYPE] = still_format
            await self.async_set_unique_id(self.flow_id)
            return self.async_create_entry(title=name, data={}, options=import_config)
        _LOGGER.error(
            "Error importing generic IP camera platform config: unexpected error '%s'",
            list(errors.values()),
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
            errors, still_format = await async_test_still(self.hass, user_input)
            errors = errors | await async_test_stream(self.hass, user_input)
            still_url = user_input.get(CONF_STILL_IMAGE_URL)
            stream_url = user_input.get(CONF_STREAM_SOURCE)
            name = user_input.get(CONF_NAME, still_url or stream_url or DEFAULT_NAME)
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
                        CONF_LIMIT_REFETCH_TO_URL_CHANGE: user_input.get(
                            CONF_LIMIT_REFETCH_TO_URL_CHANGE
                        ),
                        CONF_FRAMERATE: user_input.get(CONF_FRAMERATE),
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    },
                )
        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(user_input or self.config_entry.options),
            errors=errors,
        )
