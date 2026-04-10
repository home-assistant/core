"""The homee button platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute, HomeeNode
from pyHomee.model_homeegram import HomeeGram

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, HomeeConfigEntry
from .entity import HomeeEntity
from .helpers import setup_homee_platform

PARALLEL_UPDATES = 0

BUTTON_DESCRIPTIONS: dict[AttributeType, ButtonEntityDescription] = {
    AttributeType.AUTOMATIC_MODE_IMPULSE: ButtonEntityDescription(key="automatic_mode"),
    AttributeType.BRIEFLY_OPEN_IMPULSE: ButtonEntityDescription(key="briefly_open"),
    AttributeType.IDENTIFICATION_MODE: ButtonEntityDescription(
        key="identification_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=ButtonDeviceClass.IDENTIFY,
    ),
    AttributeType.IMPULSE: ButtonEntityDescription(key="impulse"),
    AttributeType.LIGHT_IMPULSE: ButtonEntityDescription(key="light"),
    AttributeType.OPEN_PARTIAL_IMPULSE: ButtonEntityDescription(key="open_partial"),
    AttributeType.PERMANENTLY_OPEN_IMPULSE: ButtonEntityDescription(
        key="permanently_open"
    ),
    AttributeType.RESET_METER: ButtonEntityDescription(
        key="reset_meter",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.VENTILATE_IMPULSE: ButtonEntityDescription(key="ventilate"),
}


async def add_button_entities(
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    nodes: list[HomeeNode],
) -> None:
    """Add homee button entities."""
    async_add_entities(
        HomeeButton(attribute, config_entry, BUTTON_DESCRIPTIONS[attribute.type])
        for node in nodes
        for attribute in node.attributes
        if attribute.type in BUTTON_DESCRIPTIONS and attribute.editable
    )


def get_homeegram_buttons(config_entry: HomeeConfigEntry) -> list[HomeegramButton]:
    """Get buttons for homeegrams."""
    return [
        HomeegramButton(homeegram, config_entry)
        for homeegram in config_entry.runtime_data.homeegrams
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the homee platform for the button component."""

    await setup_homee_platform(add_button_entities, async_add_entities, config_entry)
    async_add_entities(get_homeegram_buttons(config_entry))


class HomeeButton(HomeeEntity, ButtonEntity):
    """Representation of a Homee button."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize a Homee button entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        if attribute.instance == 0:
            if attribute.type == AttributeType.IMPULSE:
                self._attr_name = None
            else:
                self._attr_translation_key = description.key
        else:
            self._attr_translation_key = f"{description.key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.async_set_homee_value(1)


class HomeegramButton(ButtonEntity):
    """Representation of a Homeegram as button."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, homeegram: HomeeGram, entry: HomeeConfigEntry) -> None:
        """Initialize a homee Homeegram button entity."""
        self._homeegram = homeegram
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}-hg-{homeegram.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}-homeegrams")},
            name="Homeegrams",
            model="Homeegram Buttons",
            via_device=(DOMAIN, entry.runtime_data.settings.uid),
        )
        self._host_connected = entry.runtime_data.connected
        self._attr_name = homeegram.name

        self._attr_entity_registry_enabled_default = self.add_as_enabled(homeegram)

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
    def available(self) -> bool:
        """Return the availability of the homeegram based on host availability."""
        return self._homeegram.active and self._host_connected

    async def async_press(self) -> None:
        """Trigger Homeegram on push."""
        await self._entry.runtime_data.play_homeegram(self._homeegram.id)

    def _on_homeegram_updated(self, homeegram: HomeeGram) -> None:
        self.schedule_update_ha_state()

    async def _on_connection_changed(self, connected: bool) -> None:
        self._host_connected = connected
        self.schedule_update_ha_state()

    def add_as_enabled(self, homeegram: HomeeGram) -> bool:
        """Get the number of actions in a homeegram."""
        # We only enable if homeegram has more than one action and it is activated.
        return (
            sum(len(action_type) for action_type in homeegram.actions.data.values()) > 1
            and homeegram.active
        )
