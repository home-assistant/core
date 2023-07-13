"""Entity representing a Blue Current charge point."""
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import Connector
from .const import DOMAIN, MODEL_TYPE


class BlueCurrentEntity(Entity):
    """Define a base charge point entity."""

    def __init__(self, connector: Connector, evse_id: str) -> None:
        """Initialize the entity."""
        self.connector: Connector = connector

        name = connector.charge_points[evse_id][ATTR_NAME]

        self.evse_id = evse_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, evse_id)},
            name=name if name != "" else evse_id,
            manufacturer="Blue Current",
            model=connector.charge_points[evse_id][MODEL_TYPE],
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_value_update_{self.evse_id}", update
            )
        )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
