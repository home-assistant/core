"""Representation of Idasen Desk buttons."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeskData, IdasenDeskCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Idasen Desk connection buttons from config entry."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            IdasenDeskConnectButton(data.address, data.device_info, data.coordinator),
            IdasenDeskDisconnectButton(
                data.address, data.device_info, data.coordinator
            ),
        ]
    )


class IdasenDeskConnectButton(ButtonEntity):
    """Representation of a connect button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self,
        address: str,
        device_info: DeviceInfo,
        coordinator: IdasenDeskCoordinator,
    ) -> None:
        """Initialize the connect button."""
        self._attr_name = f"{device_info[ATTR_NAME]} Connect"
        self._attr_unique_id = f"connect-{address}"
        self._attr_device_info = device_info
        self._coordinator = coordinator

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_connect()


class IdasenDeskDisconnectButton(ButtonEntity):
    """Representation of a disconnect button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bluetooth-off"

    def __init__(
        self,
        address: str,
        device_info: DeviceInfo,
        coordinator: IdasenDeskCoordinator,
    ) -> None:
        """Initialize the disconnect button."""
        self._address = address
        self._attr_name = f"{device_info[ATTR_NAME]} Disconnect"
        self._attr_unique_id = f"disconnect-{address}"
        self._attr_device_info = device_info
        self._coordinator = coordinator

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_disconnect()
