"""Button entities for the Span Panel."""

import logging
from typing import Final

from span_panel_api import SpanMqttClient, SpanPanelSnapshot
from span_panel_api.exceptions import SpanPanelServerError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpanPanelConfigEntry
from .const import CONF_DEVICE_NAME
from .coordinator import SpanPanelCoordinator
from .entity import SpanPanelEntity
from .helpers import (
    async_create_span_notification,
    construct_panel_unique_id_for_entry,
    has_bess,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


GFE_OVERRIDE_DESCRIPTION: Final = ButtonEntityDescription(
    key="gfe_override",
    translation_key="gfe_override",
)


class SpanPanelGFEOverrideButton(SpanPanelEntity, ButtonEntity):
    """Button entity for overriding the panel's grid-forming entity.

    The SPAN panel's GFE (dominant-power-source) is normally managed by the
    battery system (BESS). When BESS communication is lost, the GFE value
    becomes stale. These buttons allow a user or automation to publish a
    temporary override via the eBus MQTT /set topic. The BESS automatically
    reclaims control when communication is restored.
    """

    def __init__(
        self,
        coordinator: SpanPanelCoordinator,
        description: ButtonEntityDescription,
        override_value: str,
    ) -> None:
        """Initialize the GFE override button."""
        super().__init__(coordinator)
        snapshot: SpanPanelSnapshot = coordinator.data

        self.entity_description = description
        self._override_value = override_value

        self._attr_device_info = self._build_device_info(coordinator, snapshot)

        device_name = coordinator.config_entry.data.get(
            CONF_DEVICE_NAME, coordinator.config_entry.title
        )
        self._attr_unique_id = construct_panel_unique_id_for_entry(
            coordinator, snapshot, description.key, device_name
        )

    async def async_press(self) -> None:
        """Publish the GFE override to the panel."""
        client = self.coordinator.client
        if not hasattr(client, "set_dominant_power_source"):
            _LOGGER.warning("Client does not support GFE override")
            return

        try:
            await client.set_dominant_power_source(self._override_value)
            await self.coordinator.async_request_refresh()
        except SpanPanelServerError:
            warning_msg = (
                f"SPAN API returned a server error attempting "
                f"to override GFE to {self._override_value}."
            )
            _LOGGER.warning(warning_msg)
            await async_create_span_notification(
                self.hass,
                message=warning_msg,
                title="SPAN API Error",
                notification_id="span_panel_gfe_override_error",
            )

    @property
    def available(self) -> bool:
        """Return entity availability.

        The override is only relevant when BESS communication is lost and the
        panel is not already reporting grid-connected. When BESS is online or
        GFE is already GRID, firmware is managing correctly and the button
        should not be pressable.
        """
        if getattr(self.coordinator, "panel_offline", False):
            return False
        if not super().available:
            return False
        snapshot: SpanPanelSnapshot = self.coordinator.data
        bess_connected = snapshot.battery.connected if snapshot.battery else None
        gfe = snapshot.dominant_power_source
        if bess_connected is True:
            return False
        if gfe == "GRID":
            return False
        return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SpanPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for Span Panel."""
    coordinator = config_entry.runtime_data.coordinator

    entities: list[SpanPanelGFEOverrideButton] = []

    snapshot: SpanPanelSnapshot = coordinator.data
    if isinstance(coordinator.client, SpanMqttClient) and has_bess(snapshot):
        entities.append(
            SpanPanelGFEOverrideButton(coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID")
        )

    async_add_entities(entities)
