"""Switch platform for Hyperion."""

from typing import Any, Callable, Dict, Optional

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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import get_hyperion_unique_id, listen_for_instance_updates
from .const import (
    CONF_INSTANCE_CLIENTS,
    DOMAIN,
    NAME_SUFFIX_HYPERION_COMPONENT_SWITCH,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_COMPONENT_SWITCH_BASE,
)

COMPONENT_TO_SWITCH_TYPE = {
    component: f"{TYPE_HYPERION_COMPONENT_SWITCH_BASE}_{component.lower()}"
    for component in [
        KEY_COMPONENTID_ALL,
        KEY_COMPONENTID_SMOOTHING,
        KEY_COMPONENTID_BLACKBORDER,
        KEY_COMPONENTID_FORWARDER,
        KEY_COMPONENTID_BOBLIGHTSERVER,
        KEY_COMPONENTID_GRABBER,
        KEY_COMPONENTID_LEDDEVICE,
        KEY_COMPONENTID_V4L,
    ]
}


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up a Hyperion platform from config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    server_id = config_entry.unique_id

    def instance_add(instance_num: int, instance_name: str) -> None:
        """Add entities for a new Hyperion instance."""
        assert server_id
        switches = []
        for component in COMPONENT_TO_SWITCH_TYPE:
            switches.append(
                HyperionComponentSwitch(
                    get_hyperion_unique_id(
                        server_id, instance_num, COMPONENT_TO_SWITCH_TYPE[component]
                    ),
                    f"{instance_name} {NAME_SUFFIX_HYPERION_COMPONENT_SWITCH} {component.capitalize()}",
                    component,
                    entry_data[CONF_INSTANCE_CLIENTS][instance_num],
                ),
            )
        async_add_entities(switches)

    def instance_remove(instance_num: int) -> None:
        """Remove entities for an old Hyperion instance."""
        assert server_id
        for component in COMPONENT_TO_SWITCH_TYPE:
            async_dispatcher_send(
                hass,
                SIGNAL_ENTITY_REMOVE.format(
                    get_hyperion_unique_id(
                        server_id, instance_num, COMPONENT_TO_SWITCH_TYPE[component]
                    )
                ),
            )

    listen_for_instance_updates(hass, config_entry, instance_add, instance_remove)
    return True


class HyperionComponentSwitch(SwitchEntity):
    """ComponentBinarySwitch switch class."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        component_name: str,
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the switch."""
        self._unique_id = unique_id
        self._name = name
        self._component_name = component_name
        self._client = hyperion_client
        self._client_callbacks = {
            f"{KEY_COMPONENTS}-{KEY_UPDATE}": self._update_components
        }

    @property
    def should_poll(self) -> bool:
        """Return whether or not this entity should be polled."""
        return False

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
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        for component in self._client.components:
            if component[KEY_NAME] == self._component_name:
                return bool(component.setdefault(KEY_ENABLED, False))
        return False

    @property
    def available(self) -> bool:
        """Return server availability."""
        return bool(self._client.has_loaded_state)

    async def _async_send_set_component(self, value: bool) -> None:
        await self._client.async_send_set_component(
            **{
                KEY_COMPONENTSTATE: {
                    KEY_COMPONENT: self._component_name,
                    KEY_STATE: value,
                }
            }
        )

    # pylint: disable=unused-argument
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_send_set_component(True)

    # pylint: disable=unused-argument
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_send_set_component(False)

    def _update_components(self, _: Optional[Dict[str, Any]] = None) -> None:
        """Update Hyperion components."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        assert self.hass
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self._unique_id),
                self.async_remove,
            )
        )

        self._client.add_callbacks(self._client_callbacks)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to hass removal."""
        self._client.remove_callbacks(self._client_callbacks)
