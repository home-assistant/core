"""Insteon base entity."""
from enum import Enum
import functools
import logging

from pyinsteon import devices
from pyinsteon.address import Address
from pyinsteon.device_types.device_base import Device

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DOMAIN,
    SIGNAL_ADD_DEFAULT_LINKS,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
    SIGNAL_REMOVE_ENTITY,
    SIGNAL_SAVE_DEVICES,
    STATE_NAME_LABEL_MAP,
)
from .utils import print_aldb_to_log

_LOGGER = logging.getLogger(__name__)
WRITE_DELAY = 10
WRITE_DEBOUNCER = "write_debouncer"


def get_write_debouncer(hass: HomeAssistant, device: Device) -> Debouncer:
    """Return a debouncer for the device async_write_config method."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN][WRITE_DEBOUNCER] = hass.data[DOMAIN].get(WRITE_DEBOUNCER, {})
    if debouncer := hass.data[DOMAIN][WRITE_DEBOUNCER].get(device.address.id):
        return debouncer

    debouncer = Debouncer(
        hass=hass,
        logger=_LOGGER,
        cooldown=WRITE_DELAY,
        immediate=False,
        function=device.async_write_config,
    )
    hass.data[DOMAIN][WRITE_DEBOUNCER][device.address.id] = debouncer
    return debouncer


class InsteonEntityBase(Entity):
    """INSTEON abstract base entity."""

    _attr_should_poll = False

    def __init__(
        self, device: Device, group: int | None = None, name: str | None = None
    ) -> None:
        """Initialize the INSTEON base class."""
        if group is not None:
            self._entity = device.groups[group]
        else:
            self._entity = device.configuration[name]
        self._insteon_device = device
        self._group = group
        self._name = name

    def __hash__(self):
        """Return the hash of the Insteon Entity."""
        return hash(self._insteon_device)

    @property
    def address(self):
        """Return the address of the node."""
        return str(self._insteon_device.address)

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        # Set a base description
        if (description := self._insteon_device.description) is None:
            description = "Unknown Device"
        # Get an extension label if there is one
        if extension := self._get_label():
            extension = f" {extension}"
        return f"{description} {self._insteon_device.address}{extension}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._insteon_device.address))},
            manufacturer="SmartLabs, Inc",
            model=(
                f"{self._insteon_device.model} ({self._insteon_device.cat!r},"
                f" 0x{self._insteon_device.subcat:02x})"
            ),
            name=f"{self._insteon_device.description} {self._insteon_device.address}",
            sw_version=(
                f"{self._insteon_device.firmware:02x} Engine Version:"
                f" {self._insteon_device.engine_version}"
            ),
            via_device=(DOMAIN, str(devices.modem.address)),
        )

    async def async_added_to_hass(self):
        """Register INSTEON update events."""
        self._entity.subscribe(self.async_entity_update)
        load_signal = f"{self.entity_id}_{SIGNAL_LOAD_ALDB}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, load_signal, self._async_read_aldb)
        )
        print_signal = f"{self.entity_id}_{SIGNAL_PRINT_ALDB}"
        async_dispatcher_connect(self.hass, print_signal, self._print_aldb)
        default_links_signal = f"{self.entity_id}_{SIGNAL_ADD_DEFAULT_LINKS}"
        async_dispatcher_connect(
            self.hass, default_links_signal, self._async_add_default_links
        )
        remove_signal = f"{self._insteon_device.address.id}_{SIGNAL_REMOVE_ENTITY}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                remove_signal,
                functools.partial(self.async_remove, force_remove=True),
            )
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe to INSTEON update events."""
        self._entity.unsubscribe(self.async_entity_update)

    @callback
    def async_entity_update(self, *args, **kwargs) -> None:
        """Receive notification from transport that new data exists."""
        raise NotImplementedError

    async def _async_read_aldb(self, reload):
        """Call device load process and print to log."""
        await self._insteon_device.aldb.async_load(refresh=reload)
        self._print_aldb()
        async_dispatcher_send(self.hass, SIGNAL_SAVE_DEVICES)

    def _print_aldb(self):
        """Print the device ALDB to the log file."""
        print_aldb_to_log(self._insteon_device.aldb)

    def get_device_property(self, name: str):
        """Get a single Insteon device property value (raw)."""
        if (prop := self._insteon_device.properties.get(name)) is not None:
            return prop.value
        return None

    def _get_label(self):
        """Get the device label for grouped devices."""
        label = ""

        if self._group and len(self._insteon_device.groups) == 1:
            return label

        if self._entity.name in STATE_NAME_LABEL_MAP:
            label = STATE_NAME_LABEL_MAP[self._entity.name]
        else:
            label = self._entity.name.replace("_", " ").title()
        return label

    async def _async_add_default_links(self):
        """Add default links between the device and the modem."""
        await self._insteon_device.async_add_default_links()


class InsteonEntity(InsteonEntityBase):
    """Base class for Insteon state entities."""

    @property
    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._entity.group

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._entity.group == 0x01:
            uid = self._insteon_device.id
        else:
            uid = f"{self._insteon_device.id}_{self._entity.group}"
        return uid

    @property
    def extra_state_attributes(self) -> dict[str, Address | int]:
        """Provide attributes for display on device card."""
        return {
            "insteon_address": self.address,
            "insteon_group": self.group,
        }

    # pylint: disable=arguments-differ
    @callback
    def async_entity_update(
        self, name: str, address: Address, value: int | bool, group: int
    ):
        """Receive notification from transport that new data exists."""
        self.async_write_ha_state()


class InsteonConfigEntity(InsteonEntityBase):
    """Base class for Insteon configuration entities."""

    _attr_entity_category = EntityCategory.CONFIG
    _debounce_writer: Debouncer

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._insteon_device.id}_config_{self._entity.name}"

    # pylint: disable=arguments-differ
    @callback
    def async_entity_update(self, name: str, value: int | bool | Enum | list):
        """Receive notification from transport that new data exists."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle the added to HASS event."""
        await super().async_added_to_hass()
        self._debounce_writer = get_write_debouncer(self.hass, self._insteon_device)
