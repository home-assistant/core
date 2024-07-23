"""Define Guardian-specific utilities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from aioguardian.errors import GuardianError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import LOGGER

if TYPE_CHECKING:
    from . import GuardianEntity

    _GuardianEntityT = TypeVar("_GuardianEntityT", bound=GuardianEntity)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)

SIGNAL_REBOOT_REQUESTED = "guardian_reboot_requested_{0}"

_P = ParamSpec("_P")


@dataclass
class EntityDomainReplacementStrategy:
    """Define an entity replacement."""

    old_domain: str
    old_unique_id: str


@callback
def async_finish_entity_domain_replacements(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entity_replacement_strategies: Iterable[EntityDomainReplacementStrategy],
) -> None:
    """Remove old entities and create a repairs issue with info on their replacement."""
    ent_reg = er.async_get(hass)
    for strategy in entity_replacement_strategies:
        try:
            [registry_entry] = [
                registry_entry
                for registry_entry in er.async_entries_for_config_entry(
                    ent_reg, entry.entry_id
                )
                if registry_entry.domain == strategy.old_domain
                and registry_entry.unique_id == strategy.old_unique_id
            ]
        except ValueError:
            continue

        old_entity_id = registry_entry.entity_id
        LOGGER.info('Removing old entity: "%s"', old_entity_id)
        ent_reg.async_remove(old_entity_id)


@callback
def convert_exceptions_to_homeassistant_error(
    func: Callable[Concatenate[_GuardianEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_GuardianEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate to handle exceptions from the Guardian API."""

    @wraps(func)
    async def wrapper(
        entity: _GuardianEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        """Wrap the provided function."""
        try:
            await func(entity, *args, **kwargs)
        except GuardianError as err:
            raise HomeAssistantError(
                f"Error while calling {func.__name__}: {err}"
            ) from err

    return wrapper
