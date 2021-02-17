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
    CONF_REST,
    DOMAIN,
    PLATFORMS,
    RESOURCE_SCHEMA,
    create_rest_from_config,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **BINARY_SENSOR_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the REST binary sensor."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    force_update = config.get(CONF_FORCE_UPDATE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    rest = config.get(CONF_REST)

    if not rest:
        rest = create_rest_from_config(config)
        await rest.async_update()

    if rest.data is None:
        raise PlatformNotReady

    async_add_entities(
        [
            RestBinarySensor(
                hass,
                rest,
                name,
                device_class,
                value_template,
                force_update,
                resource_template,
            )
        ],
    )


class RestBinarySensor(BinarySensorEntity):
    """Representation of a REST binary sensor."""

    def __init__(
        self,
        hass,
        rest,
        name,
        device_class,
        value_template,
        force_update,
        resource_template,
    ):
        """Initialize a REST binary sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._device_class = device_class
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self._force_update = force_update
        self._resource_template = resource_template

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self.rest.data is not None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.rest.data is None:
            return False

        response = self.rest.data

        if self._value_template is not None:
            response = self._value_template.async_render_with_possible_json_value(
                self.rest.data, False
            )

        try:
            return bool(int(response))
        except ValueError:
            return {"true": True, "on": True, "open": True, "yes": True}.get(
                response.lower(), False
            )

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    async def async_update(self):
        """Get the latest data from REST API and updates the state."""
        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.async_render(parse_result=False))

        await self.rest.async_update()
