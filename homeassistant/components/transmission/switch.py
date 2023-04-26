"""Support for setting the Transmission BitTorrent client Turtle Mode."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import transmission_rpc

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TransmissionClient
from .const import DOMAIN


@dataclass
class TransmissionSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[transmission_rpc.Client], bool | None]
    on_fn: Callable[[transmission_rpc.Client], None]
    off_fn: Callable[[transmission_rpc.Client], None]


@dataclass
class TransmissionSwitchEntityDescription(
    SwitchEntityDescription, TransmissionSwitchEntityDescriptionMixin
):
    """Describes Transmission switch entity."""


ENTITY_DESCRIPTIONS = [
    TransmissionSwitchEntityDescription(
        key="Switch",
        name="Switch",
        state_fn=lambda api: api.data.active_torrent_count > 0 if api.data else None,
        on_fn=lambda api: api.start_torrents(),
        off_fn=lambda api: api.stop_torrents(),
    ),
    TransmissionSwitchEntityDescription(
        key="Turtle Mode",
        name="Turtle mode",
        state_fn=lambda api: api.get_alt_speed_enabled(),
        on_fn=lambda api: api.set_alt_speed_enabled(True),
        off_fn=lambda api: api.set_alt_speed_enabled(False),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    client_name = config_entry.data[CONF_NAME]

    dev = [
        TransmissionSwitch(entity_description, tm_client, client_name)
        for entity_description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(dev, True)


class TransmissionSwitch(SwitchEntity):
    """Representation of a Transmission switch."""

    entity_description: TransmissionSwitchEntityDescription

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entity_description: TransmissionSwitchEntityDescription,
        tm_client: TransmissionClient,
        client_name: str,
    ) -> None:
        """Initialize the Transmission switch."""
        self.entity_description = entity_description
        self._tm_client = tm_client
        self._state = STATE_OFF
        self.unsub_update: Callable[[], None] | None = None

        self._attr_unique_id = (
            f"{self._tm_client.api.host}-{client_name} {entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, tm_client.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._tm_client.api.available

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.entity_description.on_fn(self._tm_client.api)
        self._tm_client.api.update()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.entity_description.off_fn(self._tm_client.api)
        self._tm_client.api.update()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass,
            self._tm_client.api.signal_update,
            self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        active = self.entity_description.state_fn(self._tm_client.api)

        if active is None:
            return

        self._state = STATE_ON if active else STATE_OFF
