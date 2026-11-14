"""Global Visonic Data Types."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CONF_PANEL_NUMBER, DOMAIN
from .visonic_types import AlarmPanelStatus

if TYPE_CHECKING:
    # Imports used purely to define a type for type checking:
    #    This ensures no cyclic imports
    from .coordinator import VisonicCoordinator
    from .visonic_entity_types import PanelState


###################################################################################################
# This set of classes define the data that is saved in the HASS config entry and run_time data
###################################################################################################
@dataclass
class VisonicPanelData:
    """The class that is saved as Home Assistant runtime data (for clients)."""

    # Coordinator
    coordinator: VisonicCoordinator
    # panel identifier
    panel_id: int | str


type VisonicConfigEntry = ConfigEntry[VisonicPanelData]


def get_panels_by_config_state(
    hass: HomeAssistant,
    state_set: set[ConfigEntryState] | None = None,
    invert: bool = False,
) -> list[int]:
    """Get all config entries registered under the visonic domain, that match the parameter patterns."""
    retval: list[int] = []
    visonic_entries = hass.config_entries.async_entries(DOMAIN)
    for entry in visonic_entries:
        if CONF_PANEL_NUMBER in entry.data:
            panel_id: int = int(str(entry.data.get(CONF_PANEL_NUMBER)))
            if (
                state_set is None
                or (not invert and entry.state in state_set)
                or (invert and entry.state not in state_set)
            ):
                retval.append(panel_id)
    return retval


# Data class that the coordinator uses to manage the data passed to the entities
@dataclass(frozen=True, slots=True)
class VisonicCoordinatorData:
    """Coordinator data for passing to entities. Make it frozen i.e. immutable."""

    # This is the data that is created as part of the coordinator data capture activities and used by all entities

    connected: bool = False  # Is the lower level connected to the panel
    ispowermaster: bool = False  # Is the panel confirmed as a powermaster
    mode: str = ""  # A string shown as an attribute to tell the user the status of the connection
    achieved_powerlink: bool = False
    disconnection_count: int = 0
    model: str | None = None  # The reported panel model
    statusdict: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    panelstate: PanelState | None = (
        None  # Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    )
    armcode: AlarmPanelStatus = AlarmPanelStatus.UNKNOWN
    siren_active: bool = False

    def _convert_recursive(self, convert_to_name: bool, obj: Any) -> Any:
        """Recursively convert Mappings to dicts and sets to lists."""
        if obj is None:
            return None
        if convert_to_name and isinstance(obj, Enum):
            return obj.name.capitalize()
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Mapping):
            mapping_obj = cast(Mapping[object, object], obj)
            return {
                k: self._convert_recursive(convert_to_name, v)
                for k, v in mapping_obj.items()
            }
        if isinstance(obj, (set, list, tuple)):
            iterable_obj = cast(Iterable[object], obj)
            return [self._convert_recursive(convert_to_name, v) for v in iterable_obj]
        return obj

    def as_dict(self, convert_to_name: bool = False) -> dict[str, Any]:
        """Return a fully mutable dictionary representation."""
        return {
            f.name: self._convert_recursive(convert_to_name, getattr(self, f.name))
            for f in fields(self)
        }
