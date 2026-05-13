"""Provides functionality to interact with infrared devices."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
import logging
from typing import final

from infrared_protocols.commands import Command as InfraredCommand
from propcache.api import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.deprecation import deprecated_class
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

__all__ = [
    "DOMAIN",
    "InfraredEmitterEntity",
    "InfraredEmitterEntityDescription",
    "InfraredEntity",
    "InfraredEntityDescription",
    "InfraredReceivedSignal",
    "InfraredReceiverEntity",
    "InfraredReceiverEntityDescription",
    "async_get_emitters",
    "async_get_receivers",
    "async_send_command",
    "async_subscribe_receiver",
]


class InfraredDeviceClass(StrEnum):
    """Device class for infrared entities."""

    EMITTER = "emitter"
    RECEIVER = "receiver"


_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[
    EntityComponent[InfraredEmitterEntity | InfraredReceiverEntity]
] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the infrared domain."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[
        InfraredEmitterEntity | InfraredReceiverEntity
    ](_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@callback
def async_get_emitters(hass: HomeAssistant) -> list[str]:
    """Get all infrared emitter entity IDs."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    return [
        entity.entity_id
        for entity in component.entities
        if isinstance(entity, InfraredEmitterEntity)
    ]


@callback
def async_get_receivers(hass: HomeAssistant) -> list[str]:
    """Get all infrared receiver entity IDs."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    return [
        entity.entity_id
        for entity in component.entities
        if isinstance(entity, InfraredReceiverEntity)
    ]


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: InfraredCommand,
    context: Context | None = None,
) -> None:
    """Send an IR command to the specified infrared entity.

    Raises:
        HomeAssistantError: If the infrared entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, InfraredEmitterEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


@callback
def async_subscribe_receiver(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    signal_callback: Callable[[InfraredReceivedSignal], None],
) -> CALLBACK_TYPE:
    """Subscribe to IR signals from a specific receiver entity.

    Raises:
        HomeAssistantError: If the receiver entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    except vol.Invalid as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id_or_uuid},
        ) from err

    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, InfraredReceiverEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity.async_subscribe_received_signal(signal_callback)


@dataclass(frozen=True, slots=True)
class InfraredReceivedSignal:
    """Represents a received IR signal."""

    timings: list[int]
    modulation: int | None = None


class InfraredEmitterEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared emitter entities."""


class InfraredEmitterEntity(RestoreEntity):
    """Base class for infrared emitter entities."""

    entity_description: InfraredEmitterEntityDescription
    _attr_device_class: InfraredDeviceClass = InfraredDeviceClass.EMITTER
    _attr_should_poll = False
    _attr_state: None = None

    __last_command_sent: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_command_sent

    @final
    async def async_send_command_internal(self, command: InfraredCommand) -> None:
        """Send an IR command and update state.

        Should not be overridden, handles setting last sent timestamp.
        """
        await self.async_send_command(command)
        self.__last_command_sent = dt_util.utcnow().isoformat(timespec="milliseconds")
        self.async_write_ha_state()

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the infrared entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__last_command_sent = state.state

    @abstractmethod
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Args:
            command: The IR command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """


class InfraredReceiverEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared receiver entities."""


class InfraredReceiverEntity(RestoreEntity):
    """Base class for infrared receiver entities."""

    entity_description: InfraredReceiverEntityDescription
    _attr_device_class: InfraredDeviceClass = InfraredDeviceClass.RECEIVER
    _attr_should_poll = False
    _attr_state: None = None

    __last_signal_received: str | None = None

    @cached_property
    def __signal_callbacks(self) -> set[Callable[[InfraredReceivedSignal], None]]:
        """Subscriber callback set, lazily initialized on first access."""
        return set()

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_signal_received

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the infrared entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
        ):
            self.__last_signal_received = state.state

    @final
    def _handle_received_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal.

        Should not be overridden. To be called by platform implementations when a
        signal is received.
        """
        self.__last_signal_received = dt_util.utcnow().isoformat(
            timespec="milliseconds"
        )
        self.async_write_ha_state()
        for signal_callback in tuple(self.__signal_callbacks):
            try:
                signal_callback(signal)
            except Exception:
                _LOGGER.exception("Error in signal callback for %s", self.entity_id)

    @callback
    def async_subscribe_received_signal(
        self,
        signal_callback: Callable[[InfraredReceivedSignal], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to received IR signals.

        Returns a callable to unsubscribe.
        """
        callbacks = self.__signal_callbacks
        callbacks.add(signal_callback)

        @callback
        def remove_callback() -> None:
            callbacks.discard(signal_callback)

        return remove_callback


@deprecated_class(
    "homeassistant.components.infrared.InfraredEmitterEntityDescription",
    breaks_in_ha_version="2027.6",
)
class InfraredEntityDescription(InfraredEmitterEntityDescription):
    """Deprecated alias for InfraredEmitterEntityDescription."""


@deprecated_class(
    "homeassistant.components.infrared.InfraredEmitterEntity",
    breaks_in_ha_version="2027.6",
)
class InfraredEntity(InfraredEmitterEntity):
    """Deprecated alias for InfraredEmitterEntity."""
