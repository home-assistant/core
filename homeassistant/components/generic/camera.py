"""Support for IP Cameras."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import httpx
import voluptuous as vol
import yarl

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    PLATFORM_SCHEMA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
    RTSP_TRANSPORTS,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template as template_helper
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN
from .const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DEFAULT_NAME,
    GET_IMAGE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(vol.Any(CONF_STILL_IMAGE_URL, CONF_STREAM_SOURCE)): cv.template,
        vol.Optional(vol.Any(CONF_STILL_IMAGE_URL, CONF_STREAM_SOURCE)): cv.template,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_FRAMERATE, default=2): vol.Any(
            cv.small_float, cv.positive_int
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_RTSP_TRANSPORT): vol.In(RTSP_TRANSPORTS),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a generic IP Camera."""

    _LOGGER.warning(
        "Loading generic IP camera via configuration.yaml is deprecated, "
        "it will be automatically imported.  Once you have confirmed correct "
        "operation, please remove 'generic' (IP camera) section(s) from "
        "configuration.yaml"
    )
    image = config.get(CONF_STILL_IMAGE_URL)
    stream = config.get(CONF_STREAM_SOURCE)
    config_new = {
        CONF_NAME: config[CONF_NAME],
        CONF_STILL_IMAGE_URL: image.template if image is not None else None,
        CONF_STREAM_SOURCE: stream.template if stream is not None else None,
        CONF_AUTHENTICATION: config.get(CONF_AUTHENTICATION),
        CONF_USERNAME: config.get(CONF_USERNAME),
        CONF_PASSWORD: config.get(CONF_PASSWORD),
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: config.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE),
        CONF_CONTENT_TYPE: config.get(CONF_CONTENT_TYPE),
        CONF_FRAMERATE: config.get(CONF_FRAMERATE),
        CONF_VERIFY_SSL: config.get(CONF_VERIFY_SSL),
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config_new
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a generic IP Camera."""

    async_add_entities(
        [GenericCamera(hass, entry.options, entry.entry_id, entry.title)]
    )


def generate_auth(device_info: Mapping[str, Any]) -> httpx.Auth | None:
    """Generate httpx.Auth object from credentials."""
    username: str | None = device_info.get(CONF_USERNAME)
    password: str | None = device_info.get(CONF_PASSWORD)
    authentication = device_info.get(CONF_AUTHENTICATION)
    if username and password:
        if authentication == HTTP_DIGEST_AUTHENTICATION:
            return httpx.DigestAuth(username=username, password=password)
        return httpx.BasicAuth(username=username, password=password)
    return None


class GenericCamera(Camera):
    """A generic implementation of an IP camera."""

    _last_image: bytes | None

    def __init__(
        self,
        hass: HomeAssistant,
        device_info: Mapping[str, Any],
        identifier: str,
        title: str,
    ) -> None:
        """Initialize a generic camera."""
        super().__init__()
        self.hass = hass
        self._attr_unique_id = identifier
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._name = device_info.get(CONF_NAME, title)
        self._still_image_url = device_info.get(CONF_STILL_IMAGE_URL)
        if (
            not isinstance(self._still_image_url, template_helper.Template)
            and self._still_image_url
        ):
            self._still_image_url = cv.template(self._still_image_url)
        if self._still_image_url:
            self._still_image_url.hass = hass
        self._stream_source = device_info.get(CONF_STREAM_SOURCE)
        if self._stream_source:
            if not isinstance(self._stream_source, template_helper.Template):
                self._stream_source = cv.template(self._stream_source)
            self._stream_source.hass = hass
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]
        self._attr_frame_interval = 1 / device_info[CONF_FRAMERATE]
        if self._stream_source:
            self._attr_supported_features = CameraEntityFeature.STREAM
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        if device_info.get(CONF_RTSP_TRANSPORT):
            self.stream_options[CONF_RTSP_TRANSPORT] = device_info[CONF_RTSP_TRANSPORT]
        self._auth = generate_auth(device_info)
        if device_info.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS):
            self.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = True

        self._last_url = None
        self._last_image = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if not self._still_image_url:
            if not self.stream:
                await self.async_create_stream()
            if self.stream:
                return await self.stream.async_get_image(width, height)
            return None
        try:
            url = self._still_image_url.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        try:
            async_client = get_async_client(self.hass, verify_ssl=self.verify_ssl)
            response = await async_client.get(
                url, auth=self._auth, timeout=GET_IMAGE_TIMEOUT
            )
            response.raise_for_status()
            self._last_image = response.content
        except httpx.TimeoutException:
            _LOGGER.error("Timeout getting camera image from %s", self._name)
            return self._last_image
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self._name, err)
            return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if self._stream_source is None:
            return None

        try:
            stream_url = self._stream_source.async_render(parse_result=False)
            url = yarl.URL(stream_url)
            if (
                not url.user
                and not url.password
                and self._username
                and self._password
                and url.is_absolute()
            ):
                url = url.with_user(self._username).with_password(self._password)
            return str(url)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._stream_source, err)
            return None
