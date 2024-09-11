"""Support for the myStrom buttons."""

from __future__ import annotations

from http import HTTPStatus
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorEntity
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up myStrom Binary Sensor."""
    hass.http.register_view(MyStromView(async_add_entities))


class MyStromView(HomeAssistantView):
    """View to handle requests from myStrom buttons."""

    url = "/api/mystrom"
    name = "api:mystrom"
    supported_actions = ["single", "double", "long", "touch"]

    def __init__(self, add_entities):
        """Initialize the myStrom URL endpoint."""
        self.buttons = {}
        self.add_entities = add_entities

    async def get(self, request):
        """Handle the GET request received from a myStrom button."""
        return await self._handle(request.app[KEY_HASS], request.query)

    async def _handle(self, hass, data):
        """Handle requests to the myStrom endpoint."""
        button_action = next(
            (parameter for parameter in data if parameter in self.supported_actions),
            None,
        )

        if button_action is None:
            _LOGGER.error("Received unidentified message from myStrom button: %s", data)
            return (
                f"Received unidentified message: {data}",
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        button_id = data[button_action]
        entity_id = f"{DOMAIN}.{button_id}_{button_action}"
        if entity_id not in self.buttons:
            _LOGGER.info(
                "New myStrom button/action detected: %s/%s", button_id, button_action
            )
            self.buttons[entity_id] = MyStromBinarySensor(
                f"{button_id}_{button_action}"
            )
            self.add_entities([self.buttons[entity_id]])
        else:
            new_state = self.buttons[entity_id].state == "off"
            self.buttons[entity_id].async_on_update(new_state)
        return None


class MyStromBinarySensor(BinarySensorEntity):
    """Representation of a myStrom button."""

    _attr_should_poll = False

    def __init__(self, button_id):
        """Initialize the myStrom Binary sensor."""
        self._button_id = button_id
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._button_id

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @callback
    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_write_ha_state()
