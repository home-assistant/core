"""Creates Homewizard Energy switch entities."""
from __future__ import annotations

from typing import Any

from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    if coordinator.data["state"]:
        entities.append(HWEnergyMainSwitchEntity(coordinator, entry))
        entities.append(HWEnergySwitchLockEntity(coordinator, entry))

    if coordinator.data["system"]:
        entities.append(HWEnergyEnableCloudEntity(hass, coordinator, entry))

    async_add_entities(entities)


class HWEnergySwitchEntity(HomeWizardEntity, SwitchEntity):
    """Representation switchable entity."""

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_{key}"


class HWEnergyMainSwitchEntity(HWEnergySwitchEntity):
    """Representation of the main power switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self, coordinator: HWEnergyDeviceUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "power_on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_power_on(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_power_on(False)

    async def _async_set_power_on(self, power_on: bool) -> None:
        """Set power state helper method."""
        try:
            await self.coordinator.api.state_set(power_on=power_on)
        except RequestError as ex:
            raise HomeAssistantError from ex
        except DisabledError as ex:
            await self.hass.config_entries.async_reload(self.coordinator.entry_id)
            raise HomeAssistantError from ex

        await self.coordinator.async_refresh()

    @property
    def available(self) -> bool:
        """
        Return availability of power_on.

        This switch becomes unavailable when switch_lock is enabled.
        """
        return super().available and not self.coordinator.data["state"].switch_lock

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.coordinator.data["state"].power_on)


class HWEnergySwitchLockEntity(HWEnergySwitchEntity):
    """
    Representation of the switch-lock configuration.

    Switch-lock is a feature that forces the relay in 'on' state.
    It disables any method that can turn of the relay.
    """

    _attr_name = "Switch lock"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: HWEnergyDeviceUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "switch_lock")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch-lock on."""
        await self._async_set_switch_lock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch-lock off."""
        await self._async_set_switch_lock(False)

    async def _async_set_switch_lock(self, switch_lock: bool) -> None:
        """Set switck lock helper method."""
        try:
            await self.coordinator.api.state_set(switch_lock=switch_lock)
        except RequestError as ex:
            raise HomeAssistantError from ex
        except DisabledError as ex:
            await self.hass.config_entries.async_reload(self.coordinator.entry_id)
            raise HomeAssistantError from ex

        await self.coordinator.async_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.coordinator.data["state"].switch_lock)


class HWEnergyEnableCloudEntity(HWEnergySwitchEntity):
    """
    Representation of the enable cloud configuration.

    Turning off 'cloud connection' turns off all communication to HomeWizard Cloud.
    At this point, the device is fully local.
    """

    _attr_name = "Cloud connection"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "cloud_connection")
        self.hass = hass
        self.entry = entry

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn cloud connection on."""
        await self._async_set_cloud_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn cloud connection off."""
        await self._async_set_cloud_enabled(False)

    async def _async_set_cloud_enabled(self, cloud_enabled: bool) -> None:
        """Set cloud enabled helper method."""
        try:
            await self.coordinator.api.system_set(cloud_enabled=cloud_enabled)
        except RequestError as ex:
            raise HomeAssistantError from ex
        except DisabledError as ex:
            await self.hass.config_entries.async_reload(self.coordinator.entry_id)
            raise HomeAssistantError from ex

        await self.coordinator.async_refresh()

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return "mdi:cloud" if self.is_on else "mdi:cloud-off-outline"

    @property
    def is_on(self) -> bool:
        """Return true if cloud connection is active."""
        return bool(self.coordinator.data["system"].cloud_enabled)
