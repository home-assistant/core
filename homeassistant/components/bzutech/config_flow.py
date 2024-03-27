"""Config flow for BZUTech integration."""
from __future__ import annotations

import logging
from typing import Any

from bzutech import BzuTech
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CHIPID, CONF_SENSORNAME, CONF_SENSORPORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    },
    True,
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> BzuTech:
    """Validate the user input allows us to connect."""
    hass.data[DOMAIN] = {}
    api = BzuTech(data[CONF_EMAIL], data[CONF_PASSWORD])

    if not await api.start():
        raise InvalidAuth

    return api


def get_devices(api: BzuTech, page: int) -> dict[str, Any]:
    """Get device names on a dict for the showmenu."""

    devices = {}
    i = 1
    first = page * 4
    last = first + 3
    counter = 0

    for key in list(api.dispositivos.keys()):
        if first <= counter <= last:
            returnkey = "option" + str(i)
            devices[returnkey] = key
            i = i + 1

        counter = counter + 1
    if len(list(api.dispositivos.keys())) > (page + 1) * 4:
        devices["option5"] = "Mais dispositivos"
    return devices


def get_sensors(
    api: BzuTech, devicepos: int, sensorport: int, page: int
) -> dict[str, Any]:
    """Get sensor names from a device on a dict for the showmenu."""

    sensors = {}
    first = page * 4
    last = first + 3
    counter = 0
    chipid = list(api.dispositivos.keys())[devicepos]
    numSensors = len(
        list(api.dispositivos[chipid].get_sensor_names_on(str(sensorport)))
    )

    i = 1

    for name in list(api.dispositivos[chipid].get_sensor_names_on(str(sensorport))):
        if first <= counter <= last:
            sensors["option" + str(i)] = name
            i = i + 1
        counter = counter + 1

    if numSensors > 4 * (page + 1):
        sensors["option5"] = "More sensors"

    return sensors


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BZUTech."""

    VERSION = 1
    api: BzuTech
    email = ""
    password = ""
    devicepage = 0
    sensorpage = 0
    flowstep = 0
    selecteddevice = 0
    selectedport = 0
    selectedsensor = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.api = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.email = user_input[CONF_EMAIL]
                self.password = user_input[CONF_PASSWORD]
                return await self.async_step_dispselect(user_input=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_LOGIN_SCHEMA,
            errors=errors,
            last_step=False,
        )

    async def async_step_dispselect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up second step."""
        self.flowstep = 1
        return self.async_show_menu(
            step_id="dispselect",
            menu_options=get_devices(self.api, self.devicepage),
        )

    async def async_step_option1(self, user_input: dict) -> FlowResult:
        """Unification of the device configuration."""
        if self.flowstep == 1:
            self.selecteddevice = 0
            return await self.async_step_portselect(user_input)
        if self.flowstep == 2:
            self.selectedport = 1
            return await self.async_step_sensorselect(user_input)
        if self.flowstep == 3:
            self.selectedsensor = self.sensorpage * 4 + 0
            return await self.async_step_configend()
        return await self.async_step_option1(user_input)

    async def async_step_option2(self, user_input: dict) -> FlowResult:
        """Unification of the device configuration menu options."""
        if self.flowstep == 1:
            self.selecteddevice = 1
            return await self.async_step_portselect(user_input)
        if self.flowstep == 2:
            self.selectedport = 2
            return await self.async_step_sensorselect(user_input)
        if self.flowstep == 3:
            self.selectedsensor = self.sensorpage * 4 + 1
            return await self.async_step_configend()
        return await self.async_step_option2(user_input)

    async def async_step_option3(self, user_input: dict) -> FlowResult:
        """Unification of the device configuration menu options."""
        if self.flowstep == 1:
            self.selecteddevice = 2
            return await self.async_step_portselect(user_input)
        if self.flowstep == 2:
            self.selectedport = 3
            return await self.async_step_sensorselect(user_input)
        if self.flowstep == 3:
            self.selectedsensor = self.sensorpage * 4 + 2
            return await self.async_step_configend()
        return await self.async_step_option3(user_input)

    async def async_step_option4(self, user_input: dict) -> FlowResult:
        """Unification of the device configuration menu options."""
        if self.flowstep == 1:
            self.selecteddevice = 3
            return await self.async_step_portselect(user_input)
        if self.flowstep == 2:
            self.selectedport = 4
            return await self.async_step_sensorselect(user_input)
        if self.flowstep == 3:
            self.selectedsensor = self.sensorpage * 4 + 3
            return await self.async_step_configend()
        return await self.async_step_option4(user_input)

    async def async_step_option5(self, user_input: dict) -> FlowResult:
        """Unification of the device configuration menu options."""
        if self.flowstep == 1:
            self.devicepage = self.devicepage + 1
            return await self.async_step_dispselect(user_input)
        if self.flowstep == 2:
            self.selectedport = 5
            return await self.async_step_sensorselect(user_input)
        if self.flowstep == 3:
            self.sensorpage = self.sensorpage + 1
            return await self.async_step_sensorselect(user_input)
        return await self.async_step_option5(user_input)

    async def async_step_portselect(self, user_input) -> FlowResult:
        """Set up second step."""
        self.flowstep = 2
        return self.async_show_menu(
            step_id="portselect",
            menu_options={
                "option1": "Port 1",
                "option2": "Port 2",
                "option3": "Port 3",
                "option4": "Port 4",
            },
        )

    async def async_step_sensorselect(self, user_input) -> FlowResult:
        """Sensor Selection."""
        self.flowstep = 3
        return self.async_show_menu(
            step_id="sensorselect",
            menu_options=get_sensors(
                self.api,
                self.selecteddevice,
                self.selectedport,
                self.sensorpage,
            ),
        )

    async def async_step_configend(self) -> FlowResult:
        """Set up user_input and create entry."""
        user_input = {}

        api = self.api
        chipid = api.get_device_names()[int(self.selecteddevice)]
        user_input[CONF_CHIPID] = str(chipid)
        user_input[CONF_SENSORPORT] = str(self.selectedport)
        user_input[CONF_EMAIL] = self.email
        user_input[CONF_PASSWORD] = self.password
        user_input[CONF_SENSORNAME] = api.dispositivos[chipid].get_sensor_names_on(
            str(user_input[CONF_SENSORPORT])
        )[self.selectedsensor]

        return self.async_create_entry(title=user_input[CONF_CHIPID], data=user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidSensor(HomeAssistantError):
    """Error to indicate there is invalid Sensor."""
