"""Module that stores the Coordinator class to update the data from the api."""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
import time

from olarm_api_rainepretorius import OlarmApi, OlarmUpdateAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, TempEntry
from .exceptions import APIContentTypeError, ClientConnectorError


class OlarmCoordinator(DataUpdateCoordinator):
    """Handle the coordination of the Olarm integration. Fetch data for the coordinator from the Olarm API and provide it to the binary sensors and alarm control panel."""

    data: list = []
    changed_by: dict = {1: None, 2: None}
    last_changed: dict = {1: time.ctime(), 2: time.ctime()}
    last_action: dict = {1: None, 2: None}
    device_online: bool = True
    device_json: dict = {}
    release_data: dict = {}
    device_firmware: str
    area_triggers: list[str] = ["", "", "", "", "", "", "", ""]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_name: str,
        device_make: str,
    ) -> None:
        """Handle the coordination of the Olarm integration. Fetch data for the coordinator from the Olarm API and provide it to the binary sensors and alarm control panel."""
        self.entry: ConfigEntry | TempEntry = entry

        super().__init__(
            hass,
            LOGGER,
            name=f"Olarm Coordinator ({device_name})",
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

        # Instansiating a local instance of the Olarm Github Update API.
        self.update_api = OlarmUpdateAPI()

        # Instansiating a local instance of the Olarm API
        self.api = OlarmApi(
            device_id=device_id,
            api_key=entry.data[CONF_API_KEY],
            device_name=device_name,
            entry=self.entry,
        )
        self.last_update = datetime.now() - timedelta(minutes=30)

        # Setting the necessary class variables and lists.
        self.sensor_data: list = []
        self.devices_json: dict | None = None
        self.panel_data: dict = {}
        self.panel_state: list = []
        self.bypass_data: dict = {}
        self.bypass_state: list = []
        self.ukey_data: list = []
        self.pgm_data: list = []
        self.area_changes: list[dict] = [{}, {}, {}, {}, {}, {}, {}, {}]
        self.area_triggers: list = ["", "", "", "", "", "", "", ""]

        # Setting the device info.
        self.olarm_device_name: str = device_name
        self.olarm_device_make: str = str(device_make).capitalize()
        self.olarm_device_id: str = device_id
        self.last_changed: dict = {1: time.ctime(), 2: time.ctime()}

    async def update_data(self):
        """Call to update the data for the integration from Olarm's API."""
        # Getting the update data.
        try:
            self.release_data = await self.update_api.get_version()
            self.hass.data[DOMAIN]["release_data"] = self.release_data

        except (KeyError, IndexError):
            pass

        try:
            # Getting all the devices for your Olarm Account.
            devices = await self.api.get_all_devices()
            for device in devices:
                coordinator = OlarmCoordinator(
                    self.hass,
                    entry=self.entry,
                    device_id=device["deviceId"],
                    device_name=device["deviceName"],
                    device_make=device["deviceAlarmType"],
                )

                self.hass.data.setdefault(DOMAIN, {})

                self.hass.data[DOMAIN][device["deviceId"]] = coordinator
                self.hass.data[DOMAIN]["devices"] = devices

        except ClientConnectorError as ex:
            LOGGER.error(
                "Could not check for new Olarm devices connected to your account.\nError:%s",
                ex,
            )

        except APIContentTypeError as ex:
            LOGGER.error(
                "Could not retrieve devices connected to your account. The Invalid response is:\n%s",
                ex,
            )

        if datetime.now() - self.last_update > timedelta(
            seconds=(0.9 * self.entry.data[CONF_SCAN_INTERVAL])
        ):
            self.devices_json = await self.api.get_device_json()
            with contextlib.suppress(KeyError):
                self.device_firmware = self.devices_json["deviceFirmware"]

        if bool(self.devices_json) and self.devices_json["error"] is None:
            # Checking if the device is online.
            self.device_online = self.devices_json["deviceStatus"].lower() == "online"

            # Getting the sesor states for each zone.
            self.data = await self.api.get_sensor_states(self.devices_json)
            self.sensor_data = self.data

            # Getting the Area Information
            self.panel_data = await self.api.get_panel_states(self.devices_json)
            self.panel_state = self.panel_data

            # Getting the Bypass Information
            self.bypass_data = await self.api.get_sensor_bypass_states(
                self.devices_json
            )
            self.bypass_state = self.bypass_data

            # Getting PGM Data
            self.pgm_data = await self.api.get_pgm_zones(self.devices_json)

            # Getting Ukey Data
            self.ukey_data = await self.api.get_ukey_zones(self.devices_json)

            # Getting alarm trigger
            self.area_triggers = await self.api.get_alarm_trigger(self.devices_json)

            # Getting the change json for each area.
            for area in self.panel_data:
                self.area_changes[
                    area["area_number"] - 1
                ] = await self.api.get_changed_by_json(area["area_number"])

            # Setting the last update success to true to show device as available.
            self.last_update_success = True
            self.last_update = datetime.now()

        else:
            LOGGER.warning(
                "Olarm Sensors:\nself.devices_json is empty, skipping update"
            )
            self.last_update_success = False

        return self.last_update_success

    async def _async_update_data(self):
        """Update data via Olarm's API."""
        return await self.update_data()

    async def async_get_data(self):
        """Update data via Olarm's API."""
        return await self.update_data()

    async def async_update_sensor_data(self):
        """Call to update the data for the zone sensors for the integration from Olarm's API."""
        self.devices_json = await self.api.get_device_json()
        if bool(self.devices_json) and self.devices_json["error"] is None:
            # Checking if the device is online.
            self.device_online = self.devices_json["deviceStatus"].lower() == "online"

            # Getting the sesor states for each zone.
            self.data = await self.api.get_sensor_states(self.devices_json)
            self.sensor_data = self.data
            self.last_update = datetime.now()

        else:
            LOGGER.warning(
                "Olarm Sensors:\nself.devices_json is empty, skipping update"
            )

        return self.last_update_success

    async def async_update_bypass_data(self):
        """Call to update the data for the bypass switches for the integration from Olarm's API."""
        self.devices_json = await self.api.get_device_json()
        if bool(self.devices_json) and self.devices_json["error"] is None:
            # Getting the Bypass Information
            self.bypass_data = await self.api.get_sensor_bypass_states(
                self.devices_json
            )
            self.bypass_state = self.bypass_data
            self.last_update = datetime.now()

        else:
            LOGGER.warning(
                "Olarm Sensors:\nself.devices_json is empty, skipping update of bypass sensors"
            )

        return self.last_update_success

    async def async_update_panel_data(self):
        """Call to update the panel data for the integration from Olarm's API."""
        self.devices_json = await self.api.get_device_json()
        if bool(self.devices_json) and self.devices_json["error"] is None:
            # Getting the Area Information
            self.panel_data = await self.api.get_panel_states(self.devices_json)
            self.panel_state = self.panel_data
            self.last_update = datetime.now()

        else:
            LOGGER.warning(
                "Olarm Sensors:\nself.devices_json is empty, skipping update of alarm panels"
            )
            self.last_update_success = False

        return self.last_update_success

    async def async_update_pgm_ukey_data(self):
        """Call to update the pgm data for the integration from Olarm's API."""
        self.devices_json = await self.api.get_device_json()
        if bool(self.devices_json) and self.devices_json["error"] is None:
            # Getting PGM Data
            self.pgm_data = await self.api.get_pgm_zones(self.devices_json)
            # Getting Ukey Data
            self.ukey_data = await self.api.get_ukey_zones(self.devices_json)
            self.last_update = datetime.now()

        else:
            LOGGER.warning(
                "Olarm Sensors:\nself.devices_json is empty, skipping update of buttons"
            )

        return self.last_update_success
