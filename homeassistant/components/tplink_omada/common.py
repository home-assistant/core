"""Support for TP-Link routers."""
import json
import logging
from urllib.parse import urlparse

import aiodns
from aiodns.error import DNSError
import async_timeout

from homeassistant import exceptions
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import (
    CONF_DNSRESOLVE,
    CONF_SSLVERIFY,
    CONTROLLER_PATH,
    LOGIN_PATH,
    MIN_TIME_BETWEEN_UPDATES,
    SENSOR_AP_SETTINGS_DICT,
    SENSOR_AP_STATS_DICT,
    SENSOR_DICT,
    SENSOR_SSID_SETTINGS_DICT,
    SENSOR_SSID_STATS_DICT,
    SERVICE_WIFIACRULE_ATTR_RULE,
    SSID_SETTING_KEYS,
)

_LOGGER = logging.getLogger(__name__)


async def login(host, username, password, timeout, httpsession):
    """Login to the Omada Controller.

    This function returns an token

    :note: host variable should includes scheme and port (if not standard)
           ie https://192.168.1.2:8043
    """
    # Get SessionID
    with async_timeout.timeout(timeout):
        res = await httpsession.get(host)

    if "location" not in res.history[-1].headers:
        _LOGGER.exception("Can not find actual base host of the " "Omada Controller.")
        raise InvalidAuth("Can not find actual base host of the " "Omada Controller.")
    # Get actual URL
    actual_location = urlparse(res.history[-1].headers["location"])
    base_url = actual_location.scheme + "://" + actual_location.netloc
    # Login
    login_data = {"method": "login", "params": {"name": username, "password": password}}
    params = {"ajax": ""}
    with async_timeout.timeout(timeout):
        res = await httpsession.post(
            base_url + LOGIN_PATH, params=params, data=json.dumps(login_data),
        )
    res_json = await res.json()
    if res_json.get("msg") != "Log in successfully.":
        _LOGGER.exception(
            "Omada Controller didn't respond with JSON. "
            "Check if credentials are correct"
        )
        raise InvalidAuth(
            "Omada Controller didn't respond with JSON. "
            "Check if credentials are correct"
        )
    # Get token
    res_json = await res.json()
    token = res_json["result"]["token"]
    return base_url, token


class OmadaData:
    """Omada Client class."""

    def __init__(self, hass, entry):
        """Initialize the data object."""
        self._hass = hass
        self._entry = entry
        self.name = entry.data[CONF_NAME]
        self.host = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.timeout = entry.data[CONF_TIMEOUT]
        self.dns_resolver = None
        if entry.data[CONF_DNSRESOLVE]:
            self.dns_resolver = aiodns.DNSResolver()
        verify_tls = entry.data[CONF_SSLVERIFY]
        self.httpsession = async_get_clientsession(hass, verify_tls)

        self.version = None
        self.available = True
        self.data = {}
        self.ssid_stats = {}
        self.ssid_attrs = {}
        self.access_points_stats = {}
        self.access_points_settings = {}
        self._token = None
        self._base_url = None

    async def login(self):
        """Login to the Omada Controller."""
        logged = await login(
            self.host, self.username, self.password, self.timeout, self.httpsession
        )
        if not isinstance(logged, tuple) or len(logged) != 2:
            _LOGGER.error("Unable to login to Omada Controller %s", self.host)
            return False
        self._base_url = logged[0]
        self._token = logged[1]

        return True

    async def fetch_version(self):
        """Get the current version of the Omada Controller."""
        data = {"method": "getAboutInfo", "params": {}}
        params = {"aboutInfo": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
            res_json = await res.json()
        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching version: %s", res_json["msg"])
            return

        self.version = res_json["result"]["version"]

    async def fetch_global_stats(self):
        """Fetch the global statistics of the Omada Controller."""
        data = {"method": "getGlobalStat", "params": {}}
        params = {"globalStat": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
            res_json = await res.json()

        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching global stats: %s", res_json["msg"])
            return

        for sensor_name in SENSOR_DICT:
            if sensor_name in res_json["result"]:
                self.data[sensor_name] = res_json["result"][sensor_name]

    async def fetch_ssid_stats(self):
        """Get statistics for each SSID."""
        data = {"method": "getSsidStats", "params": {}}
        params = {"ssidStatsStore": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
            res_json = await res.json()

        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching ssid stats: %s", res_json["msg"])
            return

        for ssid_data in res_json["result"]["ssidList"]:
            ssid_name = ssid_data.pop("ssid")
            self.ssid_stats[ssid_name] = {}
            for stat_id, stat_data in SENSOR_SSID_STATS_DICT.items():
                if stat_id in ssid_data:
                    self.ssid_stats[ssid_name][stat_data[0]] = ssid_data[stat_id]

    async def fetch_ap_stats(self):
        """Get Access point stats."""
        data = {
            "method": "getGridAps",
            "params": {
                "sortOrder": "asc",
                "currentPage": 1,
                "currentPageSize": 10,
                "filters": {"status": "All"},
            },
        }
        params = {"apsStore": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
            res_json = await res.json()

        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching access points stats: %s", res_json["msg"])
            return

        for access_point in res_json["result"]["data"]:
            ap_mac = access_point.pop("mac")

            for sensor_name in access_point:
                if sensor_name in SENSOR_AP_STATS_DICT:
                    self.access_points_stats.setdefault(ap_mac, {})
                    self.access_points_stats[ap_mac][sensor_name] = access_point[
                        sensor_name
                    ]
                elif sensor_name in SENSOR_AP_SETTINGS_DICT:
                    self.access_points_settings.setdefault(ap_mac, {})
                    setting_name = SENSOR_AP_SETTINGS_DICT[sensor_name]
                    self.access_points_settings[ap_mac][setting_name] = access_point[
                        sensor_name
                    ]

    async def fetch_clients_list(self):
        """Get the list of the connected clients to the access points."""
        _LOGGER.debug("Loading wireless clients from Omada Controller...")
        current_page_size = 10

        current_page = 1
        total_rows = current_page_size + 1
        list_of_devices = {}
        while (current_page - 1) * current_page_size <= total_rows:
            data = {
                "method": "getGridActiveClients",
                "params": {
                    "sortOrder": "asc",
                    "currentPage": current_page,
                    "currentPageSize": current_page_size,
                    "filters": {"type": "all"},
                },
            }
            params = {"userStore": "", "token": self._token}
            with async_timeout.timeout(self.timeout):
                res = await self.httpsession.post(
                    self._base_url + CONTROLLER_PATH,
                    params=params,
                    data=json.dumps(data),
                )
                res_json = await res.json()
            if res_json["errorCode"] != 0:
                _LOGGER.error("Error fetching client list: %s", res_json["msg"])
                return
            results = res_json["result"]
            total_rows = results["totalRows"]
            for data in results["data"]:
                key = data["mac"].replace("-", ":")
                name = data["name"]
                # Search for a better device name
                if self.dns_resolver:
                    try:
                        result = await self.dns_resolver.gethostbyaddr(data["ip"])
                        name = result.name.split(".", 1)[0]
                    except DNSError:
                        _LOGGER.debug("Can not resolve %s", data["ip"])
                # Set default name from the mac address
                if not name:
                    name = data["mac"].replace("-", "_").lower()

                list_of_devices[key] = name.lower()
            current_page += 1

        if _LOGGER.level <= logging.DEBUG:
            msgs = []
            for mac, name in list_of_devices.items():
                msgs.append("{}: {}".format(mac, name))
            _LOGGER.debug("\nDevice count: %s\n%s", len(msgs), "\n".join(msgs))

        return list_of_devices

    async def fetch_ssid_attributes(self):
        """Get SSID attributes."""
        ssid_id_dict = await self.fetch_ssid_settings()

        for ssid_name, ssid_settings in ssid_id_dict.items():
            self.ssid_attrs[ssid_name] = {}
            for setting_id, setting_name in SENSOR_SSID_SETTINGS_DICT.items():
                if setting_id in ssid_settings:
                    self.ssid_attrs[ssid_name][setting_name] = ssid_settings[setting_id]

    async def fetch_ssid_settings(self):
        """Get the list of the SSIDs and their IDs."""
        data = {
            "method": "getGridSsid",
            "params": {
                "sortOrder": "asc",
                "currentPage": 1,
                "currentPageSize": 5,
                "filters": {},
            },
        }
        params = {"wlBasicSsidGridS": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
        res_json = await res.json()
        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching ssid settings: %s", res_json["msg"])
            return

        ssid_id_dict = {}

        for ssid in res_json["result"]["data"]:
            ssid_id_dict[ssid["name"]] = ssid

        return ssid_id_dict

    async def set_ssid_access_control_rule(self, ssid, access_control_rule):
        """Apply an access control rule to a ssid."""
        access_control_rule = access_control_rule or "None"
        ssid_id_dict = await self.fetch_ssid_settings()
        if ssid not in ssid_id_dict:
            _LOGGER.error("SSID %s not found", ssid)
            return

        data = {"method": "getSsid", "params": {"id": ssid_id_dict[ssid]["id"]}}
        params = {"wlBasicSsid24SettingsM": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
        res_json = await res.json()
        if res_json["errorCode"] != 0:
            _LOGGER.error("Error fetching ssid parame: %s", res_json["msg"])
            return

        ssid_settings = res_json["result"]

        ssid_params = {}
        for setting, value in ssid_settings.items():
            if setting in SSID_SETTING_KEYS:
                ssid_params[setting] = value

        ssid_params["accessControlRuleName"] = access_control_rule
        data = {"method": "modifySsid", "params": ssid_params}
        params = {"wlBasicSsid24SettingsM": "", "token": self._token}
        with async_timeout.timeout(self.timeout):
            res = await self.httpsession.post(
                self._base_url + CONTROLLER_PATH, params=params, data=json.dumps(data),
            )
        res_json = await res.json()
        if res_json["errorCode"] == -1001:
            _LOGGER.error(
                "Access Controller Rule `%s` doesn't exist", access_control_rule
            )
            return False
        if res_json["errorCode"] != 0:
            _LOGGER.error("Can not set access controller rule: %s", res_json["msg"])
            return False
        _LOGGER.debug(
            "Access Controller Rule `%s` affected to SSID %s", access_control_rule, ssid
        )

        return True

    async def set_accesscontrolerrule_service_handler(self, service):
        """TP-Link Omada accesscontrolerrule service handle method."""
        entity_id = service.data[ATTR_ENTITY_ID]
        rule = service.data.get(SERVICE_WIFIACRULE_ATTR_RULE)
        # Check if the entity is a ssid
        if self._hass.data["sensor"].get_entity(entity_id) is None:
            raise Exception(
                "The entity `{}` doesn't seems to be an SSID".format(entity_id)
            )
        if (
            "ssid"
            not in self._hass.data["sensor"]
            .get_entity(entity_id)
            .device_state_attributes
        ):
            raise Exception(
                "The entity `{}` doesn't seems to be an SSID".format(entity_id)
            )
        ssid = (
            self._hass.data["sensor"]
            .get_entity(entity_id)
            .device_state_attributes["ssid"]
        )

        return await self.set_ssid_access_control_rule(ssid, rule)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Omada Controller."""
        try:
            logged = await self.login()
            if not logged:
                self.available = False
                return
            # Fetch data
            await self.fetch_version()
            await self.fetch_global_stats()
            await self.fetch_ssid_stats()
            await self.fetch_ap_stats()
            await self.fetch_ssid_attributes()
            self.available = True
        except Exception as exp:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to fetch data from Omada Controller %s. Error: %s",
                self.host,
                exp,
            )
            self.available = False
        return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
