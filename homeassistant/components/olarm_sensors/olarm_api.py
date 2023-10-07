"""Module to interact with the Olarm API."""
import asyncio
from datetime import datetime, timedelta
import time
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ContentTypeError

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import ServiceCall

from .const import GITHUB_TOKEN, LOGGER, VERSION
from .exceptions import (
    APIClientConnectorError,
    APIContentTypeError,
    APINotFoundError,
    DictionaryKeyError,
    ListIndexError,
)


class OlarmApi:
    """Provides an interface to the Olarm API. It handles authentication, and provides methods for making requests to arm, disarm, sleep, or stay a security zone.

    params:
        ``device_id (str): UUID for the Olarm device.``n
        ``api_key (str): The key can be passed in an authorization header to authenticate to Olarm.
    """

    def __init__(
        self,
        device_id: str,
        api_key: str,
        device_name: str = "Olarm Sensors",
        entry: Any = None,
    ) -> None:
        """Initatiates a connection to the Olarm API.

        params:
         device_id (str): UUID for the Olarm device.
         api_key (str): The key can be passed in an authorization header to authenticate to Olarm.
        """
        self.device_id: str = device_id
        self.api_key: str = api_key
        self.data: list = []
        self.bypass_data: list = []
        self.panel_data: list = []
        self.devices: list = []
        self.device_name: str = device_name
        self.entry: Any = entry
        self.headers: dict = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Home Assistant",
        }

    async def get_device_json(self) -> dict:
        """Get and return the data from the Olarm API for a specific device.

        return: dict The info associated with a device
        """
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"https://apiv4.olarm.co/api/v4/devices/{self.device_id}",
                headers=self.headers,
            ) as response:
                try:
                    resp = await response.json()
                    resp["error"] = None
                    return resp

                except (APIContentTypeError, ContentTypeError):
                    text = await response.text()
                    if "forbidden" in text.lower():
                        LOGGER.error(
                            "Could not get JSON data due to incorrect API key. Please update the api key"
                        )
                        return {"error": text}

                    if response.status == 502:
                        LOGGER.error(
                            "The Olarm API is currently unavailable. The Gateway is working, but there seems to be no response from the API server"
                        )
                        return {"error": text}

                    if "too many requests" in text.lower():
                        LOGGER.error(
                            "Your refresh interval is set too frequent for the Olarm API to handle"
                        )
                        return {"error": text}

                    LOGGER.error(
                        "The api returned text instead of JSON. The text is:\n%s",
                        text,
                    )
                    return {"error": text}

        except APIClientConnectorError as ex:
            LOGGER.error("Olarm API Devices error\n%s", ex)
            return {"error": ex}

    async def get_changed_by_json(self, area) -> dict:
        """DOCSTRING: Get the actions for a specific device from Olarm and returns the user that last changed the state of an Area.

        return (str): The user that triggered thanlast state change of an area.
        """
        return_data: dict = {
            "userFullname": "No User",
            "actionCreated": 0,
            "actionCmd": None,
        }
        try:
            await asyncio.sleep(0.5 * self.entry.data[CONF_SCAN_INTERVAL])
            async with aiohttp.ClientSession() as session, session.get(
                f"https://apiv4.olarm.co/api/v4/devices/{self.device_id}/actions",
                headers=self.headers,
            ) as response:
                if response.status == 404:
                    LOGGER.warning(
                        "Olarm has no saved history for device (%s)",
                        self.device_name,
                    )
                    return return_data

                try:
                    changes: dict = {
                        "actionCmd": "zone-bypass",
                        "actionNum": 0,
                        "actionCreated": 0,
                    }
                    changes = await response.json()
                    for change in changes:
                        if (
                            change["actionCmd"]
                            not in [
                                "zone-bypass",
                                "pgm-open",
                                "pgm-close",
                                "pgm-pulse",
                                "ukey-activate",
                            ]
                            and int(change["actionNum"]) == int(area)
                            and int(return_data["actionCreated"])
                            < int(change["actionCreated"])
                        ):
                            return_data = change

                except (APIContentTypeError, ContentTypeError):
                    text = response.text
                    LOGGER.error(
                        "The Olarm API returned text instead of json. The text is:\n%s",
                        text,
                    )

                try:
                    last_changed = datetime.strptime(
                        time.ctime(int(return_data["actionCreated"])),
                        "%a %b  %d %X %Y",
                    )
                    return_data["actionCreated"] = last_changed.strftime(
                        "%a %d %b %Y %X"
                    )

                except TypeError:
                    last_changed = None

                return return_data

        except APIClientConnectorError as ex:
            LOGGER.error("Olarm API Changed By error\n%s", ex)
            return return_data

        except APINotFoundError as ex:
            LOGGER.error("Olarm API Changed By error\n%s", ex)
            return return_data

    async def check_credentials(self) -> dict:
        """DOCSTRING: Checks if the details the user provided is valid.

        return (dict): The device json from Olarm.
        """
        try:
            resp = await self.get_device_json()
            if resp["error"] is None:
                resp["auth_success"] = True
                return resp

            resp["auth_success"] = False
            return resp

        except (
            APIClientConnectorError,
            APIContentTypeError,
            IndexError,
            KeyError,
        ) as ex:
            return {"auth_success": False, "error": ex}

    async def get_sensor_states(self, devices_json) -> list:
        """DOCSTRING: Get the state for each zone for each area of your alarm panel.

        params: device_json (dict): The device json from get_devices_json.

        return: list:  A sensor for each zone in each area of the alarm panel. As well as the power states.
        """
        olarm_state = devices_json["deviceState"]
        olarm_zones = devices_json["deviceProfile"]

        self.data = []

        try:
            for zone in range(0, olarm_zones["zonesLimit"]):
                if str(olarm_state["zones"][zone]).lower() == "a":
                    state = "on"

                else:
                    state = "off"

                try:
                    last_changed_dt = datetime.strptime(
                        time.ctime(int(olarm_state["zonesStamp"][zone]) / 1000),
                        "%a %b  %d %X %Y",
                    )
                    last_changed = last_changed_dt.strftime("%a %d %b %Y %X")

                except TypeError:
                    last_changed = None

                if zone < len(olarm_zones["zonesLabels"]) and (
                    olarm_zones["zonesLabels"][zone]
                    or olarm_zones["zonesLabels"][zone] == ""
                ):
                    zone_name = olarm_zones["zonesLabels"][zone]
                    zone_type = olarm_zones["zonesTypes"][zone]

                else:
                    zone_name = f"Zone {zone + 1}"
                    zone_type = 0

                self.data.append(
                    {
                        "name": zone_name,
                        "state": state,
                        "last_changed": last_changed,
                        "type": zone_type,
                        "zone_number": zone,
                    }
                )

            zone = zone + 1
            for key, value in olarm_state["power"].items():
                sensortype = 1000
                if int(value) == 1:
                    state = "on"

                else:
                    state = "off"

                if key == "Batt":
                    key = "Battery"
                    sensortype = 1001

                self.data.append(
                    {
                        "name": f"Powered by {key}",
                        "state": state,
                        "last_changed": None,
                        "type": sensortype,
                        "zone_number": zone,
                    }
                )
                zone = zone + 1

            return self.data

        except (DictionaryKeyError, KeyError, IndexError, ListIndexError) as ex:
            LOGGER.error(
                "Olarm sensors error for  device (%s):\n%s", self.device_name, ex
            )
            return self.data

    async def get_sensor_bypass_states(self, devices_json) -> list:
        """DOCSTRING: Get the bypass state for each zone for each area of your alarm panel.

        params: device_json (dict): The device json from get_devices_json.

        return: List:  A sensor for each zone's bypass state in each area of the alarm panel.
        """
        olarm_state = devices_json["deviceState"]
        olarm_zones = devices_json["deviceProfile"]

        self.bypass_data = []
        try:
            for zone in range(0, olarm_zones["zonesLimit"]):
                if str(olarm_state["zones"][zone]).lower() == "b":
                    state = "on"

                else:
                    state = "off"

                last_changed_dt = datetime.strptime(
                    time.ctime(int(olarm_state["zonesStamp"][zone]) / 1000),
                    "%a %b  %d %X %Y",
                ) + timedelta(hours=2)

                last_changed = last_changed_dt.strftime("%a %d %b %Y %X")

                if zone < len(olarm_zones["zonesLabels"]) and (
                    olarm_zones["zonesLabels"][zone]
                    or olarm_zones["zonesLabels"][zone] == ""
                ):
                    zone_name = olarm_zones["zonesLabels"][zone]

                else:
                    zone_name = f"Zone {zone + 1}"

                self.bypass_data.append(
                    {
                        "name": zone_name,
                        "state": state,
                        "last_changed": last_changed,
                        "zone_number": zone,
                    }
                )

            return self.bypass_data

        except (DictionaryKeyError, KeyError, IndexError, ListIndexError) as ex:
            LOGGER.error(
                "Olarm Bypass sensors error for device (%s):\n%s", self.device_name, ex
            )
            return self.bypass_data

    async def get_panel_states(self, devices_json) -> list:
        """DOCSTRING: Get the state of each zone for the alarm panel from Olarm.

        params: device_json (dict): The device json from get_devices_json.

        return: (list): The state for each are of the alarm panel.
        """
        olarm_state = devices_json["deviceState"]
        zones = devices_json["deviceProfile"]
        olarm_zones = zones["areasLabels"]

        self.panel_data = []

        area_count = zones["areasLimit"]
        for area_num in range(area_count):
            try:
                if olarm_zones[area_num] == "":
                    LOGGER.warning(
                        "This device's area names have not been set up in Olarm, generating automatically"
                    )
                    olarm_zones[area_num] = f"Area {area_num + 1}"

                if len(olarm_state["areas"]) > area_num:
                    self.panel_data.append(
                        {
                            "name": f"{olarm_zones[area_num]}",
                            "state": olarm_state["areas"][area_num],
                            "area_number": area_num + 1,
                        }
                    )

            except (DictionaryKeyError, KeyError) as ex:
                LOGGER.error(
                    "Olarm API Panel error for device (%s):\n%s", self.device_name, ex
                )

        return self.panel_data

    async def get_pgm_zones(self, devices_json) -> list:
        """Get all the PGMs for the alarm panel.

        params: device_json (dict): The device json from get_devices_json.

        return: (list): The pgm's for the alarm panel.
        """
        try:
            pgm_state = devices_json["deviceState"]["pgm"]
            pgm_labels = devices_json["deviceProfile"]["pgmLabels"]
            pgm_limit = devices_json["deviceProfile"]["pgmLimit"]
            pgm_setup = devices_json["deviceProfile"]["pgmControl"]

        except (DictionaryKeyError, KeyError):
            # Error with PGM setup from Olarm app. Skipping PGM's
            LOGGER.error(
                "Error getting pgm setup data for Olarm device (%s)", self.device_id
            )
            return []

        pgms = []
        try:
            for i in range(0, pgm_limit):
                state = str(pgm_state[i]).lower() == "a"
                name = pgm_labels[i]
                if pgm_setup[i] == "":
                    continue

                try:
                    enabled = pgm_setup[i][0] == "1"

                except ListIndexError:
                    continue

                try:
                    pulse = pgm_setup[i][2] == "1"

                except ListIndexError:
                    continue

                number = i + 1

                if name == "":
                    LOGGER.debug(
                        "PGM name not set. Generating automatically. PGM %s", number
                    )
                    name = f"PGM {number}"

                pgms.append(
                    {
                        "name": name,
                        "enabled": enabled,
                        "pulse": pulse,
                        "state": state,
                        "pgm_number": number,
                    }
                )

            return pgms

        except (DictionaryKeyError, KeyError, IndexError, ListIndexError) as ex:
            LOGGER.error("Olarm PGM Error for device (%s):\n%s", self.device_name, ex)
            return pgms

    async def get_ukey_zones(self, devices_json) -> list:
        """Get all the Utility keys for the alarm panel.

        params: device_json (dict): The device json from get_devices_json.

        return: (list): The utility keys for the alarm panel.
        """
        ukey_labels = devices_json["deviceProfile"]["ukeysLabels"]
        ukey_limit = devices_json["deviceProfile"]["ukeysLimit"]
        ukey_state = devices_json["deviceProfile"]["ukeysControl"]
        ukeys = []
        try:
            for i in range(0, ukey_limit):
                try:
                    state = int(ukey_state[i]) == 1
                    name = ukey_labels[i]
                    number = i + 1

                    if name == "":
                        LOGGER.debug(
                            "Ukey name not set. Generating automatically. Ukey %s",
                            number,
                        )
                        name = f"Ukey {number}"

                    ukeys.append({"name": name, "state": state, "ukey_number": number})

                except (DictionaryKeyError, KeyError) as ex:
                    LOGGER.error(
                        "Olarm Ukey Error for device (%s):\n%s", self.device_name, ex
                    )
                    return []

            return ukeys

        except (DictionaryKeyError, KeyError, IndexError, ListIndexError) as ex:
            LOGGER.error("Olarm Ukey error for device (%s):\n%s", self.device_name, ex)
            return []

    async def get_alarm_trigger(self, devices_json) -> list:
        """Return the data for the zones that triggered an alarm for the area."""
        return devices_json["deviceState"]["areasDetail"]

    async def send_action(self, post_data) -> bool:
        """DOCSTRING: Sends an action to the Olarm API to perform an action on the device.

        params: post_data_data (dict): The area to perform the action to. As well as the action.
        """
        try:
            async with aiohttp.ClientSession() as session, session.post(
                url=f"https://apiv4.olarm.co/api/v4/devices/{self.device_id}/actions",
                data=post_data,
                headers=self.headers,
            ) as response:
                try:
                    resp = await response.json()
                    if str(resp["actionStatus"]).lower() != "ok":
                        LOGGER.error(
                            "Could not send action: %s to Olarm Device (%s) due to error: %s",
                            resp["actionCmd"],
                            resp["deviceName"],
                            resp["actionMsg"],
                        )
                    return str(resp["actionStatus"]).lower() == "ok"

                except (APIContentTypeError, ContentTypeError):
                    text = await response.text()
                    LOGGER.error(
                        "Error Bypassing zone: %s on device (%s).\n\n%s",
                        post_data["actionNum"],
                        self.device_name,
                        text,
                    )
                    return False

        except APIClientConnectorError as ex:
            LOGGER.error(
                "Olarm API update zone error on device (%s):\nCould not set action:  %s due to error:\n%s",
                self.device_name,
                post_data,
                ex,
            )
            return False

    async def update_pgm(self, pgm_data) -> bool:
        """DOCSTRING: Sends an action to the Olarm API to perform a pgm action on the device.

        params: post_data (dict): The pgm to perform the action to. As well as the action.
        """
        try:
            return await self.send_action(pgm_data)

        except APIClientConnectorError as ex:
            LOGGER.error(
                "Olarm API update pgm error on device (%s):\nCould not set action:  %s due to error:\n%s",
                self.device_name,
                pgm_data,
                ex,
            )
            return False

    async def update_ukey(self, ukey_data) -> bool:
        """DOCSTRING: Sends an action to the Olarm API to perform a pgm action on the device.

        params: ukey_data (dict): The ukey to perform the action to. As well as the action.
        """
        try:
            return await self.send_action(ukey_data)

        except APIClientConnectorError as ex:
            LOGGER.error(
                "Olarm API update ukey error on device (%s):\nCould not set action:  %s due to error:\n%s",
                self.device_name,
                ukey_data,
                ex,
            )
            return False

    async def arm_area(self, area=None) -> bool:
        """Send the request to send_action to arm an area.

        params: area (int): The number of the area to apply the zone to.
        """
        post_data = {"actionCmd": "area-arm", "actionNum": area}
        return await self.send_action(post_data)

    async def sleep_area(self, area=None) -> bool:
        """Send the request to send_action to arm an area.

        params: area (int): The number of the area to apply the zone to.
        """
        post_data = {"actionCmd": "area-sleep", "actionNum": area}
        return await self.send_action(post_data)

    async def stay_area(self, area=None) -> bool:
        """Send the request to send_action to arm an area.

        params: area (int): The number of the area to apply the zone to.
        """
        post_data = {"actionCmd": "area-stay", "actionNum": area}
        return await self.send_action(post_data)

    async def disarm_area(self, area=None) -> bool:
        """Send the request to send_action to arm an area.

        params: area (int): The number of the area to apply the zone to.
        """
        post_data = {"actionCmd": "area-disarm", "actionNum": area}
        return await self.send_action(post_data)

    async def bypass_zone(self, zone: Any) -> bool:
        """Send the request to send_action to bypass a zone.

        params: zone (dict): The number of the zone to apply the zone to.
        """
        post_data = {
            "actionCmd": "zone-bypass",
            "actionNum": zone.data["zone_num"],
        }
        return await self.send_action(post_data)

    async def bypass_zone_with_service(self, zone: ServiceCall) -> None:
        """Send the request to send_action to bypass a zone.

        params: zone (dict): The number of the zone to apply the zone to.
        """
        post_data = {
            "actionCmd": "zone-bypass",
            "actionNum": zone.data["zone_num"],
        }
        await self.send_action(post_data)

    async def get_all_devices(self) -> list:
        """Get and return the devices from the Olarm API.

        return: list The devices associated with the api key.
        """
        try:
            async with aiohttp.ClientSession() as session, session.get(
                "https://apiv4.olarm.co/api/v4/devices",
                headers=self.headers,
            ) as response:
                try:
                    olarm_resp = await response.json()
                    self.devices = olarm_resp["data"]
                    return self.devices

                except (APIContentTypeError, ContentTypeError):
                    text = await response.text()
                    if "Forbidden" in text:
                        LOGGER.error(
                            "Could not get JSON data due to incorrect API key. Please update the api key"
                        )
                        return []

                    if "Too Many Requests" in text:
                        LOGGER.error(
                            "Your api key has been temporarily blocked due to too many request. Increase your scan interval"
                        )
                        return []

                    LOGGER.error(
                        "The api returned text instead of JSON. The text is:\n%s",
                        text,
                    )
                    return []

        except APIClientConnectorError as ex:
            LOGGER.error("Olarm API Devices error\n%s", ex)
            return []


class OlarmSetupApi:
    """Provides an interface to the Olarm API. It handles authentication, and provides methods for making requests to arm, disarm, sleep, or stay a security zone.

    params:
         device_id (str): UUID for the Olarm device.
         api_key (str): The key can be passed in an authorization header to authenticate to Olarm.
    """

    def __init__(self, api_key: str) -> None:
        """Initatiate a connection to the Olarm API.

        params:
         api_key (str): The key can be passed in an authorization header to authenticate to Olarm.
        """
        self.data: list = []
        self.headers: dict = {"Authorization": f"Bearer {api_key}"}

    async def get_olarm_devices(self) -> list:
        """Get and returns the devices from the Olarm API.

        return: list The devices associated with the api key.
        """
        try:
            async with aiohttp.ClientSession() as session, session.get(
                "https://apiv4.olarm.co/api/v4/devices",
                headers=self.headers,
            ) as response:
                try:
                    olarm_resp = await response.json()
                    self.data = olarm_resp["data"]
                    return self.data

                except (ContentTypeError, APIContentTypeError):
                    text = await response.text()
                    if "Forbidden" in text:
                        LOGGER.error(
                            "Could not get JSON data due to incorrect API key. Please update the api key"
                        )
                        return []

                    if "Too Many Requests" in text:
                        LOGGER.error(
                            "Your api key has been temporarily blocked due to too many request. Increase your scan interval"
                        )
                        return []

                    LOGGER.error(
                        "The setup api returned text instead of JSON. The text is:\n%s",
                        text,
                    )
                    return []

        except APIClientConnectorError as ex:
            LOGGER.error("Olarm SetupAPI Devices error\n%s", ex)
            return []


class OlarmUpdateAPI:
    """Retrieve update version from github."""

    def __init__(self) -> None:
        """Retrieve update version from github."""
        # Construct the URL for the latest release
        self.url: str = "https://api.github.com/repos/rainepretorius/olarm-ha-integration/releases/latest"

        # Set up headers with your personal access token for authentication
        self.headers: dict = {
            "Authorization": f"token {GITHUB_TOKEN}",
        }
        self.release_data: dict = {
            "name": f"Version {VERSION}",
            "body": "",
            "html_url": "",
        }

    async def get_version(self):
        """Get the newes version from GitHub."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.url,
                    headers=self.headers,
                ) as response:
                    self.release_data = await response.json()

                    return self.release_data

            except APIClientConnectorError:
                return self.release_data
