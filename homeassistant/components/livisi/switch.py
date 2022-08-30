"""Code to handle a Livisi switches."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LIVISI_DISCOVERY_NEW,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
)
from .shc import SHC


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""
    shc = hass.data[DOMAIN][config_entry.entry_id]

    async def async_discover_device(device) -> None:
        """Add switch."""
        livisi_switch: SwitchEntity = await create_entity(
            hass, config_entry, device, shc
        )
        LOGGER.debug("Include device type: %s", device.get("type"))
        async_add_entities([livisi_switch])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, LIVISI_DISCOVERY_NEW, async_discover_device)
    )


async def create_entity(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dict[str, Any], shc: SHC
) -> SwitchEntity:
    """Create Switch Entity."""
    config_details: dict[str, Any] = device["config"]
    capabilities: list = device["capabilities"]
    is_on = await shc.async_get_pss_state(capability=capabilities[0])
    room_id: str = device["location"].removeprefix("/location/")
    room_name: str = shc.rooms[room_id]
    livisi_switch = LivisiSwitch(
        hass,
        config_entry,
        shc,
        unique_id=device.get("id"),
        manufacturer=device.get("manufacturer"),
        product=device.get("product"),
        serial_number=device.get("serialNumber"),
        device_type=device.get("type"),
        name=config_details.get("name"),
        capability_id=capabilities[0],
        is_on=is_on,
        room=room_name,
    )
    return livisi_switch


class LivisiSwitch(SwitchEntity):
    """Represents the Livisi Switch."""

    def __init__(
        self,
        hass,
        config_entry,
        shc,
        unique_id,
        manufacturer,
        product,
        serial_number,
        device_type,
        name,
        capability_id,
        is_on,
        room,
        version=None,
    ):
        """Initialize the Livisi Switch."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry
        self._shc: SHC = shc
        self._attr_unique_id = unique_id
        self._manufacturer = manufacturer
        self._product = product
        self._serial_number = serial_number
        self._attr_model = device_type
        self._attr_name = name
        self._state = None
        self._capability_id = capability_id
        self._attr_is_on = is_on
        self._room = room
        self._version = version
        self.aio_livisi = shc.aiolivisi
        if is_on is None:
            self._attr_is_available = False
        else:
            self._attr_is_available = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._attr_unique_id))},
            manufacturer=self._manufacturer,
            model=self._attr_model,
            name=self._attr_name,
            suggested_area=self._room,
            sw_version=self._version,
            via_device=(DOMAIN, str(self._attr_unique_id)),
        )

        config_entry.async_on_unload(
            async_dispatcher_connect(hass, LIVISI_STATE_CHANGE, self.update_states)
        )
        config_entry.async_on_unload(
            async_dispatcher_connect(
                hass, LIVISI_REACHABILITY_CHANGE, self.update_reachability
            )
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return the device state."""
        return self._attr_is_on

    @property
    def available(self):
        """Return if switch is available."""
        return self._attr_is_available

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        if self.is_on is True:
            return
        response = await self.aio_livisi.async_pss_set_state(
            self._capability_id, is_on=True
        )
        if response is None:
            self._attr_is_available = False

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        if self.is_on is False:
            return
        response = await self.aio_livisi.async_pss_set_state(
            self._capability_id, is_on=False
        )
        if response is None:
            self._attr_is_available = False

    @callback
    def update_states(self, device_id_state: dict) -> None:
        """Update the states of the switch device."""
        if device_id_state.get("id") != self._capability_id:
            return
        on_state = device_id_state.get("state")
        if on_state is None:
            return
        if on_state is True:
            self._attr_is_on = True
        else:
            self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def update_reachability(self, device_id_reachability: dict) -> None:
        """Update the reachability of the switch device."""
        if device_id_reachability.get("id") != self.unique_id:
            return
        if device_id_reachability.get("is_reachable") is False:
            self._attr_is_available = False
        else:
            self._attr_is_available = True
