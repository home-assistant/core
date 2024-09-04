"""Support for Roku selects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from rokuecp import Roku
from rokuecp.models import Device as RokuDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity
from .helpers import format_channel_name, roku_exception_handler


def _get_application_name(device: RokuDevice) -> str | None:
    if device.app is None or device.app.name is None:
        return None

    if device.app.name == "Roku":
        return "Home"

    return device.app.name


def _get_applications(device: RokuDevice) -> list[str]:
    return ["Home", *sorted(app.name for app in device.apps if app.name is not None)]


def _get_channel_name(device: RokuDevice) -> str | None:
    if device.channel is None:
        return None

    return format_channel_name(device.channel.number, device.channel.name)


def _get_channels(device: RokuDevice) -> list[str]:
    return sorted(
        format_channel_name(channel.number, channel.name) for channel in device.channels
    )


async def _launch_application(device: RokuDevice, roku: Roku, value: str) -> None:
    if value == "Home":
        await roku.remote("home")

    appl = next(
        (app for app in device.apps if value == app.name),
        None,
    )

    if appl is not None and appl.app_id is not None:
        await roku.launch(appl.app_id)


async def _tune_channel(device: RokuDevice, roku: Roku, value: str) -> None:
    _channel = next(
        (
            channel
            for channel in device.channels
            if (
                channel.name is not None
                and value == format_channel_name(channel.number, channel.name)
            )
            or value == channel.number
        ),
        None,
    )

    if _channel is not None:
        await roku.tune(_channel.number)


@dataclass(frozen=True, kw_only=True)
class RokuSelectEntityDescription(SelectEntityDescription):
    """Describes Roku select entity."""

    options_fn: Callable[[RokuDevice], list[str]]
    value_fn: Callable[[RokuDevice], str | None]
    set_fn: Callable[[RokuDevice, Roku, str], Awaitable[None]]


ENTITIES: tuple[RokuSelectEntityDescription, ...] = (
    RokuSelectEntityDescription(
        key="application",
        translation_key="application",
        set_fn=_launch_application,
        value_fn=_get_application_name,
        options_fn=_get_applications,
        entity_registry_enabled_default=False,
    ),
)

CHANNEL_ENTITY = RokuSelectEntityDescription(
    key="channel",
    translation_key="channel",
    set_fn=_tune_channel,
    value_fn=_get_channel_name,
    options_fn=_get_channels,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roku select based on a config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device: RokuDevice = coordinator.data

    entities: list[RokuSelectEntity] = [
        RokuSelectEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in ENTITIES
    ]

    if len(device.channels) > 0:
        entities.append(
            RokuSelectEntity(
                coordinator=coordinator,
                description=CHANNEL_ENTITY,
            )
        )

    async_add_entities(entities)


class RokuSelectEntity(RokuEntity, SelectEntity):
    """Defines a Roku select entity."""

    entity_description: RokuSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options_fn(self.coordinator.data)

    @roku_exception_handler()
    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.entity_description.set_fn(
            self.coordinator.data,
            self.coordinator.roku,
            option,
        )
        await self.coordinator.async_request_refresh()
