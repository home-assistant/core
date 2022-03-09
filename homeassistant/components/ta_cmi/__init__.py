"""The Technische Alternative C.M.I. integration."""
from __future__ import annotations

import asyncio
from typing import Any

from async_timeout import timeout
from ta_cmi import ApiError, Channel, Device, InvalidCredentialsError, RateLimitError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    CONF_CHANNELS,
    CONF_CHANNELS_DEVICE_CLASS,
    CONF_CHANNELS_ID,
    CONF_CHANNELS_NAME,
    CONF_CHANNELS_TYPE,
    CONF_DEVICE_FETCH_MODE,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    DEVICE_DELAY,
    DOMAIN,
    SCAN_INTERVAL,
)

PLATFORMS: list[str] = [Platform.SENSOR, Platform.BINARY_SENSOR]

API_VERSION: str = "api_version"
DEVICE_TYPE: str = "device_type"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    host: str = entry.data[CONF_HOST]
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    devices: dict[str, Any] = entry.data[CONF_DEVICES]

    coordinator = CMIDataUpdateCoordinator(hass, host, username, password, devices)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class CMIDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching CMI data."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        devices: Any,
    ) -> None:
        """Initialize."""
        self.devices_raw: dict[str, Any] = {}

        self.devices: list[Device] = []
        self.host = host

        for dev_raw in devices:
            device_id: str = dev_raw[CONF_DEVICE_ID]
            device: Device = Device(
                device_id, host, username, password, async_get_clientsession(hass)
            )
            self.devices.append(device)
            self.devices_raw[device_id] = dev_raw

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        try:
            return_data: dict[str, Any] = {}
            for device in self.devices:
                async with timeout(10):
                    await device.update()

                return_data[device.id] = _parse_data(
                    device, self.devices_raw[device.id]
                )

                return_data[device.id][CONF_HOST] = self.host

                if len(self.devices) != 1:
                    await asyncio.sleep(DEVICE_DELAY)

            return return_data
        except (InvalidCredentialsError, RateLimitError, ApiError) as err:
            raise UpdateFailed(err) from err


def _parse_data(device: Device, device_raw: dict[str, Any]) -> dict[str, Any]:
    """Parse data."""
    data: dict[str, Any] = {
        "I": {},
        "O": {},
        "IB": {},
        "OB": {},
        API_VERSION: device.apiVersion,
        DEVICE_TYPE: device.getDeviceType(),
    }

    fetchmode: str = device_raw[CONF_DEVICE_FETCH_MODE]
    channel_options: list = []

    for channel in device_raw[CONF_CHANNELS]:
        channel_options.append(
            {
                CONF_CHANNELS_ID: channel[CONF_CHANNELS_ID],
                CONF_CHANNELS_TYPE: channel[CONF_CHANNELS_TYPE],
                CONF_CHANNELS_NAME: channel[CONF_CHANNELS_NAME],
                CONF_CHANNELS_DEVICE_CLASS: channel[CONF_CHANNELS_DEVICE_CLASS],
            }
        )

    for ch_id in device.inputs:
        name = None
        device_class = None

        for i in channel_options:
            if ch_id == i[CONF_CHANNELS_ID] and i[CONF_CHANNELS_TYPE] == "input":
                name = i[CONF_CHANNELS_NAME]
                if len(i[CONF_CHANNELS_DEVICE_CLASS]) != 0:
                    device_class = i[CONF_CHANNELS_DEVICE_CLASS]
                break

        if (name is not None and fetchmode == "defined") or fetchmode == "all":
            channel_input: Channel = device.inputs[ch_id]

            value, unit = format_input(channel_input)

            platform = "I"

            if (
                channel_input.getUnit() == "On/Off"
                or channel_input.getUnit() == "No/Yes"
            ):
                platform = "IB"

            data[platform][ch_id] = {
                "channel": channel_input,
                "value": value,
                "mode": "Input",
                "unit": unit,
                "name": name,
                "device_class": device_class,
            }

    for ch_id in device.outputs:
        name = None
        device_class = None

        for i in channel_options:
            if ch_id == i[CONF_CHANNELS_ID] and i[CONF_CHANNELS_TYPE] == "output":
                name = i[CONF_CHANNELS_NAME]
                if len(i[CONF_CHANNELS_DEVICE_CLASS]) != 0:
                    device_class = i[CONF_CHANNELS_DEVICE_CLASS]
                break

        if (name is not None and fetchmode == "defined") or fetchmode == "all":
            channel_output: Channel = device.outputs[ch_id]

            value, unit = format_input(channel_output)

            platform = "O"

            if (
                channel_output.getUnit() == "On/Off"
                or channel_output.getUnit() == "No/Yes"
            ):
                platform = "OB"

            data[platform][ch_id] = {
                "channel": channel_output,
                "value": value,
                "mode": "Output",
                "unit": unit,
                "name": name,
                "device_class": device_class,
            }

    return data


def format_input(channel: Channel) -> tuple[str, str]:
    """Format the unit and value."""
    unit: str = channel.getUnit()
    value: str = channel.value

    if unit == "On/Off":
        unit = ""
        if bool(value):
            value = STATE_ON
        else:
            value = STATE_OFF

    if unit == "No/Yes":
        unit = ""
        if bool(value):
            value = "yes"
        else:
            value = "no"

    return (value, unit)
