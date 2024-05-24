"""Support for Duwi Smart Switch."""

from __future__ import annotations

import logging
from typing import Any

from duwi_smarthome_sdk.api.control import ControlClient
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.model.req.device_control import ControlDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import APP_VERSION, CLIENT_MODEL, CLIENT_VERSION, DOMAIN, MANUFACTURER
from .util import debounce, persist_messages_with_status_code

# Initialize logger
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Retrieve the instance ID from the configuration entry
    instance_id = config_entry.entry_id

    # Check if the DUWI_DOMAIN is loaded and has house_no available
    if DOMAIN in hass.data and "house_no" in hass.data[DOMAIN][instance_id]:
        # Access the SWITCH devices from the domain storage
        devices = hass.data[DOMAIN][instance_id]["devices"].get("SWITCH")

        # If there are devices present, proceed with entity addition
        if devices is not None:
            # Helper function to create DuwiSwitch entities
            def create_switch_entities(device_list):
                return [
                    DuwiSwitch(
                        hass=hass,
                        instance_id=instance_id,
                        unique_id=device.device_no,
                        device_name=device.device_name,
                        device_no=device.device_no,
                        house_no=device.house_no,
                        room_name=device.room_name,
                        floor_name=device.floor_name,
                        terminal_sequence=device.terminal_sequence,
                        route_num=device.route_num,
                        state=device.value.get("switch", None) == "on",
                        available=device.value.get("online", False),
                        is_group=bool(getattr(device, "device_group_no", None)),
                    )
                    for device in device_list
                ]

            # Loop through each switch type ['On', 'Off', other types if exist] to create entities
            for switch_type in devices.keys():
                switch_entities = create_switch_entities(devices[switch_type])
                async_add_entities(switch_entities)


class DuwiSwitch(SwitchEntity):
    """Initialize the DuwiSwitch entity."""

    _attr_name = None
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        device_no: str,
        unique_id: str,
        terminal_sequence: str,
        route_num: str,
        house_no: str,
        room_name: str,
        floor_name: str,
        state: bool,
        available: bool,
        device_name: str,
        is_group: bool = False,
        assumed: bool = False,
    ) -> None:
        """Initialize the Duwi Switch Entity."""
        self._device_no = device_no
        self._unique_id = unique_id
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self._house_no = house_no
        self._room_name = room_name
        self._floor_name = floor_name

        self._instance_id = instance_id
        self._is_on = state
        self._available = available
        self._is_group = is_group
        self._assumed = assumed
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=(
                self._room_name + " "
                if self._room_name is not None and self._room_name != ""
                else ""
            )
            + device_name,
            suggested_area=(
                self._floor_name + " " + self._room_name
                if self._room_name is not None and self._room_name != ""
                else "default room"
            ),
        )

        self.hass = hass

        # Initialize Control Client
        self.cc = ControlClient(
            app_key=self.hass.data[DOMAIN][instance_id]["app_key"],
            app_secret=self.hass.data[DOMAIN][instance_id]["app_secret"],
            access_token=self.hass.data[DOMAIN][instance_id]["access_token"],
            app_version=APP_VERSION,
            client_version=CLIENT_VERSION,
            client_model=CLIENT_MODEL,
            is_group=is_group,
        )

        # Initialize Control Device
        self.cd = ControlDevice(device_no=self._device_no, house_no=self._house_no)

        # Store unique entity ID globally
        self.entity_id = f"switch.duwi_{device_no}"
        self.hass.data[DOMAIN][instance_id][unique_id] = {
            "device_no": self._device_no,
            "update_device_state": self.update_device_state,
        }
        if self.hass.data[DOMAIN][instance_id].get(self._terminal_sequence) is None:
            self.hass.data[DOMAIN][instance_id][self._terminal_sequence] = {}
        self.hass.data[DOMAIN][instance_id].setdefault("slave", {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return self._unique_id

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return the device's availability."""
        return self._available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._is_on = True
        # Update HA State to 'on'
        self.cd.add_param_info("switch", "on")
        if not kwargs.get("is_scheduled", False):
            status = await self.cc.control(self.cd)
            if status == Code.SUCCESS.value:
                self.async_write_ha_state()
            else:
                await persist_messages_with_status_code(hass=self.hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()
        self.cd.remove_param_info()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._is_on = False
        # Update HA State to 'off'
        self.cd.add_param_info("switch", "off")
        # Control the switch only if the action is not locked.
        if not kwargs.get("is_scheduled", False):
            status = await self.cc.control(self.cd)
            if status == Code.SUCCESS.value:
                self.async_write_ha_state()
            else:
                await persist_messages_with_status_code(hass=self.hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()
        self.cd.remove_param_info()

    async def update_device_state(
        self, action: str = None, is_scheduled: bool = True, **kwargs: Any
    ):
        """Update the device state."""
        kwargs["is_scheduled"] = is_scheduled
        if action == "turn_on":
            await self.async_turn_on(**kwargs)
        elif action == "turn_off":
            await self.async_turn_off(**kwargs)
        elif action == "toggle":
            await self.async_toggle(**kwargs)
        else:
            if "available" in kwargs:
                self._available = kwargs["available"]
                self.async_write_ha_state()

    @debounce(0.5)
    async def async_write_ha_state_with_debounce(self):
        self.async_write_ha_state()
