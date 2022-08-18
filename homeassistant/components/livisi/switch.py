"""Code to handle a Livisi switches."""
from aiolivisi import AioLivisi

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, SWITCH_PLATFORM
from .device import Device
from .shc import SHC


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""

    shc = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    async def async_add_switch(device) -> None:
        """Add switch."""
        livisi_switch: LivisiSwitch = await create_device(device, hass, shc)
        LOGGER.debug("Include device type: %s", device.get("type"))
        shc.included_devices.append(livisi_switch)
        async_add_entities([livisi_switch])

    shc.register_new_device_callback(SWITCH_PLATFORM, async_add_switch)
    await async_setup_switch_entry(hass, shc, async_add_entities)


async def async_setup_switch_entry(
    hass: HomeAssistant,
    shc: SHC,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""

    livisi_switches = []
    for device in shc.switch_devices:
        if device in shc.included_devices:
            continue
        livisi_switch: LivisiSwitch = await create_device(device, hass, shc)
        livisi_switches.append(livisi_switch)
        LOGGER.debug("Include device type: %s", device.get("type"))
        shc.included_devices.append(livisi_switch)

    async_add_entities(livisi_switches)


async def create_device(device, hass, shc):
    """Create Switch Entity."""
    config_details = device.get("config")
    capabilities: list = device.get("capabilities")
    is_on = await shc.async_get_pss_state(capability=capabilities[0])
    room_id: str = device.get("location").removeprefix("/location/")
    room_name: str = shc.rooms[room_id]
    livisi_switch = LivisiSwitch(
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


class LivisiSwitch(SwitchEntity, Device):
    """Represents the Livisi Switch."""

    def __init__(
        self,
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
        self._shc = shc
        self._attr_unique_id = unique_id
        self._manufacturer = manufacturer
        self._product = product
        self._serial_number = serial_number
        self._device_type = device_type
        self._name = name
        self._state = None
        self._capability_id = capability_id
        self._is_on = is_on
        self._room = room
        self._version = version
        self.aio_livisi = AioLivisi.get_instance()
        if is_on is None:
            self._is_available = False
        else:
            self._is_available = True

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer."""
        return self._manufacturer

    @manufacturer.setter
    def manufacturer(self, new_value: str):
        self._manufacturer = new_value

    @property
    def product(self) -> str:
        """Return the product type."""
        return self._product

    @product.setter
    def product(self, new_value: str):
        self._product = new_value

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        return self._serial_number

    @serial_number.setter
    def serial_number(self, new_value: str):
        self._serial_number = new_value

    @property
    def device_type(self) -> str:
        """Return the device type."""
        return self._device_type

    @device_type.setter
    def device_type(self, new_value: str):
        self._device_type = new_value

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @name.setter
    def name(self, new_value: str):
        self._name = new_value

    @property
    def version(self):
        """Return the version number."""
        return self._version

    @version.setter
    def version(self, new_value: str):
        self._version = new_value

    @property
    def capability_id(self):
        """Return the capability id of the device."""
        return self._capability_id

    @capability_id.setter
    def capability_id(self, new_value: str):
        self._capability_id = new_value

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._attr_unique_id))},
            manufacturer=self.manufacturer,
            model=self.device_type,
            name=self.name,
            suggested_area=self._room,
            sw_version=self._version,
            via_device=(DOMAIN, str(self._attr_unique_id)),
        )

    @property
    def is_on(self):
        """Return the device state."""
        return self._is_on

    @property
    def available(self):
        """Return if switch is available."""
        return self._is_available

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        if self.is_on is True:
            return
        response = await self.aio_livisi.async_pss_set_state(
            self.capability_id, is_on=True
        )
        if response is None:
            self._is_available = False

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        if self.is_on is False:
            return
        response = await self.aio_livisi.async_pss_set_state(
            self.capability_id, is_on=False
        )
        if response is None:
            self._is_available = False

    def update_states(self, states) -> None:
        """Update the states of the switch device."""
        on_state = states.get("onState")
        if on_state is None:
            return
        if on_state is True:
            self._is_on = True
        else:
            self._is_on = False
        self.async_write_ha_state()

    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the switch device."""
        if is_reachable is False:
            self._is_available = False
        else:
            self._is_available = True
