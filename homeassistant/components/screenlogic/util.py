"""Utility functions for the ScreenLogic integration."""
import logging

from screenlogicpy.const.data import SHARED_VALUES

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN as SL_DOMAIN, SL_UNIT_TO_HA_UNIT, ScreenLogicDataPath
from .coordinator import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def generate_unique_id(*args: str | int | None) -> str:
    """Generate new unique_id for a screenlogic entity from specified parameters."""
    _LOGGER.debug("gen_uid called with %s", args)
    if len(args) == 3:
        if args[2] in SHARED_VALUES:
            if args[1] is not None and (isinstance(args[1], int) or args[1].isdigit()):
                return f"{args[0]}_{args[1]}_{args[2]}"
            return f"{args[0]}_{args[2]}"
        return f"{args[2]}"
    return f"{args[1]}"


def get_ha_unit(sl_unit) -> str:
    """Return equivalent Home Assistant unit of measurement if exists."""
    if (ha_unit := SL_UNIT_TO_HA_UNIT.get(sl_unit)) is not None:
        return ha_unit
    return sl_unit


def cleanup_excluded_entity(
    coordinator: ScreenlogicDataUpdateCoordinator,
    platform_domain: str,
    data_path: ScreenLogicDataPath,
) -> None:
    """Remove excluded entity if it exists."""
    assert coordinator.config_entry
    entity_registry = er.async_get(coordinator.hass)
    unique_id = f"{coordinator.config_entry.unique_id}_{generate_unique_id(*data_path)}"
    if entity_id := entity_registry.async_get_entity_id(
        platform_domain, SL_DOMAIN, unique_id
    ):
        _LOGGER.debug(
            "Removing existing entity '%s' per data inclusion rule", entity_id
        )
        entity_registry.async_remove(entity_id)
