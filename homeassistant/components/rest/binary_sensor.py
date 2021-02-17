"""Support for RESTful binary sensors."""
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service

from . import (
    BINARY_SENSOR_SCHEMA,
    CONF_COORDINATOR,
    CONF_REST,
    DOMAIN,
    PLATFORMS,
    RESOURCE_SCHEMA,
    RestEntity,
    create_rest_from_config,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **BINARY_SENSOR_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the REST binary sensor."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    conf = discovery_info or config

    name = conf.get(CONF_NAME)
    device_class = conf.get(CONF_DEVICE_CLASS)
    value_template = conf.get(CONF_VALUE_TEMPLATE)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    rest = conf.get(CONF_REST)
    coordinator = conf.get(CONF_COORDINATOR)

    if coordinator:
        if rest.data is None:
            await coordinator.async_request_refresh()
    else:
        rest = create_rest_from_config(conf)
        await rest.async_update()

    if rest.data is None:
        raise PlatformNotReady

    async_add_entities(
        [
            RestBinarySensor(
                coordinator,
                rest,
                name,
                device_class,
                value_template,
                force_update,
                resource_template,
            )
        ],
    )


class RestBinarySensor(RestEntity, BinarySensorEntity):
    """Representation of a REST binary sensor."""

    def __init__(
        self,
        coordinator,
        rest,
        name,
        device_class,
        value_template,
        force_update,
        resource_template,
    ):
        """Initialize a REST binary sensor."""
        super.__init__(coordinator, name, device_class, resource_template, force_update)
        self.rest = rest
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self._is_on = None

    @property
    def available(self):
        """Return the availability of this sensor."""
        if not super().available:
            return False
        return self.rest.data is not None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    def _update_from_rest_data(self):
        """Update state from the rest data."""
        if self.rest.data is None:
            self._is_on = False

        response = self.rest.data

        if self._value_template is not None:
            response = self._value_template.async_render_with_possible_json_value(
                self.rest.data, False
            )

        try:
            self._is_on = bool(int(response))
        except ValueError:
            self._is_on = {"true": True, "on": True, "open": True, "yes": True}.get(
                response.lower(), False
            )
