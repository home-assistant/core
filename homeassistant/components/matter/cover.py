"""Matter cover."""
from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter cover from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.COVER, async_add_entities)


class MatterCover(MatterEntity, CoverEntity):
    """Representation of a Matter cover."""

    entity_description: CoverEntityDescription

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        return features

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        if self._attr_current_cover_position:
            current_position = self._attr_current_cover_position
        else:
            current_position = self.get_matter_attribute_value(
                clusters.WindowCovering.Attributes.CurrentPositionLiftPercentage
            )

        assert current_position is not None

        LOGGER.info(
            "Got current position %s for %s",
            current_position,
            self.entity_id,
        )

        return current_position

    @property
    def is_closed(self) -> bool:
        """Return true if cover is closed, else False."""
        return self.current_cover_position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        operational_status = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.OperationalStatus
        )

        assert operational_status is not None

        LOGGER.debug(
            "GOT OPERATIONAL STATUS %s for %s", operational_status, self.entity_id
        )
        state = operational_status & 0b11
        return state == 0b10

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        operational_status = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.OperationalStatus
        )

        assert operational_status is not None

        LOGGER.debug(
            "GOT OPERATIONAL STATUS %s for %s", operational_status, self.entity_id
        )
        state = operational_status & 0b11
        return state == 0b01

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.send_device_command(clusters.WindowCovering.Commands.StopMotion())

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.UpOrOpen())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.DownOrClose())

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self.send_device_command(
            clusters.WindowCovering.Commands.GoToLiftPercentage(position)
        )

    async def send_device_command(self, command: Any) -> None:
        """Send device command."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_current_cover_position = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercentage
        )
        LOGGER.info("GOT CURRENT POSITION %s", self._attr_current_cover_position)


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=CoverEntityDescription(key="MatterCover"),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
            clusters.WindowCovering.Attributes.OperationalStatus,
        ),
        optional_attributes=(),
        # restrict device type to prevent discovery in switch platform
        not_device_type=(device_types.OnOffPlugInUnit,),
    ),
]
