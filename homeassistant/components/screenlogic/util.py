"""Utility functions for the ScreenLogic integration."""
import logging

from screenlogicpy.const.data import SHARED_VALUES

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def generate_unique_id(
    device: str | int, group: str | int | None, data_key: str | int
) -> str:
    """Generate new unique_id for a screenlogic entity from specified parameters."""
    if data_key in SHARED_VALUES and device is not None:
        if group is not None and (isinstance(group, int) or group.isdigit()):
            return f"{device}_{group}_{data_key}"
        return f"{device}_{data_key}"
    return str(data_key)


def cleanup_excluded_entity(
    coordinator: ScreenlogicDataUpdateCoordinator,
    platform_domain: str,
    entity_key: str,
) -> None:
    """Remove excluded entity if it exists."""
    assert coordinator.config_entry
    entity_registry = er.async_get(coordinator.hass)
    unique_id = f"{coordinator.config_entry.unique_id}_{entity_key}"
    if entity_id := entity_registry.async_get_entity_id(
        platform_domain, SL_DOMAIN, unique_id
    ):
        _LOGGER.debug(
            "Removing existing entity '%s' per data inclusion rule", entity_id
        )
        entity_registry.async_remove(entity_id)
