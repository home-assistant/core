"""Config flow for generic (IP Camera)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import contextlib
from datetime import datetime, timedelta
from errno import EHOSTUNREACH, EIO
import io
import logging
from typing import Any, cast

from aiohttp import web
from httpx import HTTPStatusError, RequestError, TimeoutException
import PIL.Image
import voluptuous as vol
import yarl

from homeassistant.components import websocket_api
from homeassistant.components.camera import (
    CAMERA_IMAGE_TIMEOUT,
    DOMAIN as CAMERA_DOMAIN,
    DynamicStreamSettings,
    _async_get_image,
)
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
    HLS_PROVIDER,
    RTSP_TRANSPORTS,
    SOURCE_TIMEOUT,
    Stream,
    create_stream,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import config_validation as cv, template as template_helper
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util import slugify

from .camera import GenericCamera, generate_auth
from .const import (
    CONF_CONFIRMED_OK,
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DEFAULT_NAME,
    DOMAIN,
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

SUPPORTED_IMAGE_TYPES = {"png", "jpeg", "gif", "svg+xml", "webp"}
IMAGE_PREVIEWS_ACTIVE = "previews"


class InvalidStreamException(HomeAssistantError):
    """Error to indicate an invalid stream."""

    def __init__(self, error: str, details: str | None = None) -> None:
        """Initialize the error."""
        super().__init__(error)
        self.details = details


def build_schema(
    user_input: Mapping[str, Any],
    is_options_flow: bool = False,
    show_advanced_options: bool = False,
) -> vol.Schema:
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
            CONF_RTSP_TRANSPORT,
            description={"suggested_value": user_input.get(CONF_RTSP_TRANSPORT)},
        ): vol.In(RTSP_TRANSPORTS),
        vol.Optional(
            CONF_AUTHENTICATION,
            description={"suggested_value": user_input.get(CONF_AUTHENTICATION)},
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
            CONF_FRAMERATE,
            description={"suggested_value": user_input.get(CONF_FRAMERATE, 2)},
        ): vol.All(vol.Range(min=0, min_included=False), cv.positive_float),
        vol.Required(
            CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
        ): bool,
    }
    if is_options_flow:
        spec[
            vol.Required(
                CONF_LIMIT_REFETCH_TO_URL_CHANGE,
                default=user_input.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE, False),
            )
        ] = bool
        if show_advanced_options:
            spec[
                vol.Required(
                    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
                    default=user_input.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS, False),
                )
            ] = bool
    return vol.Schema(spec)


def get_image_type(image: bytes) -> str | None:
    """Get the format of downloaded bytes that could be an image."""
    fmt = None
    imagefile = io.BytesIO(image)
    with contextlib.suppress(PIL.UnidentifiedImageError):
        img = PIL.Image.open(imagefile)
        fmt = img.format.lower() if img.format else None

    if fmt is None:
        # if PIL can't figure it out, could be svg.
        with contextlib.suppress(UnicodeDecodeError):
            if image.decode("utf-8").lstrip().startswith("<svg"):
                return "svg+xml"
    return fmt


async def async_test_still(
    hass: HomeAssistant, info: Mapping[str, Any]
) -> tuple[dict[str, str], str | None]:
    """Verify that the still image is valid before we create an entity."""
    fmt = None
    if not (url := info.get(CONF_STILL_IMAGE_URL)):
        return {}, info.get(CONF_CONTENT_TYPE, "image/jpeg")
    try:
        if not isinstance(url, template_helper.Template):
            url = template_helper.Template(url, hass)
        url = url.async_render(parse_result=False)
    except TemplateError as err:
        _LOGGER.warning("Problem rendering template %s: %s", url, err)
        return {CONF_STILL_IMAGE_URL: "template_error"}, None
    try:
        yarl_url = yarl.URL(url)
    except ValueError:
        return {CONF_STILL_IMAGE_URL: "malformed_url"}, None
    if not yarl_url.is_absolute():
        return {CONF_STILL_IMAGE_URL: "relative_url"}, None
    verify_ssl = info[CONF_VERIFY_SSL]
    auth = generate_auth(info)
    try:
        async_client = get_async_client(hass, verify_ssl=verify_ssl)
        async with asyncio.timeout(GET_IMAGE_TIMEOUT):
            response = await async_client.get(url, auth=auth, timeout=GET_IMAGE_TIMEOUT)
            response.raise_for_status()
            image = response.content
    except (
        TimeoutError,
        RequestError,
        TimeoutException,
    ) as err:
        _LOGGER.error("Error getting camera image from %s: %s", url, type(err).__name__)
        return {CONF_STILL_IMAGE_URL: "unable_still_load"}, None
    except HTTPStatusError as err:
        _LOGGER.error(
            "Error getting camera image from %s: %s %s",
            url,
            type(err).__name__,
            err.response.text,
        )
        if err.response.status_code in [401, 403]:
            return {CONF_STILL_IMAGE_URL: "unable_still_load_auth"}, None
        if err.response.status_code in [404]:
            return {CONF_STILL_IMAGE_URL: "unable_still_load_not_found"}, None
        if err.response.status_code in [500, 503]:
            return {CONF_STILL_IMAGE_URL: "unable_still_load_server_error"}, None
        return {CONF_STILL_IMAGE_URL: "unable_still_load"}, None

    if not image:
        return {CONF_STILL_IMAGE_URL: "unable_still_load_no_image"}, None
    fmt = get_image_type(image)
    _LOGGER.debug(
        "Still image at '%s' detected format: %s",
        info[CONF_STILL_IMAGE_URL],
        fmt,
    )
    if fmt not in SUPPORTED_IMAGE_TYPES:
        return {CONF_STILL_IMAGE_URL: "invalid_still_image"}, None
    return {}, f"image/{fmt}"


def slug(
    hass: HomeAssistant, template: str | template_helper.Template | None
) -> str | None:
    """Convert a camera url into a string suitable for a camera name."""
    url = ""
    if not template:
        return None
    if not isinstance(template, template_helper.Template):
        template = template_helper.Template(template, hass)
    try:
        url = template.async_render(parse_result=False)
        return slugify(yarl.URL(url).host)
    except (ValueError, TemplateError, TypeError) as err:
        _LOGGER.error("Syntax error in '%s': %s", template, err)
    return None


async def async_test_and_preview_stream(
    hass: HomeAssistant, info: Mapping[str, Any]
) -> Stream | None:
    """Verify that the stream is valid before we create an entity.

    Returns the stream object if valid. Raises InvalidStreamException if not.
    The stream object is used to preview the video in the UI.
    """
    if not (stream_source := info.get(CONF_STREAM_SOURCE)):
        return None

    if not isinstance(stream_source, template_helper.Template):
        stream_source = template_helper.Template(stream_source, hass)
    try:
        stream_source = stream_source.async_render(parse_result=False)
    except TemplateError as err:
        _LOGGER.warning("Problem rendering template %s: %s", stream_source, err)
        raise InvalidStreamException("template_error") from err
    stream_options: dict[str, str | bool | float] = {}
    if rtsp_transport := info.get(CONF_RTSP_TRANSPORT):
        stream_options[CONF_RTSP_TRANSPORT] = rtsp_transport
    if info.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS):
        stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = True

    try:
        url = yarl.URL(stream_source)
    except ValueError as err:
        raise InvalidStreamException("malformed_url") from err
    if not url.is_absolute():
        raise InvalidStreamException("relative_url")
    if not url.user and not url.password:
        username = info.get(CONF_USERNAME)
        password = info.get(CONF_PASSWORD)
        if username and password:
            url = url.with_user(username).with_password(password)
            stream_source = str(url)
    try:
        stream = create_stream(
            hass,
            stream_source,
            stream_options,
            DynamicStreamSettings(),
            f"{DOMAIN}.test_stream",
        )
        hls_provider = stream.add_provider(HLS_PROVIDER)
    except PermissionError as err:
        raise InvalidStreamException("stream_not_permitted") from err
    except OSError as err:
        if err.errno == EHOSTUNREACH:
            raise InvalidStreamException("stream_no_route_to_host") from err
        if err.errno == EIO:  # input/output error
            raise InvalidStreamException("stream_io_error") from err
        raise
    except HomeAssistantError as err:
        if "Stream integration is not set up" in str(err):
            raise InvalidStreamException("stream_not_set_up") from err
        raise
    await stream.start()
    if not await hls_provider.part_recv(timeout=SOURCE_TIMEOUT):
        hass.async_create_task(stream.stop())
        raise InvalidStreamException("timeout")
    return stream


def register_preview(hass: HomeAssistant) -> None:
    """Set up previews for camera feeds during config flow."""
    hass.data.setdefault(DOMAIN, {})

    if not hass.data[DOMAIN].get(IMAGE_PREVIEWS_ACTIVE):
        _LOGGER.debug("Registering camera image preview handler")
        hass.http.register_view(CameraImagePreview(hass))
    hass.data[DOMAIN][IMAGE_PREVIEWS_ACTIVE] = True


class GenericIPCamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for generic IP camera."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize Generic ConfigFlow."""
        self.preview_cam: dict[str, Any] = {}
        self.preview_stream: Stream | None = None
        self.user_input: dict[str, Any] = {}
        self.title = ""

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GenericOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GenericOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        errors = {}
        description_placeholders = {}
        hass = self.hass
        if user_input:
            # Secondary validation because serialised vol can't seem to handle this complexity:
            if not user_input.get(CONF_STILL_IMAGE_URL) and not user_input.get(
                CONF_STREAM_SOURCE
            ):
                errors["base"] = "no_still_image_or_stream_url"
            else:
                errors, still_format = await async_test_still(hass, user_input)
                try:
                    self.preview_stream = await async_test_and_preview_stream(
                        hass, user_input
                    )
                except InvalidStreamException as err:
                    errors[CONF_STREAM_SOURCE] = str(err)
                    if err.details:
                        errors["error_details"] = err.details
                    self.preview_stream = None
                if not errors:
                    user_input[CONF_CONTENT_TYPE] = still_format
                    still_url = user_input.get(CONF_STILL_IMAGE_URL)
                    stream_url = user_input.get(CONF_STREAM_SOURCE)
                    name = (
                        slug(hass, still_url) or slug(hass, stream_url) or DEFAULT_NAME
                    )
                    if still_url is None:
                        # If user didn't specify a still image URL,
                        # The automatically generated still image that stream generates
                        # is always jpeg
                        user_input[CONF_CONTENT_TYPE] = "image/jpeg"
                    self.user_input = user_input
                    self.title = name
                    # temporary preview for user to check the image
                    self.preview_cam = user_input
                    return await self.async_step_user_confirm()
                if "error_details" in errors:
                    description_placeholders["error"] = errors.pop("error_details")
        elif self.user_input:
            user_input = self.user_input
        else:
            user_input = DEFAULT_DATA.copy()
        return self.async_show_form(
            step_id="user",
            data_schema=build_schema(user_input),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_user_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user clicking confirm after still preview."""
        if user_input:
            if ha_stream := self.preview_stream:
                # Kill off the temp stream we created.
                await ha_stream.stop()
            if not user_input.get(CONF_CONFIRMED_OK):
                return await self.async_step_user()
            return self.async_create_entry(
                title=self.title, data={}, options=self.user_input
            )
        register_preview(self.hass)
        preview_url = f"/api/generic/preview_flow_image/{self.flow_id}?t={datetime.now().isoformat()}"
        return self.async_show_form(
            step_id="user_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONFIRMED_OK, default=False): bool,
                }
            ),
            description_placeholders={"preview_url": preview_url},
            errors=None,
            preview="generic_camera",
        )

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


class GenericOptionsFlowHandler(OptionsFlow):
    """Handle Generic IP Camera options."""

    def __init__(self) -> None:
        """Initialize Generic IP Camera options flow."""
        self.preview_cam: dict[str, Any] = {}
        self.user_input: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Generic IP Camera options."""
        errors: dict[str, str] = {}
        description_placeholders = {}
        hass = self.hass

        if user_input is not None:
            errors, still_format = await async_test_still(
                hass, self.config_entry.options | user_input
            )
            try:
                await async_test_and_preview_stream(hass, user_input)
            except InvalidStreamException as err:
                errors[CONF_STREAM_SOURCE] = str(err)
                if err.details:
                    errors["error_details"] = err.details
                # Stream preview during options flow not yet implemented

            still_url = user_input.get(CONF_STILL_IMAGE_URL)
            if not errors:
                if still_url is None:
                    # If user didn't specify a still image URL,
                    # The automatically generated still image that stream generates
                    # is always jpeg
                    still_format = "image/jpeg"
                data = {
                    CONF_USE_WALLCLOCK_AS_TIMESTAMPS: self.config_entry.options.get(
                        CONF_USE_WALLCLOCK_AS_TIMESTAMPS, False
                    ),
                    **user_input,
                    CONF_CONTENT_TYPE: still_format
                    or self.config_entry.options.get(CONF_CONTENT_TYPE),
                }
                self.user_input = data
                # temporary preview for user to check the image
                self.preview_cam = data
                return await self.async_step_confirm_still()
            if "error_details" in errors:
                description_placeholders["error"] = errors.pop("error_details")
        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(
                user_input or self.config_entry.options,
                True,
                self.show_advanced_options,
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_confirm_still(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user clicking confirm after still preview."""
        if user_input:
            if not user_input.get(CONF_CONFIRMED_OK):
                return await self.async_step_init()
            return self.async_create_entry(
                title=self.config_entry.title,
                data=self.user_input,
            )
        register_preview(self.hass)
        preview_url = f"/api/generic/preview_flow_image/{self.flow_id}?t={datetime.now().isoformat()}"
        return self.async_show_form(
            step_id="confirm_still",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONFIRMED_OK, default=False): bool,
                }
            ),
            description_placeholders={"preview_url": preview_url},
            errors=None,
        )


class CameraImagePreview(HomeAssistantView):
    """Camera view to temporarily serve an image."""

    url = "/api/generic/preview_flow_image/{flow_id}"
    name = "api:generic:preview_flow_image"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise."""
        self.hass = hass

    async def get(self, request: web.Request, flow_id: str) -> web.Response:
        """Start a GET request."""
        _LOGGER.debug("processing GET request for flow_id=%s", flow_id)
        flow = cast(
            GenericIPCamConfigFlow,
            self.hass.config_entries.flow._progress.get(flow_id),  # noqa: SLF001
        ) or cast(
            GenericOptionsFlowHandler,
            self.hass.config_entries.options._progress.get(flow_id),  # noqa: SLF001
        )
        if not flow:
            _LOGGER.warning("Unknown flow while getting image preview")
            raise web.HTTPNotFound
        user_input = flow.preview_cam
        camera = GenericCamera(self.hass, user_input, flow_id, "preview")
        if not camera.is_on:
            _LOGGER.debug("Camera is off")
            raise web.HTTPServiceUnavailable
        image = await _async_get_image(
            camera,
            CAMERA_IMAGE_TIMEOUT,
        )
        return web.Response(body=image.content, content_type=image.content_type)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "generic_camera/start_preview",
        vol.Required("flow_id"): str,
        vol.Optional("flow_type"): vol.Any("config_flow"),
        vol.Optional("user_input"): dict,
    }
)
@websocket_api.async_response
async def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate websocket handler for the camera still/stream preview."""
    _LOGGER.debug("Generating websocket handler for generic camera preview")

    flow_id = msg["flow_id"]
    flow = cast(
        GenericIPCamConfigFlow,
        hass.config_entries.flow._progress.get(flow_id),  # noqa: SLF001
    )
    user_input = flow.preview_cam

    # Create an EntityPlatform, needed for name translations
    platform = await async_prepare_setup_platform(hass, {}, CAMERA_DOMAIN, DOMAIN)
    entity_platform = EntityPlatform(
        hass=hass,
        logger=_LOGGER,
        domain=CAMERA_DOMAIN,
        platform_name=DOMAIN,
        platform=platform,
        scan_interval=timedelta(seconds=3600),
        entity_namespace=None,
    )
    await entity_platform.async_load_translations()

    ha_still_url = None
    ha_stream_url = None

    if user_input.get(CONF_STILL_IMAGE_URL):
        ha_still_url = f"/api/generic/preview_flow_image/{msg['flow_id']}?t={datetime.now().isoformat()}"
        _LOGGER.debug("Got preview still URL: %s", ha_still_url)

    if ha_stream := flow.preview_stream:
        ha_stream_url = ha_stream.endpoint_url(HLS_PROVIDER)
        _LOGGER.debug("Got preview stream URL: %s", ha_stream_url)

    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            {"attributes": {"still_url": ha_still_url, "stream_url": ha_stream_url}},
        )
    )
