"""Sensor platform for FireServiceRota integration."""
import logging
import threading
from typing import Any, Dict

from pyfireservicerota import FireServiceRotaIncidents

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_TOKEN, CONF_URL
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTRIBUTION,
    DOMAIN,
    SENSOR_ENTITY_LIST,
    SIGNAL_UPDATE_INCIDENTS,
    WSS_BWRURL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota sensor based on a config entry."""
    incidents_data = IncidentsDataProvider(hass, entry)
    unique_id = entry.unique_id

    entities = []
    for (
        sensor_type,
        (name, unit, icon, device_class, enabled_by_default),
    ) in SENSOR_ENTITY_LIST.items():

        _LOGGER.debug(
            "Registering entity: %s, %s, %s, %s, %s, %s",
            sensor_type,
            name,
            unit,
            icon,
            device_class,
            enabled_by_default,
        )
        entities.append(
            IncidentsSensor(
                incidents_data,
                unique_id,
                sensor_type,
                name,
                unit,
                icon,
                device_class,
                enabled_by_default,
            )
        )

    async_add_entities(entities, True)


class IncidentsDataProvider:
    """Open a websocket connection to FireServiceRota to get incidents data."""

    def __init__(self, hass, entry):
        """Initialize the data object."""
        self._hass = hass
        self._entry = entry

        self._token_info = self._entry.data[CONF_TOKEN]
        self._wsurl = WSS_BWRURL.format(
            self._entry.data[CONF_URL], self._token_info["access_token"]
        )
        self._data = None

        self._listener = None
        self._thread = threading.Thread(target=self.incidents_listener)
        self._thread.daemon = True
        self._thread.start()

    def on_incident(self, data):
        """Update the current data."""
        _LOGGER.debug("Got data from listener: %s", data)
        self._data = data
        self._hass.data[DOMAIN].set_incident_data(data)

        async_dispatcher_send(self._hass, SIGNAL_UPDATE_INCIDENTS)

    @property
    def data(self):
        """Return the current data."""
        return self._data

    @staticmethod
    def on_close():
        """Log websocket close and restart listener."""
        _LOGGER.debug("Websocket closed")
        # return

    def incidents_listener(self):
        """(re)start a websocket listener."""
        while True:
            try:
                _LOGGER.debug("Starting incidents listener forever")
                self._listener = FireServiceRotaIncidents(
                    url=self._wsurl,
                    on_incident=self.on_incident,
                    on_close=self.on_close,
                )
                self._listener.run_forever()
            except ConnectionAbortedError:
                pass


class IncidentsSensor(RestoreEntity):
    """Representation of FireServiceRota incidents sensor."""

    def __init__(
        self,
        data,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        device_class,
        enabled_default: bool = True,
    ):
        """Initialize."""
        self._data = data
        self._unique_id = unique_id
        self._type = sensor_type
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._enabled_default = enabled_default
        self._available = True
        self._state = None
        self._state_attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self._unique_id}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return available attributes for sensor."""
        attr = {}
        data = self._state_attributes

        if data:
            for value in (
                "id",
                "trigger",
                "state",
                "created_at",
                "start_time",
                "location",
                "message_to_speech_url",
                "prio",
                "type",
                "responder_mode",
                "can_respond_until",
            ):
                if data.get(value):
                    attr[value] = data[value]

            try:
                for address_value in (
                    "address_line1",
                    "address_line2",
                    "street_name",
                    "house_number",
                    "postcode",
                    "city",
                    "country",
                    "state",
                    "latitude",
                    "longitude",
                    "address_type",
                    "formatted_address",
                ):
                    attr[address_value] = data.get("address").get(address_value)
            except (KeyError, TypeError):
                pass

            attr[ATTR_ATTRIBUTION] = ATTRIBUTION
            return attr

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": f"{self._name} Sensor",
            "manufacturer": "FireServiceRota",
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            self._state_attributes = state.attributes

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_INCIDENTS, self.async_on_demand_update
            )
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update using FireServiceRota data."""
        if not self.enabled:
            return

        try:
            self._state = self._data.data["body"]
            self._state_attributes = self._data.data
        except (KeyError, TypeError):
            pass

        _LOGGER.debug("Entity state changed to: %s", self._state)
