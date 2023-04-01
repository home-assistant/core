"""Support for RESTful switches."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template_entity import TemplateEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_BODY_OFF, CONF_BODY_ON, CONF_IS_ON_TEMPLATE, CONF_STATE_RESOURCE
from .schema import RESOURCE_SCHEMA, SWITCH_SCHEMA

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "REST Switch"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA}).extend({**SWITCH_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the RESTful switch."""
    unique_id: str | None = config.get(CONF_UNIQUE_ID)

    try:
        switch = RestSwitch(hass, config, unique_id)

        req = await switch.get_device_state(hass)
        if req.status >= HTTPStatus.BAD_REQUEST:
            _LOGGER.error("Got non-ok response from resource: %s", req.status)
        else:
            async_add_entities([switch])
    except (TypeError, ValueError):
        _LOGGER.error(
            "Missing resource or schema in configuration. "
            "Add http:// or https:// to your URL"
        )
    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        if config.get(CONF_RESOURCE) is not None:
            rendered_resource = config[CONF_RESOURCE]
        else:
            resource: template.Template = config[CONF_RESOURCE_TEMPLATE]
            resource.hass = hass
            rendered_resource = resource.async_render_with_possible_json_value(
                resource, "http://127.0.0.1"
            )
        raise PlatformNotReady(
            f"No route to resource/endpoint: {rendered_resource}"
        ) from exc


class RestSwitch(TemplateEntity, SwitchEntity):
    """Representation of a switch that can be toggled using REST."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the REST switch."""
        TemplateEntity.__init__(
            self,
            hass,
            config=config,
            fallback_name=DEFAULT_NAME,
            unique_id=unique_id,
        )

        auth: aiohttp.BasicAuth | None = None
        username: str | None = None
        if username := config.get(CONF_USERNAME):
            password: str = config[CONF_PASSWORD]
            auth = aiohttp.BasicAuth(username, password=password)

        if config.get(CONF_RESOURCE) is not None:
            self._res_is_template = False
            self._resource = config[CONF_RESOURCE]
            self._rendered_resource = self._resource
        else:
            self._res_is_template = True
            self._resource = config[CONF_RESOURCE_TEMPLATE]
            self._resource.hass = hass
            self._update_rendered_resource()
        self._state_resource: str = (
            config.get(CONF_STATE_RESOURCE) or self._rendered_resource
        )
        self._method: str = config[CONF_METHOD]
        self._headers: dict[str, template.Template] | None = config.get(CONF_HEADERS)
        self._params: dict[str, template.Template] | None = config.get(CONF_PARAMS)
        self._auth = auth
        self._body_on: template.Template = config[CONF_BODY_ON]
        self._body_off: template.Template = config[CONF_BODY_OFF]
        self._is_on_template: template.Template | None = config.get(CONF_IS_ON_TEMPLATE)
        self._timeout: int = config[CONF_TIMEOUT]
        self._verify_ssl: bool = config[CONF_VERIFY_SSL]

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._body_on.hass = hass
        self._body_off.hass = hass
        if (is_on_template := self._is_on_template) is not None:
            is_on_template.hass = hass

        template.attach(hass, self._headers)
        template.attach(hass, self._params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        body_on_t = self._body_on.async_render(parse_result=False)

        try:
            req = await self.set_device_state(body_on_t)

            if req.status == HTTPStatus.OK:
                self._attr_is_on = True
            else:
                _LOGGER.error(
                    "Can't turn on %s. Is resource/endpoint offline?",
                    self._rendered_resource,
                )
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while switching on %s", self._rendered_resource)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        body_off_t = self._body_off.async_render(parse_result=False)

        try:
            req = await self.set_device_state(body_off_t)
            if req.status == HTTPStatus.OK:
                self._attr_is_on = False
            else:
                _LOGGER.error(
                    "Can't turn off %s. Is resource/endpoint offline?",
                    self._rendered_resource,
                )
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while switching off %s", self._rendered_resource)

    async def set_device_state(self, body: Any) -> aiohttp.ClientResponse:
        """Send a state update to the device."""
        websession = async_get_clientsession(self.hass, self._verify_ssl)

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)
        self._update_rendered_resource()

        async with async_timeout.timeout(self._timeout):
            req: aiohttp.ClientResponse = await getattr(websession, self._method)(
                self._rendered_resource,
                auth=self._auth,
                data=bytes(body, "utf-8"),
                headers=rendered_headers,
                params=rendered_params,
            )
            return req

    async def async_update(self) -> None:
        """Get the current state, catching errors."""
        try:
            await self.get_device_state(self.hass)
        except asyncio.TimeoutError:
            _LOGGER.exception("Timed out while fetching data")
        except aiohttp.ClientError as err:
            _LOGGER.exception("Error while fetching data: %s", err)

    async def get_device_state(self, hass: HomeAssistant) -> aiohttp.ClientResponse:
        """Get the latest data from REST API and update the state."""
        websession = async_get_clientsession(hass, self._verify_ssl)

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        async with async_timeout.timeout(self._timeout):
            req = await websession.get(
                self._state_resource,
                auth=self._auth,
                headers=rendered_headers,
                params=rendered_params,
            )
            text = await req.text()

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
        else:
            if text == self._body_on.template:
                self._attr_is_on = True
            elif text == self._body_off.template:
                self._attr_is_on = False
            else:
                self._attr_is_on = None

        return req

    def _update_rendered_resource(self) -> None:
        if self._res_is_template:
            self._rendered_resource = (
                self._resource.async_render_with_possible_json_value(
                    self._resource, "http://127.0.0.1"
                )
            )
        else:
            self._rendered_resource = self._resource
