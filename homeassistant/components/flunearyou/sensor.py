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
    TOPIC_UPDATE,
)

ATTR_CITY = "city"
ATTR_REPORTED_DATE = "reported_date"
ATTR_REPORTED_LATITUDE = "reported_latitude"
ATTR_REPORTED_LONGITUDE = "reported_longitude"
ATTR_STATE_REPORTS_LAST_WEEK = "state_reports_last_week"
ATTR_STATE_REPORTS_THIS_WEEK = "state_reports_this_week"
ATTR_ZIP_CODE = "zip_code"

DEFAULT_ATTRIBUTION = "Data provided by Flu Near You"

TYPE_CDC_LEVEL = "level"
TYPE_CDC_LEVEL2 = "level2"
TYPE_USER_CHICK = "chick"
TYPE_USER_DENGUE = "dengue"
TYPE_USER_FLU = "flu"
TYPE_USER_LEPTO = "lepto"
TYPE_USER_NO_SYMPTOMS = "none"
TYPE_USER_SYMPTOMS = "symptoms"
TYPE_USER_TOTAL = "total"

EXTENDED_TYPE_MAPPING = {
    TYPE_USER_FLU: "ili",
    TYPE_USER_NO_SYMPTOMS: "no_symptoms",
    TYPE_USER_TOTAL: "total_surveys",
}

SENSORS = {
    CATEGORY_CDC_REPORT: [
        (TYPE_CDC_LEVEL, "CDC Level", "mdi:biohazard", None),
        (TYPE_CDC_LEVEL2, "CDC Level 2", "mdi:biohazard", None),
    ],
    CATEGORY_USER_REPORT: [
        (TYPE_USER_CHICK, "Avian Flu Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_DENGUE, "Dengue Fever Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_FLU, "Flu Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_LEPTO, "Leptospirosis Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_NO_SYMPTOMS, "No Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_SYMPTOMS, "Flu-like Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_TOTAL, "Total Symptoms", "mdi:alert", "reports"),
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Flu Near You sensors based on a config entry."""
    fny = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]

    async_add_entities(
        [
            FluNearYouSensor(fny, kind, name, category, icon, unit)
            for category, sensors in SENSORS.items()
            for kind, name, icon, unit in sensors
        ],
        True,
    )


class FluNearYouSensor(Entity):
    """Define a base Flu Near You sensor."""

    def __init__(self, fny, kind, name, category, icon, unit):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._async_unsub_dispatcher_connect = None
        self._category = category
        self._fny = fny
        self._icon = icon
        self._kind = kind
        self._name = name
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
        return f"{self._fny.latitude},{self._fny.longitude}_{self._kind}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_write_ha_state()

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_update(self):
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
            self._state = cdc_data[self._kind]
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

            if self._kind in user_data["state"]["data"]:
                states_key = self._kind
            elif self._kind in EXTENDED_TYPE_MAPPING:
                states_key = EXTENDED_TYPE_MAPPING[self._kind]

            self._attrs[ATTR_STATE_REPORTS_THIS_WEEK] = user_data["state"]["data"][
                states_key
            ]
            self._attrs[ATTR_STATE_REPORTS_LAST_WEEK] = user_data["state"][
                "last_week_data"
            ][states_key]

            if self._kind == TYPE_USER_TOTAL:
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
                self._state = user_data["local"][self._kind]

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
            self._async_unsub_dispatcher_connect = None
