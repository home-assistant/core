"""Representation of Z-Wave buttons."""
from __future__ import annotations

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN, LOGGER
from .helpers import get_device_id, get_valueless_base_unique_id

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_ping_button_entity(node: ZwaveNode) -> None:
        """Add ping button entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveNodePingButton(driver, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_ping_button_entity",
            async_add_ping_button_entity,
        )
    )


class ZWaveNodePingButton(ButtonEntity):
    """Representation of a ping button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, driver: Driver, node: ZwaveNode) -> None:
        """Initialize a ping Z-Wave device button entity."""
        self.node = node
        name: str = (
            node.name or node.device_config.description or f"Node {node.node_id}"
        )
        # Entity class attributes
        self._attr_name = f"{name}: Ping"
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.ping"
        # device is precreated in main handler
        self._attr_device_info = DeviceInfo(
            identifiers={get_device_id(driver, node)},
        )

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value "
            "service won't work for it"
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity",
                self.async_remove,
            )
        )

    async def async_press(self) -> None:
        """Press the button."""
        self.hass.async_create_task(self.node.async_ping())
