"""Config flow for Heatmiser NetMonitor integration."""
from __future__ import annotations

import logging
import time

import requests
from requests.auth import HTTPBasicAuth

from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HeatmiserStat:
    """Utility class for Heatmiser NetMonitor stats."""

    def __init__(
        self,
        id,
        name,
        current_temperature,
        target_temperature,
        hvac_mode,
        current_state,
    ):
        """Initialize the stat."""
        self.id = id
        self.name = name
        self.current_temperature = current_temperature
        self.target_temperature = target_temperature
        self.hvac_mode = hvac_mode
        self.current_state = current_state


class HeatmiserHub:
    """Heatmiser Hub controller."""

    def __init__(
        self, host: str, username: str, password: str, hass: HomeAssistant
    ) -> None:
        """Initialize the hub controller."""
        self.host = host
        self.username = username
        self.password = password
        self.hass = hass

    def async_auth(self) -> bool:
        """Validate the username, password and host."""

        response = requests.get(
            "http://" + self.host + "/quickview.htm",
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if response.status_code == 200:
            return True
        else:
            return False

    async def authenticate(self) -> bool:
        """Validate the username, password and host asynchronously."""
        response = self.hass.async_add_executor_job(self.async_auth)

        return response

    def get_devices(self):
        """Get the list of devices."""

        device_list = []
        response = requests.get(
            "http://" + self.host + "/quickview.htm",
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if response.status_code == 200:
            content = response.content.decode("utf-8")
            statnames = content.split('statname" value="')[1].split('"')[0].split("#")
            quickvals = content.split('quickview" value="')[1].split('"')[0]
            statmap = content.split('statmap" value="')[1].split('"')[0]
            i = 0
            for statname in statnames:
                if (statmap[i : i + 1]) == "1":
                    current_temperature_str = quickvals[i * 6 : i * 6 + 2]
                    current_temperature = None
                    if current_temperature_str != "NC":
                        current_temperature = int(current_temperature_str)
                    target_temperature_str = quickvals[i * 6 + 2 : i * 6 + 4]
                    target_temperature = None
                    if target_temperature_str != "NC":
                        target_temperature = int(target_temperature_str)
                    state = quickvals[i * 6 + 4 : i * 6 + 5]
                    current_state = CURRENT_HVAC_OFF
                    if state == "1":
                        current_state = CURRENT_HVAC_HEAT

                    print(
                        statname
                        + "("
                        + current_temperature_str
                        + " "
                        + target_temperature_str
                        + ")"
                    )

                    device_list.append(
                        HeatmiserStat(
                            i,
                            statname,
                            current_temperature,
                            target_temperature,
                            HVAC_MODE_HEAT,
                            current_state,
                        )
                    )
                    i = i + 1
        return device_list

    async def get_devices_async(self):
        """Get the list of devices asynchronously."""
        return await self.hass.async_add_executor_job(self.get_devices)

    def set_temperature(self, name, target_temperature):
        """Set a device target temperature."""

        for _ in range(10):
            response = requests.post(
                "http://" + self.host + "/right.htm",
                data={"rdbkck": "1", "curSelStat": name},
                auth=HTTPBasicAuth(self.username, self.password),
            )
            if response.status_code == 200:
                response = requests.post(
                    "http://" + self.host + "/right.htm",
                    data={"selSetTemp": str(int(target_temperature))},
                    auth=HTTPBasicAuth(self.username, self.password),
                )
            time.sleep(1)

    async def set_temperature_async(self, name, target_temperature):
        """Set a device target temperature asynchronously."""
        return await self.hass.async_add_executor_job(
            self.set_temperature, name, target_temperature
        )

    def set_mode(self, name, hvac_mode):
        """Set a device target mode."""
        mode = "0"
        if hvac_mode == HVAC_MODE_OFF:
            mode = "1"
        for _ in range(10):
            response = requests.post(
                "http://" + self.host + "/right.htm",
                data={"rdbkck": "1", "curSelStat": name},
                auth=HTTPBasicAuth(self.username, self.password),
            )
            if response.status_code == 200:
                response = requests.post(
                    "http://" + self.host + "/right.htm",
                    data={"selFrost": mode},
                    auth=HTTPBasicAuth(self.username, self.password),
                )
            time.sleep(1)

    async def set_mode_async(self, name, hvac_mode):
        """Set a device target mode asynchronously."""
        return await self.hass.async_add_executor_job(self.set_mode, name, hvac_mode)

    def get_device_status(self, name) -> HeatmiserStat:
        """Get the device status."""

        response = requests.post(
            "http://" + self.host + "/right.htm",
            data={"rdbkck": "0", "curSelStat": name},
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if response.status_code == 200:
            content = response.content.decode("utf-8")
            statvals = content.split('statInfo" value="')[1].split('"')[0]
            current_temperature_str = statvals[0:2]
            current_temperature = None
            if current_temperature_str != "NC":
                current_temperature = int(current_temperature_str)
            target_temperature_str = statvals[2:4]
            target_temperature = None
            if target_temperature_str != "NC":
                target_temperature = int(target_temperature_str)
            current_state = statvals[8:9]
            current_mode = statvals[10:11]
            mode = HVAC_MODE_HEAT
            if current_mode == "1":
                mode = HVAC_MODE_OFF
            state = CURRENT_HVAC_OFF
            if current_state == "1":
                state = CURRENT_HVAC_HEAT
            stat = HeatmiserStat(
                0, name, current_temperature, target_temperature, mode, state
            )
            return stat
        else:
            return None

    async def get_device_status_async(self, name) -> HeatmiserStat:
        """Get the device status asynchronously."""
        return await self.hass.async_add_executor_job(self.get_device_status, name)
