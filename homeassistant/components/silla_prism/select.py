"""Silla Prism select entity module."""

import logging
from typing import override

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SELECT_DOMAIN
from .entity import PrismBaseEntity
from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    entry_data: RuntimeEntryData = entry.runtime_data
    _LOGGER.debug("async_setup_entry for select: %s", entry_data)

    ports = entry_data.ports
    selects = []
    for port in range(1, ports + 1):
        selects.extend(
            [PrismSelect(entry_data, description, port) for description in SELECTS]
        )
    async_add_entities(selects)


class PrismSelectEntityDescription(SelectEntityDescription, frozen_or_thawed=True):
    """A class that describes prism binary sensor entities."""

    expire_after: float = 0
    topic: str | None = None
    topic_out: str | None = None


class PrismSelect(PrismBaseEntity, SelectEntity):
    """A Select for Prism wallbox devices."""

    _attr_has_entity_name = True

    entity_description: PrismSelectEntityDescription

    def description(
        self, port: int, mulitport: bool, description: PrismSelectEntityDescription
    ) -> PrismSelectEntityDescription:
        """Create a Select entity for Prism EVSE devices."""
        assert description.topic is not None
        assert description.topic_out is not None
        if mulitport:
            return PrismSelectEntityDescription(
                key=description.key.format(port),
                topic=description.topic.format(port),
                entity_category=description.entity_category,
                device_class=description.device_class,
                options=description.options,
                has_entity_name=description.has_entity_name,
                translation_key=description.translation_key,
                topic_out=description.topic_out.format(port),
            )
        return PrismSelectEntityDescription(
            key=description.key[0:-3],
            topic=description.topic.format(port),
            entity_category=description.entity_category,
            device_class=description.device_class,
            options=description.options,
            has_entity_name=description.has_entity_name,
            translation_key=description.translation_key,
            topic_out=description.topic_out.format(port),
        )

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismSelectEntityDescription,
        port: int,
    ) -> None:
        """Init Prism select."""
        ismultiport = entry_data.ports > 1
        if not ismultiport:
            device = entry_data.devices[0]
        else:
            device = entry_data.devices[port]

        _description = self.description(port, ismultiport, description)
        super().__init__(
            entry_data,
            SELECT_DOMAIN,
            _description,
            device,
        )

        self._attr_current_option = None
        assert _description.topic_out is not None
        self._topic_out = entry_data.topic + _description.topic_out

    @override
    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        try:
            _sel = int(msg.payload) - 1
        except ValueError:
            _LOGGER.warning(
                "Invalid topic payload: topic:%s payload:%s",
                self._topic,
                msg.payload,
            )
            return

        # Update state if value is valid and different from current option
        if (
            0 <= _sel < len(self.options)
            and self.options[_sel] != self._attr_current_option
        ):
            self._attr_current_option = self.options[_sel]
            self.schedule_update_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        _LOGGER.debug("async_added_to_hass key:%s", self.entity_description.key)
        await self._subscribe_topic()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        _LOGGER.debug("async_will_remove_from_hass key:%s", self.entity_description.key)
        await super().async_will_remove_from_hass()
        self.cleanup_expiration_trigger()

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.schedule_update_ha_state()
        await mqtt.async_publish(
            self.hass, self._topic_out, self.options.index(option) + 1
        )


SELECTS: tuple[PrismSelectEntityDescription, ...] = (
    PrismSelectEntityDescription(
        key="set_mode_{}",
        topic="{}/mode",
        topic_out="{}/command/set_mode",
        entity_category=EntityCategory.CONFIG,
        options=["solar", "normal", "paused", "hybrid"],
        has_entity_name=True,
        translation_key="set_port_mode",
    ),
)
