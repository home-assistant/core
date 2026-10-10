"""Support for AdGuard Home switches."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from adguardhome import AdGuardHome, AdGuardHomeError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    AdGuardConfigEntry,
    AdGuardHomeState,
    AdGuardHomeStateCoordinator,
)
from .entity import AdGuardHomeEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeSwitchEntityDescription(SwitchEntityDescription):
    """Describes AdGuard Home switch entity."""

    is_on_fn: Callable[[AdGuardHomeState], bool]
    turn_on_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]
    turn_off_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]


SWITCHES: tuple[AdGuardHomeSwitchEntityDescription, ...] = (
    AdGuardHomeSwitchEntityDescription(
        key="protection",
        translation_key="protection",
        is_on_fn=lambda data: data.status.protection_enabled,
        turn_on_fn=lambda adguard: adguard.enable_protection,
        turn_off_fn=lambda adguard: adguard.disable_protection,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="parental",
        translation_key="parental",
        is_on_fn=lambda data: data.parental,
        turn_on_fn=lambda adguard: adguard.parental.enable,
        turn_off_fn=lambda adguard: adguard.parental.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safesearch",
        translation_key="safe_search",
        is_on_fn=lambda data: data.safe_search.enabled,
        turn_on_fn=lambda adguard: adguard.safesearch.enable,
        turn_off_fn=lambda adguard: adguard.safesearch.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safebrowsing",
        translation_key="safe_browsing",
        is_on_fn=lambda data: data.safe_browsing,
        turn_on_fn=lambda adguard: adguard.safebrowsing.enable,
        turn_off_fn=lambda adguard: adguard.safebrowsing.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="filtering",
        translation_key="filtering",
        is_on_fn=lambda data: data.filtering.enabled,
        turn_on_fn=lambda adguard: adguard.filtering.enable,
        turn_off_fn=lambda adguard: adguard.filtering.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="querylog",
        translation_key="query_log",
        is_on_fn=lambda data: data.query_log.enabled,
        turn_on_fn=lambda adguard: adguard.querylog.enable,
        turn_off_fn=lambda adguard: adguard.querylog.disable,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home switch based on a config entry."""
    coordinator = entry.runtime_data.state

    async_add_entities(
        AdGuardHomeSwitch(coordinator, description) for description in SWITCHES
    )


class AdGuardHomeSwitch(AdGuardHomeEntity[AdGuardHomeStateCoordinator], SwitchEntity):
    """Defines a AdGuard Home switch."""

    entity_description: AdGuardHomeSwitchEntityDescription

    def __init__(
        self,
        coordinator: AdGuardHomeStateCoordinator,
        description: AdGuardHomeSwitchEntityDescription,
    ) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.entity_description = description
        # Legacy format, kept as migrating existing unique IDs is not worth the risk
        self._attr_unique_id = "_".join(  # pylint: disable=home-assistant-entity-unique-id-redundant-domain,home-assistant-entity-unique-id-redundant-platform
            [
                DOMAIN,
                entry.data[CONF_HOST],
                str(entry.data[CONF_PORT]),
                "switch",
                description.key,
            ]
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.client)()
        except AdGuardHomeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_while_turn_off",
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.client)()
        except AdGuardHomeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_while_turn_on",
            ) from err

        await self.coordinator.async_request_refresh()

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)
