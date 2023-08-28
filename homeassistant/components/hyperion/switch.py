"""Switch platform for Hyperion."""
from __future__ import annotations

import functools
from typing import Any

from hyperion import client
from hyperion.const import (
    KEY_COMPONENT,
    KEY_COMPONENTID_ALL,
    KEY_COMPONENTID_BLACKBORDER,
    KEY_COMPONENTID_BOBLIGHTSERVER,
    KEY_COMPONENTID_FORWARDER,
    KEY_COMPONENTID_GRABBER,
    KEY_COMPONENTID_LEDDEVICE,
    KEY_COMPONENTID_SMOOTHING,
    KEY_COMPONENTID_TO_NAME,
    KEY_COMPONENTID_V4L,
    KEY_COMPONENTS,
    KEY_COMPONENTSTATE,
    KEY_ENABLED,
    KEY_NAME,
    KEY_STATE,
    KEY_UPDATE,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import (
    get_hyperion_device_id,
    get_hyperion_unique_id,
    listen_for_instance_updates,
)
from .const import (
    CONF_INSTANCE_CLIENTS,
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_COMPONENT_SWITCH_BASE,
)

COMPONENT_SWITCHES = [
    KEY_COMPONENTID_ALL,
    KEY_COMPONENTID_SMOOTHING,
    KEY_COMPONENTID_BLACKBORDER,
    KEY_COMPONENTID_FORWARDER,
    KEY_COMPONENTID_BOBLIGHTSERVER,
    KEY_COMPONENTID_GRABBER,
    KEY_COMPONENTID_LEDDEVICE,
    KEY_COMPONENTID_V4L,
]


def _component_to_unique_id(server_id: str, component: str, instance_num: int) -> str:
    """Convert a component to a unique_id."""
    return get_hyperion_unique_id(
        server_id,
        instance_num,
        slugify(
            f"{TYPE_HYPERION_COMPONENT_SWITCH_BASE} {KEY_COMPONENTID_TO_NAME[component]}"
        ),
    )


def _component_to_translation_key(component: str) -> str:
    return {
        KEY_COMPONENTID_ALL: "all",
        KEY_COMPONENTID_SMOOTHING: "smoothing",
        KEY_COMPONENTID_BLACKBORDER: "blackbar_detection",
        KEY_COMPONENTID_FORWARDER: "forwarder",
        KEY_COMPONENTID_BOBLIGHTSERVER: "boblight_server",
        KEY_COMPONENTID_GRABBER: "platform_capture",
        KEY_COMPONENTID_LEDDEVICE: "led_device",
        KEY_COMPONENTID_V4L: "usb_capture",
    }[component]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Hyperion platform from config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    server_id = config_entry.unique_id

    @callback
    def instance_add(instance_num: int, instance_name: str) -> None:
        """Add entities for a new Hyperion instance."""
        assert server_id
        switches = []
        for component in COMPONENT_SWITCHES:
            switches.append(
                HyperionComponentSwitch(
                    server_id,
                    instance_num,
                    instance_name,
                    component,
                    entry_data[CONF_INSTANCE_CLIENTS][instance_num],
                ),
            )
        async_add_entities(switches)

    @callback
    def instance_remove(instance_num: int) -> None:
        """Remove entities for an old Hyperion instance."""
        assert server_id
        for component in COMPONENT_SWITCHES:
            async_dispatcher_send(
                hass,
                SIGNAL_ENTITY_REMOVE.format(
                    _component_to_unique_id(server_id, component, instance_num),
                ),
            )

    listen_for_instance_updates(hass, config_entry, instance_add, instance_remove)


class HyperionComponentSwitch(SwitchEntity):
    """ComponentBinarySwitch switch class."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        server_id: str,
        instance_num: int,
        instance_name: str,
        component_name: str,
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the switch."""
        self._unique_id = _component_to_unique_id(
            server_id, component_name, instance_num
        )
        self._device_id = get_hyperion_device_id(server_id, instance_num)
        self._attr_translation_key = _component_to_translation_key(component_name)
        self._instance_name = instance_name
        self._component_name = component_name
        self._client = hyperion_client
        self._client_callbacks = {
            f"{KEY_COMPONENTS}-{KEY_UPDATE}": self._update_components
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Whether or not the entity is enabled by default."""
        # These component controls are for advanced users and are disabled by default.
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        for component in self._client.components or []:
            if component[KEY_NAME] == self._component_name:
                return bool(component.setdefault(KEY_ENABLED, False))
        return False

    @property
    def available(self) -> bool:
        """Return server availability."""
        return bool(self._client.has_loaded_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=HYPERION_MANUFACTURER_NAME,
            model=HYPERION_MODEL_NAME,
            name=self._instance_name,
            configuration_url=self._client.remote_url,
        )

    async def _async_send_set_component(self, value: bool) -> None:
        """Send a component control request."""
        await self._client.async_send_set_component(
            **{
                KEY_COMPONENTSTATE: {
                    KEY_COMPONENT: self._component_name,
                    KEY_STATE: value,
                }
            }
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_send_set_component(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_send_set_component(False)

    @callback
    def _update_components(self, _: dict[str, Any] | None = None) -> None:
        """Update Hyperion components."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self._unique_id),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

        self._client.add_callbacks(self._client_callbacks)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to hass removal."""
        self._client.remove_callbacks(self._client_callbacks)
