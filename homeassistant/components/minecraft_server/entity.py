"""Base entity for the Minecraft Server integration."""

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import MinecraftServer
from .const import DOMAIN, MANUFACTURER


class MinecraftServerEntity(Entity):
    """Representation of a Minecraft Server base entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        server: MinecraftServer,
        type_name: str,
        icon: str,
        device_class: str | None,
    ) -> None:
        """Initialize base entity."""
        self._server = server
        self._attr_icon = icon
        self._attr_unique_id = f"{self._server.unique_id}-{type_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server.unique_id)},
            manufacturer=MANUFACTURER,
            model=f"Minecraft Server ({self._server.version})",
            name=self._server.name,
            sw_version=str(self._server.protocol_version),
        )
        self._attr_device_class = device_class
        self._extra_state_attributes = None
        self._disconnect_dispatcher: CALLBACK_TYPE | None = None

    async def async_update(self) -> None:
        """Fetch data from the server."""
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Connect dispatcher to signal from server."""
        self._disconnect_dispatcher = async_dispatcher_connect(
            self.hass, self._server.signal_name, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher before removal."""
        if self._disconnect_dispatcher:
            self._disconnect_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)
