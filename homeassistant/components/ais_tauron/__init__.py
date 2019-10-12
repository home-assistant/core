"""Support for Tauron sensors."""
import datetime
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_MONITORED_VARIABLES,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_METER_ID,
    CONF_URL_SERVICE,
    CONF_URL_LOGIN,
    CONF_URL_CHARTS,
    CONF_REQUEST_HEADERS,
    CONF_REQUEST_PAYLOAD_CHARTS,
    ZONE,
    CONSUMPTION_DAILY,
    CONSUMPTION_MONTHLY,
    CONSUMPTION_YEARLY,
    TARIFF_G12,
)

_LOGGER = logging.getLogger(__name__)


MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=600)


SENSOR_TYPES = {
    ZONE: [timedelta(minutes=1), None],
    CONSUMPTION_DAILY: [timedelta(hours=1), "kWh"],
    CONSUMPTION_MONTHLY: [timedelta(hours=1), "kWh"],
    CONSUMPTION_YEARLY: [timedelta(hours=1), "kWh"],
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_METER_ID): cv.string,
    }
)


async def async_setup(hass, config):
    """Set up the TAURON component."""
    hass.data[DOMAIN] = {}

    # if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
    #     server_confs = config[DOMAIN][CONF_SERVERS]
    #
    #     for server_conf in server_confs:
    #         hass.async_create_task(
    #             hass.config_entries.flow.async_init(
    #                 DOMAIN, context={"source": SOURCE_IMPORT}, data=server_conf
    #             )
    #         )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up SUPLA as config entry."""
    _LOGGER.info("TAURON async_setup_entry")
    # if DOMAIN not in hass.data:
    #     hass.data[DOMAIN] = {}
    # hass.async_create_task(async_discover_devices(hass, config_entry))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # TODO await hass.config_entries.async_forward_entry_unload(config_entry, "xxx")
    return True


def setup_platform(hass, config, add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(
            TauronAmiplusSensor(
                name,
                username,
                password,
                meter_id,
                variable,
                SENSOR_TYPES[variable][1],
                SENSOR_TYPES[variable][0],
            )
        )
    add_entities(dev, True)


def calculate_configuration(username, password, meter_id, days_before=2):
    payload_login = {
        "username": username,
        "password": password,
        "service": CONF_URL_SERVICE,
    }
    session = requests.session()
    session.request(
        "POST", CONF_URL_LOGIN, data=payload_login, headers=CONF_REQUEST_HEADERS
    )
    session.request(
        "POST", CONF_URL_LOGIN, data=payload_login, headers=CONF_REQUEST_HEADERS
    )
    config_date = datetime.datetime.now() - datetime.timedelta(days_before)
    payload = {
        "dane[chartDay]": config_date.strftime("%d.%m.%Y"),
        "dane[paramType]": "day",
        "dane[smartNr]": meter_id,
        "dane[chartType]": 1,
    }
    response = session.request(
        "POST",
        CONF_URL_CHARTS,
        data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
        headers=CONF_REQUEST_HEADERS,
    )
    json_data = response.json()
    zones = json_data["dane"]["zone"]
    parsed_zones = []
    for zone in zones:
        start = datetime.time(hour=int(zone["start"][11:]))
        stop = datetime.time(hour=int(zone["stop"][11:]))
        parsed_zones.append({"start": start, "stop": stop})
    calculated_zones = []
    for i in range(0, len(parsed_zones)):
        next_i = (i + 1) % len(parsed_zones)
        start = datetime.time(parsed_zones[i]["stop"].hour)
        stop = datetime.time(parsed_zones[next_i]["start"].hour)
        calculated_zones.append({"start": start, "stop": stop})
    power_zones = {1: parsed_zones, 2: calculated_zones}
    tariff = json_data["dane"]["chart"][0]["Taryfa"]
    return power_zones, tariff, config_date.strftime("%d.%m.%Y, %H:%M")


class TauronAmiplusSensor(Entity):
    def __init__(
        self, name, username, password, meter_id, sensor_type, unit, interval: timedelta
    ):
        self.client_name = name
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.sensor_type = sensor_type
        self.unit = unit
        configuration = calculate_configuration(username, password, meter_id)
        self.power_zones = configuration[0]
        self.mode = configuration[1]
        self.power_zones_last_update = configuration[2]
        self.power_zones_last_update_tech = datetime.datetime.now() - datetime.timedelta(
            days=1
        )
        self.data = None
        self.params = {}
        self._state = None
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        return "{} {}".format(self.client_name, self.sensor_type)

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        _params = {
            "tariff": self.mode,
            "updated": self.power_zones_last_update,
            **self.params,
        }
        return _params

    @property
    def unit_of_measurement(self):
        return self.unit

    @property
    def icon(self):
        return "mdi:counter"

    def _update(self):
        self.update_configuration()
        if self.sensor_type == ZONE:
            self.update_zone()
        elif self.sensor_type == CONSUMPTION_DAILY:
            self.update_consumption_daily()
        elif self.sensor_type == CONSUMPTION_MONTHLY:
            self.update_consumption_monthly()
        elif self.sensor_type == CONSUMPTION_YEARLY:
            self.update_consumption_yearly()

    def get_session(self):
        payload_login = {
            "username": self.username,
            "password": self.password,
            "service": CONF_URL_SERVICE,
        }
        session = requests.session()
        session.request(
            "POST", CONF_URL_LOGIN, data=payload_login, headers=CONF_REQUEST_HEADERS
        )
        session.request(
            "POST", CONF_URL_LOGIN, data=payload_login, headers=CONF_REQUEST_HEADERS
        )
        return session

    def update_configuration(self):
        now_datetime = datetime.datetime.now()
        if (
            now_datetime - datetime.timedelta(days=1)
        ) >= self.power_zones_last_update_tech and now_datetime.hour >= 10:
            config = calculate_configuration(
                self.username, self.password, self.meter_id, 1
            )
            self.power_zones = config[0]
            self.mode = config[1]
            self.power_zones_last_update = config[2]
            self.power_zones_last_update_tech = now_datetime

    def update_zone(self):
        if self.mode == TARIFF_G12:
            parsed_zones = self.power_zones[1]
            now_time = datetime.datetime.now().time()
            if (
                len(
                    list(
                        filter(
                            lambda x: x["start"] <= now_time < x["stop"], parsed_zones
                        )
                    )
                )
                > 0
            ):
                self._state = 1
            else:
                self._state = 2
            self.params = {}
            for power_zone in self.power_zones:
                pz_name = "zone{} ".format(power_zone)
                pz = (
                    str(
                        list(
                            map(
                                lambda x: x["start"].strftime("%H:%M")
                                + " - "
                                + x["stop"].strftime("%H:%M"),
                                self.power_zones[power_zone],
                            )
                        )
                    )
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
                self.params[pz_name] = pz
        else:
            self._state = 1

    def update_consumption_daily(self):
        session = self.get_session()
        payload = {
            "dane[chartDay]": (
                datetime.datetime.now() - datetime.timedelta(1)
            ).strftime("%d.%m.%Y"),
            "dane[paramType]": "day",
            "dane[smartNr]": self.meter_id,
            "dane[chartType]": 2,
        }
        response = session.request(
            "POST",
            CONF_URL_CHARTS,
            data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
            headers=CONF_REQUEST_HEADERS,
        )
        correct_data = False
        if (
            response.status_code == 200
            and response.text.startswith('{"name"')
            and response.json()["isFull"]
        ):
            correct_data = True
        else:
            session = self.get_session()
            payload = {
                "dane[chartDay]": (
                    datetime.datetime.now() - datetime.timedelta(2)
                ).strftime("%d.%m.%Y"),
                "dane[paramType]": "day",
                "dane[smartNr]": self.meter_id,
                "dane[chartType]": 2,
            }
            response = session.request(
                "POST",
                CONF_URL_CHARTS,
                data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
                headers=CONF_REQUEST_HEADERS,
            )
            if response.status_code == 200 and response.text.startswith('{"name"'):
                correct_data = True
        if correct_data:
            json_data = response.json()
            self._state = round(float(json_data["sum"]), 3)
            if self.mode == TARIFF_G12:
                values = json_data["dane"]["chart"]
                z1 = list(filter(lambda x: x["Zone"] == "1", values))
                z2 = list(filter(lambda x: x["Zone"] == "2", values))
                sum_z1 = round(sum(float(val["EC"]) for val in z1), 3)
                sum_z2 = round(sum(float(val["EC"]) for val in z2), 3)
                day = values[0]["Date"]
                self.params = {"zone1": sum_z1, "zone2": sum_z2, "day": day}

    def update_consumption_monthly(self):
        session = self.get_session()
        payload = {
            "dane[chartMonth]": datetime.datetime.now().month,
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "month",
            "dane[smartNr]": self.meter_id,
            "dane[chartType]": 2,
        }
        response = session.request(
            "POST",
            CONF_URL_CHARTS,
            data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
            headers=CONF_REQUEST_HEADERS,
        )
        if response.status_code == 200 and response.text.startswith('{"name"'):
            json_data = response.json()
            self._state = round(float(json_data["sum"]), 3)
            if self.mode == TARIFF_G12:
                values = json_data["dane"]["chart"]
                z1 = list(filter(lambda x: "tariff1" in x, values))
                z2 = list(filter(lambda x: "tariff2" in x, values))
                sum_z1 = round(sum(float(val["tariff1"]) for val in z1), 3)
                sum_z2 = round(sum(float(val["tariff2"]) for val in z2), 3)
                self.params = {"zone1": sum_z1, "zone2": sum_z2}

    def update_consumption_yearly(self):
        session = self.get_session()
        payload = {
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "year",
            "dane[smartNr]": self.meter_id,
            "dane[chartType]": 2,
        }
        response = session.request(
            "POST",
            CONF_URL_CHARTS,
            data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
            headers=CONF_REQUEST_HEADERS,
        )
        if response.status_code == 200 and response.text.startswith('{"name"'):
            json_data = response.json()
            self._state = round(float(json_data["sum"]), 3)
            if self.mode == TARIFF_G12:
                values = json_data["dane"]["chart"]
                z1 = list(filter(lambda x: "tariff1" in x, values))
                z2 = list(filter(lambda x: "tariff2" in x, values))
                sum_z1 = round(sum(float(val["tariff1"]) for val in z1), 3)
                sum_z2 = round(sum(float(val["tariff2"]) for val in z2), 3)
                self.params = {"zone1": sum_z1, "zone2": sum_z2}


# sadsadsad


#
#
# async def async_discover_devices(hass, config_entry):
#     """
#     Run periodically to discover new devices.
#
#     Currently it's only run at startup.
#     """
#
#     server = SuplaAPI(
#         config_entry.data[CONF_SERVER], config_entry.data[CONF_ACCESS_TOKEN]
#     )
#
#     hass.data[DOMAIN][CONF_SERVER][config_entry.entry_id] = server
#     component_configs = {}
#
#     for channel in server.get_channels(include=["iodevice"]):
#         channel_function = channel["function"]["name"]
#         component_name = SUPLA_FUNCTION_HA_CMP_MAP.get(channel_function)
#
#         if component_name is None:
#             _LOGGER.warning(
#                 "Unsupported function: %s, channel id: %s",
#                 channel_function,
#                 channel["id"],
#             )
#             continue
#
#         component_configs.setdefault(component_name, []).append(channel)
#
#     for component_name, channel in component_configs.items():
#         hass.data[DOMAIN][CONF_CHANNELS][component_name] = channel
#         hass.async_create_task(
#             hass.config_entries.async_forward_entry_setup(config_entry, component_name)
#         )
#
#
# class SuplaChannel(Entity):
#     """Base class of a Supla Channel (an equivalent of HA's Entity)."""
#
#     def __init__(self, channel_data, supla_server):
#         """Channel data -- raw channel information from PySupla."""
#         self.channel_data = channel_data
#         self.supla_server = supla_server
#
#     @property
#     def device_info(self):
#         return {
#             "identifiers": {(DOMAIN, self.channel_data["iodevice"]["gUIDString"])},
#             "name": "SUPLA",
#             "manufacturer": "ZAMEL Sp. z oo",
#             "model": self.channel_data["function"]["name"],
#             "sw_version": self.channel_data["iodevice"]["softwareVersion"],
#             "via_device": None,
#         }
#
#     @property
#     def server(self):
#         """Return PySupla's server component associated with entity."""
#         return self.supla_server
#
#     @property
#     def unique_id(self) -> str:
#         """Return a unique ID."""
#         return "supla-{}-{}".format(
#             self.channel_data["iodevice"]["gUIDString"].lower(),
#             self.channel_data["channelNumber"],
#         )
#
#     @property
#     def name(self) -> Optional[str]:
#         """Return the name of the device."""
#         if "iodevice" in self.channel_data:
#             if "comment" in self.channel_data["iodevice"]:
#                 return self.channel_data["iodevice"]["comment"]
#             if "name" in self.channel_data["iodevice"]:
#                 return "supla: " + self.channel_data["iodevice"]["name"]
#         if "caption" in self.channel_data:
#             return self.channel_data["caption"]
#         if "type" in self.channel_data:
#             return "supla: " + self.channel_data["type"]["caption"]
#         return ""
#
#     def action(self, action, **add_pars):
#         """
#         Run server action.
#
#         Actions are currently hardcoded in components.
#         Supla's API enables autodiscovery
#         """
#         _LOGGER.debug(
#             "Executing action %s on channel %d, params: %s",
#             action,
#             self.channel_data["id"],
#             add_pars,
#         )
#         self.server.execute_action(self.channel_data["id"], action, **add_pars)
#
#     def update(self):
#         """Call to update state."""
#         self.channel_data = self.server.get_channel(
#             self.channel_data["id"], include=["connected", "state"]
#         )
