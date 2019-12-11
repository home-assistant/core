"""Config flow to configure the AIS WIFI Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_NAME
from homeassistant.components.ais_dom import ais_global
import time
import voluptuous as vol
import logging
import asyncio

G_WIFI_NETWORKS = []
_LOGGER = logging.getLogger(__name__)

DATA_AIS_WIFI_SERVICE_IMPL = "ais_wifi_service_flow_implementation"


@callback
def register_flow_implementation(hass, client_name, client_secret):
    """Register a ais wifi service implementation.
    """
    hass.data.setdefault(DATA_AIS_WIFI_SERVICE_IMPL, {})

    hass.data[DATA_AIS_WIFI_SERVICE_IMPL] = {
        CONF_NAME: client_name,
        CONF_PASSWORD: client_secret,
    }


@callback
def configured_connections(hass):
    """Return a set of configured connections instances."""
    return set(
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    )


def scan_for_wifi(hass, loop) -> []:
    global G_WIFI_NETWORKS
    _LOGGER.info("scan_for_wifi, no of try: " + str(loop))
    # send scan request to frame
    if loop == 0:
        # reset the current status
        hass.services.call("script", "ais_scan_android_wifi_network")
    # wait
    time.sleep(3)
    # and check the answer
    wifi_networks = hass.states.get("input_select.ais_android_wifi_network")
    G_WIFI_NETWORKS = wifi_networks.attributes["options"]
    return G_WIFI_NETWORKS


def connect_to_wifi(network, password) -> str:
    import requests

    # send add request to frame
    url = ais_global.G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1")
    _LOGGER.info("connect_to_wifi: " + network + " pass: " + password)
    try:
        ssid = network.split(";")[0]
        wifi_type = network.split(";")[-3]
        bssid = network.split(";")[-1].replace("MAC:", "").strip()
        requests.post(
            url + "/command",
            json={
                "WifiConnectToSid": ssid,
                "WifiNetworkPass": password,
                "WifiNetworkType": wifi_type,
                "bssid": bssid,
            },
            timeout=5,
        )
    except Exception as e:
        _LOGGER.error("connect_to_wifi: " + str(e))


def check_wifi_connection(hass, loop) -> []:
    global G_WIFI_NETWORKS
    _LOGGER.info("check_wifi_connection, no of try: " + str(loop))
    # wait
    time.sleep(3)
    # and check the answer
    net_info = hass.states.get("sensor.ais_wifi_service_current_network_info")
    ssid = net_info.attributes.get("ssid", "")
    return ssid


@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set(
        "ais_wifi_service" for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register("ais_wifi_service")
class AisWiFilowHandler(config_entries.ConfigFlow):
    """AIS WiFi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered AIS WiFi integration."""
        # Abort if other flows in progress or an entry already exists
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start - confirmation from user"""
        errors = {}
        if user_input is not None:
            return await self.async_step_one(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_one(self, user_input=None):
        """Step one"""
        errors = {}
        if user_input is not None:
            if "connect_to_hidden_ssid" in user_input:
                if user_input["connect_to_hidden_ssid"]:
                    return await self.async_step_connect_to_hidden_wifi(user_input=None)
                else:
                    return await self.async_step_search_wifi(user_input=None)

        data_schema = vol.Schema(
            {vol.Optional("connect_to_hidden_ssid", default=False): bool}
        )
        return self.async_show_form(
            step_id="one", errors=errors, data_schema=data_schema
        )

    async def async_step_search_wifi(self, user_input=None):
        """Step - scan the wifi"""
        errors = {}
        # reset wifi's list
        self.hass.async_run_job(
            self.hass.services.async_call(
                "input_select",
                "set_options",
                {
                    "entity_id": "input_select.ais_android_wifi_network",
                    "options": [ais_global.G_EMPTY_OPTION],
                },
            )
        )
        for x in range(0, 9):
            result = await self.hass.async_add_executor_job(scan_for_wifi, self.hass, x)
            _LOGGER.info("Szukam sieci WiFi: " + str(result))
            if len(result) > 1:
                return await self.async_step_connect_to_wifi(user_input=None)
            else:
                errors = {"base": "search_failed"}
        #

        data_schema = vol.Schema(
            {vol.Optional("connect_to_hidden_ssid", default=False): bool}
        )
        return self.async_show_form(
            step_id="one", errors=errors if errors else {}, data_schema=data_schema
        )

    async def async_step_connect_to_wifi(self, user_input=None):
        """Step four - connect to wifi"""
        wifi_network = self.hass.states.get("input_select.ais_android_wifi_network")
        networks = wifi_network.attributes["options"]
        # remove empty option
        if networks[0] == ais_global.G_EMPTY_OPTION:
            networks.pop(0)

        errors = {}

        if len(networks) == 0:
            errors["general"] = "wifi_error"
            return self.async_abort(reason="search_failed")

        if user_input is None:
            data_schema = vol.Schema(
                {
                    vol.Required("networks", default=networks[0]): vol.In(
                        list(networks)
                    ),
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional("rescan_wifi", default=False): bool,
                }
            )

        else:
            # check if user want to rescan
            if "rescan_wifi" in user_input:
                if user_input["rescan_wifi"]:
                    return await self.async_step_one(user_input=None)

            password = ""
            if CONF_PASSWORD in user_input:
                password = user_input[CONF_PASSWORD]
            data_schema = vol.Schema(
                {
                    vol.Required("networks", default=user_input["networks"]): vol.In(
                        list(networks)
                    ),
                    vol.Optional(CONF_PASSWORD, default=password): str,
                    vol.Optional("rescan_wifi", default=False): bool,
                }
            )

            # try to connect
            if errors == {}:
                # send a request to frame to add the new device
                network = user_input["networks"]
                text = "Łączę z siecią " + network.split(";")[0]
                self.hass.async_run_job(
                    self.hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": text}
                    )
                )
                await self.hass.async_add_executor_job(
                    connect_to_wifi, network, password
                )
                # request was correctly send, now check and wait for the answer
                for x in range(0, 7):
                    result = await self.hass.async_add_executor_job(
                        check_wifi_connection, self.hass, x
                    )
                    _LOGGER.info("Spawdzam połączenie z siecią WiFi: " + str(result))
                    if result == network.split(";")[0]:
                        # remove if exists
                        exists_entries = [
                            entry.entry_id for entry in self._async_current_entries()
                        ]
                        if exists_entries:
                            await asyncio.wait(
                                [
                                    self.hass.config_entries.async_remove(entry_id)
                                    for entry_id in exists_entries
                                ]
                            )
                        # return await self.async_step_connect_to_wifi(user_input=None)
                        return self.async_create_entry(title="WiFi", data=user_input)
                    else:
                        errors = {"base": "conn_failed"}

        # check wifi list len - without empty option
        l_net = str(len(networks) - 1)

        return self.async_show_form(
            step_id="connect_to_wifi",
            errors=errors if errors else {},
            data_schema=data_schema,
            description_placeholders={"wifi_number_info": l_net},
        )

    async def async_step_connect_to_hidden_wifi(self, user_input=None):
        """Step four - connect to hidden wifi"""
        errors = {}
        description_placeholders = {}
        networks_types = ["WEP", "WPA", "WPA2", "Open"]

        if user_input is None:
            data_schema = vol.Schema(
                {
                    vol.Required("networks_types", default="WPA"): vol.In(
                        list(networks_types)
                    ),
                    vol.Required("hidden_ssid"): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional("rescan_wifi", default=False): bool,
                }
            )
        else:
            if user_input["rescan_wifi"]:
                return await self.async_step_one(user_input=None)
            else:
                network_type = user_input["networks_types"]
                password = ""
                if CONF_PASSWORD in user_input:
                    password = user_input[CONF_PASSWORD]

                data_schema = vol.Schema(
                    {
                        vol.Required(
                            "networks_types", default=user_input["networks_types"]
                        ): vol.In(list(networks_types)),
                        vol.Required(
                            "hidden_ssid", default=user_input["hidden_ssid"]
                        ): str,
                        vol.Optional(CONF_PASSWORD, default=password): str,
                        vol.Optional("rescan_wifi", default=False): bool,
                    }
                )

                hidden_ssid = user_input["hidden_ssid"]

                # custom validation
                # if the netowrk type is selected not Open then password need to be provided
                if network_type != "Open" and password == "":
                    errors = {"base": "no_password_to_protected_wifi"}
                    description_placeholders = {"selected_net_type": network_type}

                # try to connect
                if errors == {}:
                    # send a request to frame to add the new device
                    text = "Łączę z siecią " + hidden_ssid
                    self.hass.async_run_job(
                        self.hass.services.async_call(
                            "ais_ai_service", "say_it", {"text": text}
                        )
                    )

                    wni = (
                        hidden_ssid
                        + "; "
                        + "moc mnieznana (-10); "
                        + network_type
                        + "; MAC: 00:00:00:00:00:00"
                    )
                    await self.hass.async_add_executor_job(
                        connect_to_wifi, wni, password
                    )
                    # request was correctly send, now check and wait for the answer
                    for x in range(0, 9):
                        result = await self.hass.async_add_executor_job(
                            check_wifi_connection, self.hass, x
                        )
                        _LOGGER.info(
                            "Spawdzam połączenie z siecią WiFi: " + str(result)
                        )
                        if result == hidden_ssid:
                            # remove if exists
                            exists_entries = [
                                entry.entry_id
                                for entry in self._async_current_entries()
                            ]
                            if exists_entries:
                                await asyncio.wait(
                                    [
                                        self.hass.config_entries.async_remove(entry_id)
                                        for entry_id in exists_entries
                                    ]
                                )
                            # return await self.async_step_connect_to_wifi(user_input=None)
                            return self.async_create_entry(
                                title="WiFi", data=user_input
                            )
                        else:
                            errors = {"base": "conn_failed"}

        return self.async_show_form(
            step_id="connect_to_hidden_wifi",
            errors=errors if errors else {},
            data_schema=data_schema,
            description_placeholders=description_placeholders,
        )
