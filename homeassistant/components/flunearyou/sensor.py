"""Support for user- and CDC-based flu info sensors from Flu Near You."""
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_STATE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CATEGORY_CDC_REPORT,
    CATEGORY_USER_REPORT,
    DATA_CLIENT,
    DOMAIN,
    SENSORS,
    TOPIC_UPDATE,
    TYPE_USER_CHICK,
    TYPE_USER_DENGUE,
    TYPE_USER_FLU,
    TYPE_USER_LEPTO,
    TYPE_USER_NO_SYMPTOMS,
    TYPE_USER_SYMPTOMS,
    TYPE_USER_TOTAL,
)

ATTR_CITY = "city"
ATTR_REPORTED_DATE = "reported_date"
ATTR_REPORTED_LATITUDE = "reported_latitude"
ATTR_REPORTED_LONGITUDE = "reported_longitude"
ATTR_STATE_REPORTS_LAST_WEEK = "state_reports_last_week"
ATTR_STATE_REPORTS_THIS_WEEK = "state_reports_this_week"
ATTR_ZIP_CODE = "zip_code"

DEFAULT_ATTRIBUTION = "Data provided by Flu Near You"

EXTENDED_TYPE_MAPPING = {
    TYPE_USER_FLU: "ili",
    TYPE_USER_NO_SYMPTOMS: "no_symptoms",
    TYPE_USER_TOTAL: "total_surveys",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Flu Near You sensors based on a config entry."""
    fny = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]

    async_add_entities(
        [
            FluNearYouSensor(fny, sensor_type, name, category, icon, unit)
            for category, sensors in SENSORS.items()
            for sensor_type, name, icon, unit in sensors
        ],
        True,
    )


class FluNearYouSensor(Entity):
    """Define a base Flu Near You sensor."""

    def __init__(self, fny, sensor_type, name, category, icon, unit):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._category = category
        self._fny = fny
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._fny.data[self._category])

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._fny.latitude},{self._fny.longitude}_{self._sensor_type}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, TOPIC_UPDATE, update))
        await self._fny.async_register_api_interest(self._sensor_type)
        self.update_from_latest_data()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        self._fny.async_deregister_api_interest(self._sensor_type)

    @callback
    def update_from_latest_data(self):
        """Update the sensor."""
        cdc_data = self._fny.data.get(CATEGORY_CDC_REPORT)
        user_data = self._fny.data.get(CATEGORY_USER_REPORT)

        if self._category == CATEGORY_CDC_REPORT and cdc_data:
            self._attrs.update(
                {
                    ATTR_REPORTED_DATE: cdc_data["week_date"],
                    ATTR_STATE: cdc_data["name"],
                }
            )
            self._state = cdc_data[self._sensor_type]
        elif self._category == CATEGORY_USER_REPORT and user_data:
            self._attrs.update(
                {
                    ATTR_CITY: user_data["local"]["city"].split("(")[0],
                    ATTR_REPORTED_LATITUDE: user_data["local"]["latitude"],
                    ATTR_REPORTED_LONGITUDE: user_data["local"]["longitude"],
                    ATTR_STATE: user_data["state"]["name"],
                    ATTR_ZIP_CODE: user_data["local"]["zip"],
                }
            )

            if self._sensor_type in user_data["state"]["data"]:
                states_key = self._sensor_type
            elif self._sensor_type in EXTENDED_TYPE_MAPPING:
                states_key = EXTENDED_TYPE_MAPPING[self._sensor_type]

            self._attrs[ATTR_STATE_REPORTS_THIS_WEEK] = user_data["state"]["data"][
                states_key
            ]
            self._attrs[ATTR_STATE_REPORTS_LAST_WEEK] = user_data["state"][
                "last_week_data"
            ][states_key]

            if self._sensor_type == TYPE_USER_TOTAL:
                self._state = sum(
                    v
                    for k, v in user_data["local"].items()
                    if k
                    in (
                        TYPE_USER_CHICK,
                        TYPE_USER_DENGUE,
                        TYPE_USER_FLU,
                        TYPE_USER_LEPTO,
                        TYPE_USER_SYMPTOMS,
                    )
                )
            else:
                self._state = user_data["local"][self._sensor_type]
