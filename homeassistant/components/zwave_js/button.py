"""Representation of Z-Wave buttons."""

from __future__ import annotations

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN, LOGGER
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .helpers import get_device_info, get_valueless_base_unique_id

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_button(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Button."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "notification idle":
            entities.append(ZWaveNotificationIdleButton(config_entry, driver, info))
        else:
            entities.append(ZwaveBooleanNodeButton(config_entry, driver, info))

        async_add_entities(entities)

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

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{BUTTON_DOMAIN}",
            async_add_button,
        )
    )


class ZwaveBooleanNodeButton(ZWaveBaseEntity, ButtonEntity):
    """Representation of a ZWave button entity for a boolean value."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize entity."""
        super().__init__(config_entry, driver, info)
        self._attr_name = self.generate_name(include_value_name=True)

    async def async_press(self) -> None:
        """Press the button."""
        await self._async_set_value(self.info.primary_value, True)


class ZWaveNodePingButton(ButtonEntity):
    """Representation of a ping button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "ping"

    def __init__(self, driver: Driver, node: ZwaveNode) -> None:
        """Initialize a ping Z-Wave device button entity."""
        self.node = node

        # Entity class attributes
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.ping"
        # device may not be precreated in main handler yet
        self._attr_device_info = get_device_info(driver, node)

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        # We log an error instead of raising an exception because this service call occurs
        # in a separate task since it is called via the dispatcher and we don't want to
        # raise the exception in that separate task because it is confusing to the user.
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value"
            " service won't work for it"
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

        # we don't listen for `remove_entity_on_ready_node` signal because this entity
        # is created when the node is added which occurs before ready. It only needs to
        # be removed if the node is removed from the network.
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


class ZWaveNotificationIdleButton(ZWaveBaseEntity, ButtonEntity):
    """Button to idle Notification CC values."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWaveNotificationIdleButton entity."""
        super().__init__(config_entry, driver, info)
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
            name_prefix="Idle",
        )
        self._attr_unique_id = f"{self._attr_unique_id}.notification_idle"

    async def async_press(self) -> None:
        """Press the button."""
        await self.info.node.async_manually_idle_notification_value(
            self.info.primary_value
        )
