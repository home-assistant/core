"""Base class for Lutron devices."""

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.const import ATTR_IDENTIFIERS, ATTR_VIA_DEVICE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .aiolip import Device, KeypadComponent, LutronController, Output, Sysvar
from .const import DOMAIN


class LutronBaseEntity(Entity):
    """Base class for Lutron entities.

    The entity represents a device in the Lutron system.
    The entity is associated with a device with device_name.
    The entity has no name, the name is from the device
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name: str | None = None

    def __init__(
        self,
        lutron_device: Device,
        controller: LutronController,
    ) -> None:
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Lutron",
            name=self.device_name,
            suggested_area=self.area_name,
            via_device=(DOMAIN, controller.guid),
        )

    @property
    def area_name(self) -> str:
        """Return the area name."""
        if (area := self._lutron_device.area) is not None:
            return (
                area.name
                if not self._controller.use_full_path
                else f"{area.location} {area.name}"
            )
        return ""

    @property
    def device_name(self) -> str:
        """Return the device name including the computed area_name."""
        if (lutron_device := self._lutron_device) is not None:
            return (
                f"{self.area_name} {lutron_device.name}"
                if self._controller.use_area_for_device_name
                and self.area_name is not None
                else lutron_device.name
            )
        return "No Name"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._controller.subscribe(
            self._lutron_device.integration_id, None, self._update_callback
        )

    async def async_update(self) -> None:
        """Update the entity's state. It's called after async_added."""
        await self._request_state()

    async def _request_state(self) -> None:
        """Request the state."""

    def _update_callback(self, value) -> None:
        """Handle Lutron messages for this integration_id."""

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the entity."""
        await self._controller.stop()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._lutron_device.uuid is None:
            return f"{self._controller.guid}_{self._lutron_device.legacy_uuid}"
        return f"{self._controller.guid}_{self._lutron_device.uuid}"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.integration_id}

    async def _execute_device_command(
        self, command_method: Callable, *args, **kwargs
    ) -> None:
        """Execute a command from the device.

        Takes a device method (like self._lutron_device.set_level)
        and its arguments, creates the command, and executes it through the controller.
        """
        command = command_method(*args, **kwargs)
        await self._controller.execute_command(command)


class LutronOutput(LutronBaseEntity):
    """Representation of a Lutron output device entity."""

    _lutron_device: Output


class LutronVariable(LutronBaseEntity):
    """Representation of a Lutron variable entity.

    It's connected to the controller device.
    """

    _lutron_device: Sysvar

    def __init__(
        self,
        lutron_device: Device,
        controller: LutronController,
    ) -> None:
        """Initialize the entity with the proper name. Assign it to the controller device."""
        super().__init__(lutron_device, controller)
        self._attr_name = lutron_device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.guid)},
        )


class LutronKeypadComponent(LutronBaseEntity):
    """Representation of a Lutron Keypad Component, such as Leds, Buttons, Events.

    The HA device is the keypad with device_name
    The entity has a name, so the full name is device_name + name
    """

    _lutron_device: KeypadComponent

    def __init__(
        self,
        lutron_device: KeypadComponent,
        controller: LutronController,
    ) -> None:
        """Initialize the device.

        RadioRA main repeater is also a keypad.
        HomeworksQS is not.
        """
        super().__init__(lutron_device, controller)
        self._component_number = lutron_device.component_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._lutron_device.integration_id))},
            manufacturer="Lutron",
            name=self.device_name,
            suggested_area=self.area_name,
        )
        if lutron_device.keypad.device_type == "MAIN_REPEATER":
            self._attr_device_info[ATTR_IDENTIFIERS].add((DOMAIN, controller.guid))
        else:
            self._attr_device_info[ATTR_VIA_DEVICE] = (DOMAIN, controller.guid)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if self._controller.use_radiora_mode:
            return self._lutron_device.name
        return self._lutron_device.component_name

    @property
    def keypad_name(self) -> str:
        """Return the keypad name.

        If we are using radiora mode, we use the keypad name, not the device_group_name.
        Usually the keypad device in the DB doesn't have a meaningful name (e.g., CDS 001 for international keypads).
        """
        if self._controller.use_radiora_mode:
            return self._lutron_device.keypad.name
        return f"keypad {self._lutron_device.keypad.integration_id}"

    @property
    def device_name(self) -> str:
        """Return the device name for the keypad component, which is the keypad_name name including the computed area_name."""
        return (
            f"{self.area_name} {self.keypad_name}"
            if self._controller.use_area_for_device_name and self.area_name is not None
            else self.keypad_name
        )

    async def async_added_to_hass(self) -> None:  # pylint: disable=hass-missing-super-call
        """Register the keypad component using also the component_number to get the updates for the components."""
        self._controller.subscribe(
            self._lutron_device.integration_id,
            self._component_number,
            self._update_callback,
        )


class LutronControllerBaseEntity(Entity):
    """Representation of the controller entity."""

    _attr_has_entity_name = True

    def __init__(self, controller: LutronController) -> None:
        """Initialize the controller entity."""
        self._controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.guid)},
            name="Lutron Controller",
            manufacturer="Lutron",
            model=controller.lip.controller_type.name.lower(),
            sw_version="NA",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._controller.guid
