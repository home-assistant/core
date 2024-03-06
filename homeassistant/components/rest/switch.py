"""Support for RESTful switches."""
from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_ICON,
    CONF_METHOD,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    TEMPLATE_ENTITY_BASE_SCHEMA,
    ManualTriggerEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
CONF_BODY_OFF = "body_off"
CONF_BODY_ON = "body_on"
CONF_IS_ON_TEMPLATE = "is_on_template"
CONF_STATE_RESOURCE = "state_resource"

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
)

DEFAULT_METHOD = "post"
DEFAULT_BODY_OFF = "OFF"
DEFAULT_BODY_ON = "ON"
DEFAULT_NAME = "REST Switch"
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True

SUPPORT_REST_METHODS = ["post", "put", "patch"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        **TEMPLATE_ENTITY_BASE_SCHEMA.schema,
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_STATE_RESOURCE): cv.url,
        vol.Optional(CONF_HEADERS): {cv.string: cv.template},
        vol.Optional(CONF_PARAMS): {cv.string: cv.template},
        vol.Optional(CONF_BODY_OFF, default=DEFAULT_BODY_OFF): cv.template,
        vol.Optional(CONF_BODY_ON, default=DEFAULT_BODY_ON): cv.template,
        vol.Optional(CONF_IS_ON_TEMPLATE): cv.template,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.All(
            vol.Lower, vol.In(SUPPORT_REST_METHODS)
        ),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_AVAILABILITY): cv.template,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the RESTful switch."""
    resource: str = config[CONF_RESOURCE]
    name = config.get(CONF_NAME) or template.Template(DEFAULT_NAME, hass)

    trigger_entity_config = {CONF_NAME: name}

    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in config:
            continue
        trigger_entity_config[key] = config[key]

    try:
        switch = RestSwitch(hass, config, trigger_entity_config)

        req = await switch.get_device_state(hass)
        if req.status_code >= HTTPStatus.BAD_REQUEST:
            _LOGGER.error("Got non-ok response from resource: %s", req.status_code)
        else:
            async_add_entities([switch])
    except (TypeError, ValueError):
        _LOGGER.error(
            "Missing resource or schema in configuration. "
            "Add http:// or https:// to your URL"
        )
    except (TimeoutError, httpx.RequestError) as exc:
        raise PlatformNotReady(f"No route to resource/endpoint: {resource}") from exc


class RestSwitch(ManualTriggerEntity, SwitchEntity):
    """Representation of a switch that can be toggled using REST."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        trigger_entity_config: ConfigType,
    ) -> None:
        """Initialize the REST switch."""
        ManualTriggerEntity.__init__(self, hass, trigger_entity_config)

        auth: httpx.BasicAuth | None = None
        username: str | None = None
        if username := config.get(CONF_USERNAME):
            password: str = config[CONF_PASSWORD]
            auth = httpx.BasicAuth(username, password=password)

        self._resource: str = config[CONF_RESOURCE]
        self._state_resource: str = config.get(CONF_STATE_RESOURCE) or self._resource
        self._method: str = config[CONF_METHOD]
        self._headers: dict[str, template.Template] | None = config.get(CONF_HEADERS)
        self._params: dict[str, template.Template] | None = config.get(CONF_PARAMS)
        self._auth = auth
        self._body_on: template.Template = config[CONF_BODY_ON]
        self._body_off: template.Template = config[CONF_BODY_OFF]
        self._is_on_template: template.Template | None = config.get(CONF_IS_ON_TEMPLATE)
        self._timeout: int = config[CONF_TIMEOUT]
        self._verify_ssl: bool = config[CONF_VERIFY_SSL]

        self._body_on.hass = hass
        self._body_off.hass = hass
        if (is_on_template := self._is_on_template) is not None:
            is_on_template.hass = hass

        template.attach(hass, self._headers)
        template.attach(hass, self._params)

    async def async_added_to_hass(self) -> None:
        """Handle adding to Home Assistant."""
        await super().async_added_to_hass()
        await self.async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        body_on_t = self._body_on.async_render(parse_result=False)

        try:
            req = await self.set_device_state(body_on_t)

            if HTTPStatus.OK <= req.status_code < HTTPStatus.MULTIPLE_CHOICES:
                self._attr_is_on = True
            else:
                _LOGGER.error(
                    "Can't turn on %s. Is resource/endpoint offline?", self._resource
                )
        except (TimeoutError, httpx.RequestError):
            _LOGGER.error("Error while switching on %s", self._resource)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        body_off_t = self._body_off.async_render(parse_result=False)

        try:
            req = await self.set_device_state(body_off_t)
            if HTTPStatus.OK <= req.status_code < HTTPStatus.MULTIPLE_CHOICES:
                self._attr_is_on = False
            else:
                _LOGGER.error(
                    "Can't turn off %s. Is resource/endpoint offline?", self._resource
                )
        except (TimeoutError, httpx.RequestError):
            _LOGGER.error("Error while switching off %s", self._resource)

    async def set_device_state(self, body: Any) -> httpx.Response:
        """Send a state update to the device."""
        websession = get_async_client(self.hass, self._verify_ssl)

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        req: httpx.Response = await getattr(websession, self._method)(
            self._resource,
            auth=self._auth,
            content=bytes(body, "utf-8"),
            headers=rendered_headers,
            params=rendered_params,
            timeout=self._timeout,
        )
        return req

    async def async_update(self) -> None:
        """Get the current state, catching errors."""
        req = None
        try:
            req = await self.get_device_state(self.hass)
        except (TimeoutError, httpx.TimeoutException):
            _LOGGER.exception("Timed out while fetching data")
        except httpx.RequestError as err:
            _LOGGER.exception("Error while fetching data: %s", err)

        if req:
            self._process_manual_data(req.text)
            self.async_write_ha_state()

    async def get_device_state(self, hass: HomeAssistant) -> httpx.Response:
        """Get the latest data from REST API and update the state."""
        websession = get_async_client(hass, self._verify_ssl)

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        req = await websession.get(
            self._state_resource,
            auth=self._auth,
            headers=rendered_headers,
            params=rendered_params,
            timeout=self._timeout,
        )
        text = req.text

        if self._is_on_template is not None:
            text = self._is_on_template.async_render_with_possible_json_value(
                text, "None"
            )
            text = text.lower()
            if text == "true":
                self._attr_is_on = True
            elif text == "false":
                self._attr_is_on = False
            else:
                self._attr_is_on = None
        elif text == self._body_on.template:
            self._attr_is_on = True
        elif text == self._body_off.template:
            self._attr_is_on = False
        else:
            self._attr_is_on = None

        return req
