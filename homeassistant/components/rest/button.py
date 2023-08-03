"""Support for RESTful buttons."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging

import async_timeout
import httpx
import voluptuous as vol

from homeassistant.components.button import DEVICE_CLASSES_SCHEMA, ButtonEntity
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.template_entity import (
    TEMPLATE_ENTITY_BASE_SCHEMA,
    TemplateEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
CONF_BODY = "body"

DEFAULT_METHOD = "post"
DEFAULT_NAME = "REST Button"
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DEFAULT_BODY = ""

SUPPORT_REST_METHODS = ["post", "put", "patch"]

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA_BASE.extend(
    {
        **TEMPLATE_ENTITY_BASE_SCHEMA.schema,
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_HEADERS): {cv.string: cv.template},
        vol.Optional(CONF_PARAMS): {cv.string: cv.template},
        vol.Optional(CONF_BODY, default=DEFAULT_BODY): cv.template,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.All(
            vol.Lower, vol.In(SUPPORT_REST_METHODS)
        ),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the RESTful button."""
    unique_id: str | None = config.get(CONF_UNIQUE_ID)

    button = RestButton(hass, config, unique_id)
    async_add_entities([button])


class RestButton(TemplateEntity, ButtonEntity):
    """Representation of a button that can trigger REST."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the REST button."""
        TemplateEntity.__init__(
            self,
            hass,
            config=config,
            fallback_name=DEFAULT_NAME,
            unique_id=unique_id,
        )

        auth: httpx.DigestAuth | httpx.BasicAuth | tuple[str, str] | None = None
        username: str | None = None
        password: str | None = None
        if (username := config.get(CONF_USERNAME)) and (
            password := config.get(CONF_PASSWORD)
        ):
            if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
                auth = httpx.DigestAuth(username, password)
            else:
                auth = httpx.BasicAuth(username, password=password)

        self._resource: str = config[CONF_RESOURCE]
        self._method: str = config[CONF_METHOD]
        self._headers: dict[str, template.Template] | None = config.get(CONF_HEADERS)
        self._params: dict[str, template.Template] | None = config.get(CONF_PARAMS)
        self._auth = auth
        self._body: template.Template = config[CONF_BODY]
        self._timeout: int = config[CONF_TIMEOUT]
        self._verify_ssl: bool = config[CONF_VERIFY_SSL]

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._body.hass = hass

        template.attach(hass, self._headers)
        template.attach(hass, self._params)

    async def async_press(self) -> None:
        """Handle the button press."""
        rendered_body = self._body.async_render(parse_result=False)

        websession = get_async_client(self.hass, self._verify_ssl)

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        try:
            async with async_timeout.timeout(self._timeout):
                req = await getattr(websession, self._method)(
                    self._resource,
                    auth=self._auth,
                    data=bytes(rendered_body, "utf-8"),
                    headers=rendered_headers,
                    params=rendered_params,
                )

            if req.status_code == HTTPStatus.OK:
                _LOGGER.debug("Successfully triggered %s", self._resource)
            else:
                _LOGGER.error(
                    "Http error %g by triggering %s", req.status_code, self._resource
                )
        except (asyncio.TimeoutError, httpx.RequestError):
            _LOGGER.error("Error while triggering %s", self._resource)
