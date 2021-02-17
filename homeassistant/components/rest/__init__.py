"""The rest component."""


import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import RestData
from .schema import CONFIG_SCHEMA  # noqa:F401 pylint: disable=unused-import
from .schema import CONF_COORDINATOR, CONF_REST

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rest"
PLATFORMS = ["binary_sensor", "notify", "sensor", "switch"]
COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the rest platforms."""
    component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await _async_process_config(hass, conf)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return await _async_process_config(hass, config)


async def _async_process_config(hass, config) -> bool:
    """Process rest configuration."""
    if DOMAIN not in config:
        return True

    for conf in config[DOMAIN]:
        scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        rest = create_rest_data_from_config(hass, conf)
        coordinator = _wrap_rest_in_coordinator(hass, rest, scan_interval)
        await coordinator.async_refresh()

        for platform_domain in COORDINATOR_AWARE_PLATFORMS:
            for platform_conf in conf.get(platform_domain, []):
                discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {CONF_REST: rest, CONF_COORDINATOR: coordinator, **platform_conf},
                    config,
                )

    return True


def _wrap_rest_in_coordinator(hass, rest, update_interval):
    """Wrap a DataUpdateCoordinator around the rest object."""
    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="rest data",
        update_method=rest.async_refresh,
        update_interval=update_interval,
    )


def create_rest_data_from_config(hass, config):
    """Create RestData from config."""
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    timeout = config.get(CONF_TIMEOUT)

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.async_render(parse_result=False)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)
    else:
        auth = None

    return RestData(
        hass, method, resource, auth, headers, params, payload, verify_ssl, timeout
    )


class RestEntity(Entity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        name,
        device_class,
        resource_template,
        force_update,
    ) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator
        self._name = name
        self._device_class = device_class
        self._resource_template = resource_template
        self._force_update = force_update
        super().__init__()

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def should_poll(self) -> bool:
        """Poll only if we do noty have a coordinator."""
        return not self.coordinator

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator:
            return True
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_from_rest_data()
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_rest_data()
        self.async_write_ha_state()

    async def async_update(self):
        """Get the latest data from REST API and update the state."""
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.async_render(parse_result=False))

        if self.coordinator:
            await self.coordinator.async_request_refresh()
            return

        await self.rest.async_update()
        self._update_from_rest_data()
