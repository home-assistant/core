"""Platform for Kostal Plenticore switches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERVICE_CODE
from .coordinator import PlenticoreConfigEntry, SettingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PlenticoreSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes plenticore switch entities."""

    module_id: str
    is_on: str
    on_value: str
    on_label: str
    off_value: str
    off_label: str
    installer_required: bool = False


SWITCH_SETTINGS_DATA = [
    PlenticoreSwitchEntityDescription(
        module_id="devices:local",
        key="Battery:Strategy",
        name="Battery Strategy",
        is_on="1",
        on_value="1",
        on_label="Automatic",
        off_value="2",
        off_label="Automatic economical",
    ),
    PlenticoreSwitchEntityDescription(
        module_id="devices:local",
        key="Battery:ManualCharge",
        name="Battery Manual Charge",
        is_on="1",
        on_value="1",
        on_label="On",
        off_value="0",
        off_label="Off",
        installer_required=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlenticoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add kostal plenticore Switch."""
    plenticore = entry.runtime_data

    entities: list[Entity] = []

    available_settings_data = await plenticore.client.get_settings()
    settings_data_update_coordinator = SettingDataUpdateCoordinator(
        hass, entry, _LOGGER, "Settings Data", timedelta(seconds=30), plenticore
    )
    for description in SWITCH_SETTINGS_DATA:
        if (
            description.module_id not in available_settings_data
            or description.key
            not in (
                setting.id for setting in available_settings_data[description.module_id]
            )
        ):
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s",
                description.module_id,
                description.key,
            )
            continue
        if entry.data.get(CONF_SERVICE_CODE) is None and description.installer_required:
            _LOGGER.debug(
                "Skipping installer required setting data %s/%s",
                description.module_id,
                description.key,
            )
            continue
        entities.append(
            PlenticoreDataSwitch(
                settings_data_update_coordinator,
                description,
                entry.entry_id,
                entry.title,
                plenticore.device_info,
            )
        )

    # add shadow management switches for strings which support it
    string_count_setting = await plenticore.client.get_setting_values(
        "devices:local", "Properties:StringCnt"
    )
    try:
        string_count = int(
            string_count_setting["devices:local"]["Properties:StringCnt"]
        )
    except ValueError:
        string_count = 0

    dc_strings = tuple(range(string_count))
    dc_string_feature_ids = tuple(
        PlenticoreShadowMgmtSwitch.DC_STRING_FEATURE_DATA_ID % dc_string
        for dc_string in dc_strings
    )

    dc_string_features = await plenticore.client.get_setting_values(
        PlenticoreShadowMgmtSwitch.MODULE_ID,
        dc_string_feature_ids,
    )

    for dc_string, dc_string_feature_id in zip(
        dc_strings, dc_string_feature_ids, strict=True
    ):
        try:
            dc_string_feature = int(
                dc_string_features[PlenticoreShadowMgmtSwitch.MODULE_ID][
                    dc_string_feature_id
                ]
            )
        except ValueError:
            dc_string_feature = 0

        if dc_string_feature == PlenticoreShadowMgmtSwitch.SHADOW_MANAGEMENT_SUPPORT:
            entities.append(
                PlenticoreShadowMgmtSwitch(
                    settings_data_update_coordinator,
                    dc_string,
                    entry.entry_id,
                    entry.title,
                    plenticore.device_info,
                )
            )
        else:
            _LOGGER.debug(
                "Skipping shadow management for DC string %d, not supported (Feature: %d)",
                dc_string + 1,
                dc_string_feature,
            )

    async_add_entities(entities)


class PlenticoreDataSwitch(
    CoordinatorEntity[SettingDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Plenticore Switch."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: PlenticoreSwitchEntityDescription

    def __init__(
        self,
        coordinator: SettingDataUpdateCoordinator,
        description: PlenticoreSwitchEntityDescription,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create a new Switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entity_description = description
        self.platform_name = platform_name
        self.module_id = description.module_id
        self.data_id = description.key
        self._name = description.name
        self._is_on = description.is_on
        self._attr_name = f"{platform_name} {description.name}"
        self.on_value = description.on_value
        self.on_label = description.on_label
        self.off_value = description.off_value
        self.off_label = description.off_label
        self._attr_unique_id = f"{entry_id}_{description.module_id}_{description.key}"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
            and self.data_id in self.coordinator.data[self.module_id]
        )

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.start_fetch_data(self.module_id, self.data_id)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if await self.coordinator.async_write_data(
            self.module_id, {self.data_id: self.on_value}
        ):
            self.coordinator.name = f"{self.platform_name} {self._name} {self.on_label}"
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        if await self.coordinator.async_write_data(
            self.module_id, {self.data_id: self.off_value}
        ):
            self.coordinator.name = (
                f"{self.platform_name} {self._name} {self.off_label}"
            )
            await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        if self.coordinator.data[self.module_id][self.data_id] == self._is_on:
            self.coordinator.name = f"{self.platform_name} {self._name} {self.on_label}"
        else:
            self.coordinator.name = (
                f"{self.platform_name} {self._name} {self.off_label}"
            )
        return bool(self.coordinator.data[self.module_id][self.data_id] == self._is_on)


class PlenticoreShadowMgmtSwitch(
    CoordinatorEntity[SettingDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Plenticore Switch for shadow management.

    The shadow management switch can be controlled for each DC string separately. The DC string is
    coded as bit in a single settings value, bit 0 for DC string 1, bit 1 for DC string 2, etc.

    Not all DC strings are available for shadown management, for example if one of them is used
    for a battery.
    """

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: SwitchEntityDescription

    MODULE_ID: Final = "devices:local"

    SHADOW_DATA_ID: Final = "Generator:ShadowMgmt:Enable"
    """Settings id for the bit coded shadow management."""

    DC_STRING_FEATURE_DATA_ID: Final = "Properties:String%dFeatures"
    """Settings id pattern for the DC string features."""

    SHADOW_MANAGEMENT_SUPPORT: Final = 1
    """Feature value for shadow management support in the DC string features."""

    def __init__(
        self,
        coordinator: SettingDataUpdateCoordinator,
        dc_string: int,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create a new Switch Entity for Plenticore shadow management."""
        super().__init__(coordinator, context=(self.MODULE_ID, self.SHADOW_DATA_ID))

        self._mask: Final = 1 << dc_string

        self.entity_description = SwitchEntityDescription(
            key=f"ShadowMgmt{dc_string}",
            name=f"Shadow Management DC string {dc_string + 1}",
            entity_registry_enabled_default=False,
        )

        self.platform_name = platform_name
        self._attr_name = f"{platform_name} {self.entity_description.name}"
        self._attr_unique_id = (
            f"{entry_id}_{self.MODULE_ID}_{self.SHADOW_DATA_ID}_{dc_string}"
        )
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.MODULE_ID in self.coordinator.data
            and self.SHADOW_DATA_ID in self.coordinator.data[self.MODULE_ID]
        )

    def _get_shadow_mgmt_value(self) -> int:
        """Return the current shadow management value for all strings as integer."""
        try:
            return int(self.coordinator.data[self.MODULE_ID][self.SHADOW_DATA_ID])
        except ValueError:
            return 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn shadow management on."""
        shadow_mgmt_value = self._get_shadow_mgmt_value()
        shadow_mgmt_value |= self._mask

        if await self.coordinator.async_write_data(
            self.MODULE_ID, {self.SHADOW_DATA_ID: str(shadow_mgmt_value)}
        ):
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn shadow management off."""
        shadow_mgmt_value = self._get_shadow_mgmt_value()
        shadow_mgmt_value &= ~self._mask

        if await self.coordinator.async_write_data(
            self.MODULE_ID, {self.SHADOW_DATA_ID: str(shadow_mgmt_value)}
        ):
            await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if shadow management is on."""
        return (self._get_shadow_mgmt_value() & self._mask) != 0
