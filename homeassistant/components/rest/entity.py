"""The base entity for the rest component."""

from abc import abstractmethod
import logging
import ssl
from typing import override

from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .data import RestData

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_config_rest_data_and_coordinator(
    hass: HomeAssistant,
    config: ConfigType,
    entity_domain: str,
    discovery_info: DiscoveryInfoType | None = None,
) -> tuple[ConfigType, RestData, DataUpdateCoordinator[None] | None]:
    """Get the config, rest data +/- coordinator for sub entity."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, entity_domain, discovery_info
        )
    else:
        conf = config
        coordinator = None
        rest = create_rest_data_from_config(hass, conf)
        await rest.async_update(log_errors=False)

    if rest.data is None:
        if rest.last_exception:
            if isinstance(rest.last_exception, ssl.SSLError):
                _LOGGER.error(
                    "Error connecting %s failed with %s",
                    rest.url,
                    rest.last_exception,
                )
                raise HomeAssistantError from rest.last_exception
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    return conf, rest, coordinator


def async_get_trigger_entity_config(
    hass: HomeAssistant,
    config: ConfigType,
    default_name: str,
) -> ConfigType:
    """Get trigger entity config."""

    trigger_entity_config = {
        CONF_NAME: config.get(CONF_NAME, Template(default_name, hass))
    }
    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in config:
            continue
        trigger_entity_config[key] = config[key]
    return trigger_entity_config


class RestEntity(Entity):
    """A class for entities using DataUpdateCoordinator or rest data directly."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[None] | None,
        rest: RestData,
        resource_template: Template | None,
        force_update: bool,
    ) -> None:
        """Create the entity that may have a coordinator."""
        self._coordinator = coordinator
        self.rest = rest
        self._resource_template = resource_template
        self._attr_should_poll = not coordinator
        self._attr_force_update = force_update

    @property
    @override
    def available(self) -> bool:
        """Return the availability of this sensor."""
        if self._coordinator and not self._coordinator.last_update_success:
            return False
        return self.rest.data is not None

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_from_rest_data()
        if self._coordinator:
            self.async_on_remove(
                self._coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_rest_data()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from REST API and update the state."""
        if self._coordinator:
            await self._coordinator.async_request_refresh()
            return

        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.async_render(parse_result=False))
        await self.rest.async_update()
        self._update_from_rest_data()

    @abstractmethod
    def _update_from_rest_data(self) -> None:
        """Update state from the rest data."""
