"""Bosch Smart Home Controller base entity."""

from boschshcpy.device import SHCDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import DeviceInfo, async_get as get_dev_reg
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER, OPT_EXCLUDED_DEVICES, OPT_EXCLUDED_ROOMS


def device_excluded(device, options) -> bool:
    """True if the Bosch device is excluded by the device/room filter options."""
    excluded_devices = options.get(OPT_EXCLUDED_DEVICES) or []
    excluded_rooms = options.get(OPT_EXCLUDED_ROOMS) or []
    if not excluded_devices and not excluded_rooms:
        return False
    if getattr(device, "id", None) in excluded_devices:
        return True
    if getattr(device, "room_id", None) in excluded_rooms:
        return True
    return False


async def async_get_device_id(hass: HomeAssistant, device_id: str) -> None:
    """Get device id from device registry."""
    dev_registry = get_dev_reg(hass)
    device = dev_registry.async_get_device(
        identifiers={(DOMAIN, device_id)}, connections=set()
    )
    return device.id if device is not None else None


async def async_remove_devices(
    hass: HomeAssistant, entity: Entity, entry_id: str
) -> None:
    """Get item that is removed from session."""
    dev_registry = get_dev_reg(hass)
    device = dev_registry.async_get_device(
        identifiers={(DOMAIN, entity.device_id)}, connections=set()
    )
    if device is not None:
        dev_registry.async_update_device(device.id, remove_config_entry_id=entry_id)


async def async_migrate_to_new_unique_id(
    hass: HomeAssistant,
    platform: str,
    device: SHCDevice,
    attr_name: str | None = None,
    old_unique_id: str | None = None,
) -> None:
    """Migrate old unique ids to new unique ids."""
    if old_unique_id is None:
        old_unique_id = (
            f"{device.serial}"
            if attr_name is None
            else f"{device.serial}_{attr_name.lower()}"
        )

    ent_reg = entity_registry.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, old_unique_id)

    if entity_id is not None:
        new_unique_id = (
            f"{device.root_device_id}_{device.id}"
            if attr_name is None
            else f"{device.root_device_id}_{device.id}_{attr_name.lower()}"
        )
        try:
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
        except ValueError:
            LOGGER.warning(
                "Skip migration of id [%s] to [%s] because it already exists",
                old_unique_id,
                new_unique_id,
            )
        else:
            LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                old_unique_id,
                new_unique_id,
            )


class SHCEntity(Entity):
    """Representation of a SHC base entity."""

    _attr_has_entity_name = True

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the generic SHC device."""
        self._device = device
        self._entry_id = entry_id
        # Primary entity: _attr_name = None means HA uses the device name as the
        # entity name.  Sub-classes that represent a feature set _attr_name to the
        # feature label (without the device name prefix, since HA prepends it).
        self._attr_name = None
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"
        self._update_attr()

    def _update_attr(self) -> None:
        pass

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self._update_attr()
            self.schedule_update_ha_state()

        def update_entity_information():
            if self._device.deleted:
                # Fires from the SHC poll thread → schedule on the loop safely
                # instead of hass.add_job (#288-cluster).
                self.hass.loop.call_soon_threadsafe(
                    self.hass.async_create_task,
                    async_remove_devices(self.hass, self, self._entry_id),
                )
            else:
                self._update_attr()
                self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)
        self._device.subscribe_callback(self.entity_id, update_entity_information)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)
        self._device.unsubscribe_callback(self.entity_id)

    @property
    def device_name(self):
        """Name of the device."""
        return self._device.name

    @property
    def device_id(self):
        """Device id of the entity."""
        return self._device.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self.device_name,
            manufacturer=self._device.manufacturer,
            model=self._device.device_model,
            via_device=(DOMAIN, self._device.root_device_id),
        )

    @property
    def available(self):
        """Return false if status is unavailable."""
        return self._device.status == "AVAILABLE"

    @property
    def should_poll(self):
        """Report polling mode. SHC Entity is communicating via long polling."""
        return False
