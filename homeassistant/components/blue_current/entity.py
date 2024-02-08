"""Entity representing a Blue Current charge point."""
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import Connector
from .const import DOMAIN, MODEL_TYPE


class BlueCurrentEntity(Entity):
    """Define a base Blue Current entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, connector: Connector, signal: str) -> None:
        """Initialize the entity."""
        self.connector: Connector = connector
        self.signal: str = signal
        self.has_value: bool = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, self.signal, update))

        self.update_from_latest_data()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.connector.available and self.has_value

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError


class ChargepointEntity(BlueCurrentEntity):
    """Define a base charge point entity."""

    def __init__(self, connector: Connector, evse_id: str) -> None:
        """Initialize the entity."""
        chargepoint_name = connector.charge_points[evse_id][ATTR_NAME]

        self.evse_id = evse_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, evse_id)},
            name=chargepoint_name if chargepoint_name != "" else evse_id,
            manufacturer="Blue Current",
            model=connector.charge_points[evse_id][MODEL_TYPE],
        )

        super().__init__(connector, f"{DOMAIN}_value_update_{self.evse_id}")
