"""Support for Broadlink switches."""

from abc import ABC, abstractmethod
import logging
from typing import Any, override

from broadlink_async.exceptions import BroadlinkException
from broadlink_async.magic import DeviceKind, ImportedDevice
import probatio

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    BROADLINK_DATA,
    DOMAIN,
    DOMAINS_AND_TYPES,
    is_magic_entry,
    magic_device_identifier,
)
from .coordinator import BroadLinkMagicConfigEntry, FamilyCoordinator
from .device import BroadlinkDevice
from .entity import BroadlinkEntity, BroadLinkMagicEntity
from .helpers import data_packet, import_device, mac_address

_LOGGER = logging.getLogger(__name__)

CONF_SLOTS = "slots"

SWITCH_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.string,
        probatio.Optional(CONF_COMMAND_OFF): data_packet,
        probatio.Optional(CONF_COMMAND_ON): data_packet,
    }
)

PLATFORM_SCHEMA = probatio.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_SLOTS),
    cv.deprecated(CONF_TIMEOUT),
    cv.deprecated(CONF_TYPE),
    SWITCH_PLATFORM_SCHEMA.extend(
        {
            probatio.Required(CONF_MAC): mac_address,
            probatio.Optional(CONF_HOST): cv.string,
            probatio.Optional(CONF_SWITCHES, default=[]): probatio.All(
                probatio.EnsureList(),
                [SWITCH_SCHEMA],
            ),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the device and set up custom switches.

    This is for backward compatibility.
    Do not use this method.
    """
    mac_addr = config[CONF_MAC]
    host = config.get(CONF_HOST)

    if switches := config.get(CONF_SWITCHES):
        platform_data = hass.data[BROADLINK_DATA].platforms.get(Platform.SWITCH, {})
        if not (switch_platform_data := platform_data.get(mac_addr)):
            raise PlatformNotReady
        async_add_entities_config_entry: AddConfigEntryEntitiesCallback
        device: BroadlinkDevice
        async_add_entities_config_entry, device = switch_platform_data

        async_add_entities_config_entry(
            BroadlinkRMSwitch(device, config) for config in switches
        )

    else:
        _LOGGER.warning(
            "The switch platform is deprecated, except for custom IR/RF "
            "switches. Please refer to the Broadlink documentation to "
            "catch up"
        )

    if host:
        import_device(hass, host)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink switch."""
    if is_magic_entry(config_entry):
        await _async_setup_magic_entry(hass, config_entry, async_add_entities)
        return

    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]
    switches: list[BroadlinkSwitch] = []

    if device.api.type in DOMAINS_AND_TYPES[Platform.REMOTE]:
        platform_data = hass.data[BROADLINK_DATA].platforms.setdefault(
            Platform.SWITCH, {}
        )
        platform_data[device.api.mac] = async_add_entities, device
    elif device.api.type == "SP1":
        switches.append(BroadlinkSP1Switch(device))

    elif device.api.type in {"SP2", "SP2S", "SP3", "SP3S", "SP4", "SP4B"}:
        switches.append(BroadlinkSP2Switch(device))

    elif device.api.type == "BG1":
        switches.extend(BroadlinkBG1Slot(device, slot) for slot in range(1, 3))

    elif device.api.type in {"MP1", "MP1S"}:
        switches.extend(BroadlinkMP1Slot(device, slot) for slot in range(1, 5))

    async_add_entities(switches)


class BroadlinkSwitch(BroadlinkEntity, SwitchEntity, RestoreEntity, ABC):
    """Representation of a Broadlink switch."""

    _attr_assumed_state = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, device, command_on, command_off):
        """Initialize the switch."""
        super().__init__(device)
        self._command_on = command_on
        self._command_off = command_off

    @override
    async def async_added_to_hass(self) -> None:
        """Call when the switch is added to hass."""
        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON
        await super().async_added_to_hass()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if await self._async_send_packet(self._command_on):
            self._attr_is_on = True
            self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if await self._async_send_packet(self._command_off):
            self._attr_is_on = False
            self.async_write_ha_state()

    @abstractmethod
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""


class BroadlinkRMSwitch(BroadlinkSwitch):
    """Representation of a Broadlink RM switch."""

    def __init__(self, device, config):
        """Initialize the switch."""
        super().__init__(
            device, config.get(CONF_COMMAND_ON), config.get(CONF_COMMAND_OFF)
        )
        self._attr_name = config[CONF_NAME]

    @override
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device

        if packet is None:
            return True

        try:
            await device.async_request(device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP1Switch(BroadlinkSwitch):
    """Representation of a Broadlink SP1 switch."""

    _attr_has_entity_name = True

    def __init__(self, device):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._attr_unique_id = self._device.unique_id

    @override
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device

        try:
            await device.async_request(device.api.set_power, packet)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP2Switch(BroadlinkSP1Switch):
    """Representation of a Broadlink SP2 switch."""

    _attr_assumed_state = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device, *args, **kwargs):
        """Initialize the switch."""
        super().__init__(device, *args, **kwargs)
        self._attr_is_on = self._coordinator.data["pwr"]

    @override
    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data["pwr"]


class BroadlinkMP1Slot(BroadlinkSwitch):
    """Representation of a Broadlink MP1 slot."""

    _attr_assumed_state = False
    _attr_has_entity_name = True

    def __init__(self, device, slot):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._slot = slot
        self._attr_is_on = self._coordinator.data[f"s{slot}"]
        self._attr_name = f"S{slot}"
        self._attr_unique_id = f"{device.unique_id}-s{slot}"

    @override
    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data[f"s{self._slot}"]

    @override
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device

        try:
            await device.async_request(device.api.set_power, self._slot, packet)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkBG1Slot(BroadlinkSwitch):
    """Representation of a Broadlink BG1 slot."""

    _attr_assumed_state = False
    _attr_has_entity_name = True

    def __init__(self, device, slot):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._slot = slot
        self._attr_is_on = self._coordinator.data[f"pwr{slot}"]

        self._attr_name = f"S{slot}"
        self._attr_device_class = SwitchDeviceClass.OUTLET
        self._attr_unique_id = f"{device.unique_id}-s{slot}"

    @override
    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data[f"pwr{self._slot}"]

    @override
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device
        state = {f"pwr{self._slot}": packet}

        try:
            await device.async_request(device.api.set_state, **state)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


async def _async_setup_magic_entry(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up imported switch panels and plugs."""
    coordinator = entry.runtime_data
    async_add_entities(
        BroadLinkMagicSwitch(coordinator, device, channel)
        for device in coordinator.family.switch_devices
        for channel in range(device.channel_count)
    )


class BroadLinkMagicSwitch(BroadLinkMagicEntity, SwitchEntity):
    """One channel of an imported switch panel or plug."""

    _attr_is_on = False

    def __init__(
        self,
        coordinator: FamilyCoordinator,
        device: ImportedDevice,
        channel: int,
    ) -> None:
        """Initialize one switch channel."""
        super().__init__(coordinator)
        self._device = device
        self._channel = channel
        self._report_serial = 0
        self._area_name = coordinator.room_name(device.room_id)
        if device.channel_count == 1:
            self._attr_name = None
        elif channel < len(device.channel_names) and device.channel_names[channel]:
            self._attr_name = device.channel_names[channel]
        else:
            self._attr_translation_key = "channel"
            self._attr_translation_placeholders = {"channel": str(channel + 1)}
        self._attr_unique_id = (
            f"{coordinator.family.family_id}_{device.stable_id}_{channel}"
        )
        model = (
            "Magic Home Plug" if device.kind is DeviceKind.PLUG else "Magic Home Switch"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, magic_device_identifier(device.stable_id))},
            manufacturer="BroadLink",
            model=model,
            name=device.name,
            suggested_area=self._area_name,
            via_device_id=self._family_device_id(),
        )

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply a SwitchV1 channel report."""
        # Every gateway packet refreshes the coordinator; only a new report for
        # this device may override the optimistic state set by a command.
        serial = self.coordinator.report_serials.get(self._device.stable_id, 0)
        if serial != self._report_serial:
            self._report_serial = serial
            state = self.coordinator.device_states.get(self._device.stable_id, {})
            channels = state.get("channels")
            if isinstance(channels, dict) and self._channel in channels:
                self._attr_is_on = bool(channels[self._channel])
        super()._handle_coordinator_update()

    @override
    async def async_added_to_hass(self) -> None:
        """Assign the imported room without overriding user changes."""
        await super().async_added_to_hass()
        if self._area_name and self.registry_entry is not None:
            device_id = self.registry_entry.device_id
            registry = dr.async_get(self.hass)
            registry_device = registry.async_get(device_id) if device_id else None
            if registry_device is not None and registry_device.area_id is None:
                area = ar.async_get(self.hass).async_get_or_create(self._area_name)
                registry.async_update_device(registry_device.id, area_id=area.id)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this panel channel."""
        await self.coordinator.async_send_switch(
            self._device,
            self._channel,
            True,
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this panel channel."""
        await self.coordinator.async_send_switch(
            self._device,
            self._channel,
            False,
        )
        self._attr_is_on = False
        self.async_write_ha_state()
