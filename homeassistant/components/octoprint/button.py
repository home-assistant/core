"""Support for Octoprint buttons."""

from pyoctoprintapi import OctoprintClient, OctoprintPrinterInfo

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Octoprint control buttons."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    client: OctoprintClient = hass.data[DOMAIN][config_entry.entry_id]["client"]
    device_id = config_entry.unique_id
    assert device_id is not None

    async_add_entities(
        [
            OctoprintResumeJobButton(coordinator, device_id, client),
            OctoprintPauseJobButton(coordinator, device_id, client),
            OctoprintStopJobButton(coordinator, device_id, client),
            OctoprintShutdownSystemButton(coordinator, device_id, client),
            OctoprintRebootSystemButton(coordinator, device_id, client),
            OctoprintRestartOctoprintButton(coordinator, device_id, client),
        ]
    )


class OctoprintPrinterButton(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], ButtonEntity
):
    """Represent an OctoPrint binary sensor."""

    client: OctoprintClient

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        button_type: str,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator)
        self.client = client
        self._device_id = device_id
        self._attr_name = f"OctoPrint {button_type}"
        self._attr_unique_id = f"{button_type}-{device_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]


class OctoprintSystemButton(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], ButtonEntity
):
    """Represent an OctoPrint binary sensor."""

    client: OctoprintClient

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        button_type: str,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator)
        self.client = client
        self._device_id = device_id
        self._attr_name = f"OctoPrint {button_type}"
        self._attr_unique_id = f"{button_type}-{device_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class OctoprintPauseJobButton(OctoprintPrinterButton):
    """Pause the active job."""

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Pause Job", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]

        if printer.state.flags.printing:
            await self.client.pause_job()
        elif not printer.state.flags.paused and not printer.state.flags.pausing:
            raise InvalidPrinterState("Printer is not printing")


class OctoprintResumeJobButton(OctoprintPrinterButton):
    """Resume the active job."""

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Resume Job", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]

        if printer.state.flags.paused:
            await self.client.resume_job()
        elif not printer.state.flags.printing and not printer.state.flags.resuming:
            raise InvalidPrinterState("Printer is not currently paused")


class OctoprintStopJobButton(OctoprintPrinterButton):
    """Resume the active job."""

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Stop Job", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]

        if printer.state.flags.printing or printer.state.flags.paused:
            await self.client.cancel_job()


class OctoprintShutdownSystemButton(OctoprintSystemButton):
    """Shutdown the system."""

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Shutdown System", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.shutdown()


class OctoprintRebootSystemButton(OctoprintSystemButton):
    """Reboot the system."""

    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Reboot System", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.reboot_system()


class OctoprintRestartOctoprintButton(OctoprintSystemButton):
    """Restart Octoprint."""

    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        client: OctoprintClient,
    ) -> None:
        """Initialize a new OctoPrint button."""
        super().__init__(coordinator, "Restart Octoprint", device_id, client)

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.restart()


class InvalidPrinterState(HomeAssistantError):
    """Service attempted in invalid state."""
