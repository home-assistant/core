"""Code to handle a Livisi switches."""

from typing import Any, override

from livisi import LivisiDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LIVISI_STATE_CHANGE, LOGGER, ON_STATE, SWITCH_DEVICE_TYPES
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LivisiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch device."""
    coordinator = config_entry.runtime_data

    @callback
    def handle_coordinator_update() -> None:
        """Add switch."""
        shc_devices: list[LivisiDevice] = coordinator.data
        entities: list[SwitchEntity] = []
        for device in shc_devices:
            if (
                device.type in SWITCH_DEVICE_TYPES
                and device.id not in coordinator.devices
            ):
                livisi_switch: SwitchEntity = LivisiSwitch(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s", device.type)
                coordinator.devices.add(device.id)
                entities.append(livisi_switch)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSwitch(LivisiEntity, SwitchEntity):
    """Represents the Livisi Switch."""

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi switch."""
        super().__init__(config_entry, coordinator, device)
        self._capability_id = self.capabilities["SwitchActuator"]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self._capability_id, key=ON_STATE, value=True
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")
        self._attr_available = True

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self._capability_id, key=ON_STATE, value=False
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")
        self._attr_available = True

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        await self.async_update_value()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._capability_id}_{ON_STATE}",
                self.update_states,
            )
        )

    @override
    async def async_update_value(self) -> bool:
        """Get the current switch state."""
        response = await self.coordinator.async_get_device_state(
            self._capability_id, ON_STATE
        )
        if response is None:
            self._attr_is_on = False
            self._attr_available = False
            return False
        self._attr_is_on = response
        return True

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the switch device."""
        self._attr_available = True
        self._attr_is_on = state
        self.async_write_ha_state()
