"""The homee switch platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode
from pyHomee.model_homeegram import HomeeGram

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, HomeeConfigEntry
from .const import CLIMATE_PROFILES, LIGHT_PROFILES
from .entity import HomeeEntity
from .helpers import setup_homee_platform

PARALLEL_UPDATES = 0


def get_device_class(
    attribute: HomeeAttribute, config_entry: HomeeConfigEntry
) -> SwitchDeviceClass:
    """Check device class of Switch according to node profile."""
    node = config_entry.runtime_data.get_node_by_id(attribute.node_id)
    assert node is not None
    if node.profile in [
        NodeProfile.ON_OFF_PLUG,
        NodeProfile.METERING_PLUG,
        NodeProfile.DOUBLE_ON_OFF_PLUG,
        NodeProfile.IMPULSE_PLUG,
    ]:
        return SwitchDeviceClass.OUTLET

    return SwitchDeviceClass.SWITCH


@dataclass(frozen=True, kw_only=True)
class HomeeSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes Homee switch entity."""

    device_class_fn: Callable[[HomeeAttribute, HomeeConfigEntry], SwitchDeviceClass] = (
        lambda attribute, entry: SwitchDeviceClass.SWITCH
    )


SWITCH_DESCRIPTIONS: dict[AttributeType, HomeeSwitchEntityDescription] = {
    AttributeType.EXTERNAL_BINARY_INPUT: HomeeSwitchEntityDescription(
        key="external_binary_input", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.MANUAL_OPERATION: HomeeSwitchEntityDescription(
        key="manual_operation"
    ),
    AttributeType.ON_OFF: HomeeSwitchEntityDescription(
        key="on_off", device_class_fn=get_device_class, name=None
    ),
    AttributeType.WATCHDOG_ON_OFF: HomeeSwitchEntityDescription(
        key="watchdog", entity_category=EntityCategory.CONFIG
    ),
}


async def add_switch_entities(
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    nodes: list[HomeeNode],
) -> None:
    """Add homee switch entities."""
    async_add_entities(
        HomeeSwitch(attribute, config_entry, SWITCH_DESCRIPTIONS[attribute.type])
        for node in nodes
        for attribute in node.attributes
        if (attribute.type in SWITCH_DESCRIPTIONS and attribute.editable)
        and not (
            attribute.type == AttributeType.ON_OFF and node.profile in LIGHT_PROFILES
        )
        and not (
            attribute.type == AttributeType.MANUAL_OPERATION
            and node.profile in CLIMATE_PROFILES
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform for the Homee component."""

    await setup_homee_platform(add_switch_entities, async_add_entities, config_entry)
    async_add_entities(
        HomeegramSwitch(homeegram, config_entry)
        for homeegram in config_entry.runtime_data.homeegrams
    )


class HomeeSwitch(HomeeEntity, SwitchEntity):
    """Representation of a Homee switch."""

    entity_description: HomeeSwitchEntityDescription

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeSwitchEntityDescription,
    ) -> None:
        """Initialize a Homee switch entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        if attribute.instance == 0:
            if attribute.type == AttributeType.ON_OFF:
                self._attr_name = None
            else:
                self._attr_translation_key = description.key
        else:
            self._attr_translation_key = f"{description.key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return bool(self._attribute.current_value)

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return the device class of the switch."""
        return self.entity_description.device_class_fn(self._attribute, self._entry)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.async_set_homee_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.async_set_homee_value(0)


class HomeegramSwitch(SwitchEntity):
    """Representation of a Homeegram as switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, homeegram: HomeeGram, entry: HomeeConfigEntry) -> None:
        """Initialize a homee Homeegram switch entity."""
        self._homeegram = homeegram
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}-hg-{homeegram.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}-homeegrams")},
            name="Homeegrams",
            model="Homeegram Switches",
            via_device=(DOMAIN, entry.runtime_data.settings.uid),
        )
        self._attr_translation_key = "homeegram"
        self._host_connected = entry.runtime_data.connected
        self._attr_name = homeegram.name

        self._attr_entity_registry_enabled_default = self._is_enabled_by_default(
            homeegram
        )

    async def async_added_to_hass(self) -> None:
        """Add the Homeegram entity to home assistant."""
        self.async_on_remove(
            self._homeegram.add_on_changed_listener(self._on_homeegram_updated)
        )
        self.async_on_remove(
            self._entry.runtime_data.add_connection_listener(
                self._on_connection_changed
            )
        )

    @property
    def is_on(self) -> bool:
        """Return True if homeegram is executing."""
        return bool(self._homeegram.play)

    @property
    def available(self) -> bool:
        """Return the availability of the homeegram based on host availability."""
        return bool(self._homeegram.active) and self._host_connected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Trigger Homeegram on switching on."""
        await self._entry.runtime_data.play_homeegram(self._homeegram.id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turning off homeegrams is not supported."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="homeegram_turn_off_not_supported",
        )

    def _on_homeegram_updated(self, homeegram: HomeeGram) -> None:
        self.async_write_ha_state()

    async def _on_connection_changed(self, connected: bool) -> None:
        self._host_connected = connected
        self.async_write_ha_state()

    def _is_enabled_by_default(self, homeegram: HomeeGram) -> bool:
        """Return if the homeegram should be enabled by default."""
        # Only enable homeegram switches by default if there is more than 1 homeegram action.
        return (
            sum(len(action_list) for action_list in homeegram.actions.data.values()) > 1
        )
