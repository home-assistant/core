"""Resolve which accessory type a climate entity uses.

Existing capable entities keep the Thermostat and are tracked as repair
candidates offering a one click HeaterCooler migration; entities that
have never been bridged get the HeaterCooler automatically when capable.
"""

from collections.abc import Collection
from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir

from .accessories import (
    climate_controls_target_humidity,
    climate_supports_heater_cooler,
)
from .aidmanager import AccessoryAidStorage
from .const import DOMAIN, ISSUE_HEATER_COOLER_CANDIDATE, TYPE_HEATER_COOLER


def async_climate_type_issue_id(entry_id: str, entity_id: str) -> str:
    """Return the repair issue id for a HeaterCooler candidate."""
    return f"{ISSUE_HEATER_COOLER_CANDIDATE}_{entry_id}_{entity_id}"


@callback
def async_delete_climate_type_issues(
    hass: HomeAssistant, entry_id: str, keep: Collection[str] = ()
) -> None:
    """Delete an entry's HeaterCooler candidate issues except the kept ids."""
    issue_prefix = f"{ISSUE_HEATER_COOLER_CANDIDATE}_{entry_id}_"
    issue_reg = ir.async_get(hass)
    for domain, issue_id in list(issue_reg.issues):
        if (
            domain == DOMAIN
            and issue_id.startswith(issue_prefix)
            and issue_id not in keep
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


class ClimateTypeResolver:
    """Decide the accessory type for climate entities.

    Owns the repair candidacy bookkeeping so the bridge only has to ask
    for a type and sync the issues after accessories change.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, bridge_name: str) -> None:
        """Initialize the resolver for one config entry."""
        self._hass = hass
        self._entry_id = entry_id
        self._bridge_name = bridge_name
        # Existing climate entities that would route to the HeaterCooler but
        # stay on the Thermostat until the user opts in through a repair,
        # mapped to their friendly name for the issue text.
        self._candidates: dict[str, str] = {}

    @callback
    def async_resolve(
        self,
        aid_storage: AccessoryAidStorage,
        state: State,
        conf: dict[str, Any],
        *,
        allow_auto: bool,
    ) -> str | None:
        """Resolve which accessory a climate entity uses into conf.

        An explicit type in the entity config always wins, even for
        entities with a humidity setpoint, and updates the stored routing,
        so switching back to automatic keeps the accessory the entity
        already uses. In bridge mode an entity that has never been
        bridged gets the HeaterCooler when capable. Anything else keeps
        the Thermostat and is tracked as a repair candidate.

        Returns the accessory type the caller must record with
        async_set_accessory_type once the accessory is successfully
        created, so a failed creation is not sticky across restarts.
        """
        if state.domain != CLIMATE_DOMAIN:
            return None
        entity_id = state.entity_id
        # Candidacy is re-evaluated on every resolve
        self._candidates.pop(entity_id, None)
        if climate_type := conf.get(CONF_TYPE):
            aid_storage.async_set_accessory_type(entity_id, climate_type)
            return None
        if aid_storage.get_accessory_type(entity_id) == TYPE_HEATER_COOLER:
            if not climate_controls_target_humidity(state):
                conf[CONF_TYPE] = TYPE_HEATER_COOLER
                return None
            # A humidity setpoint gained since the choice was stored cannot
            # be represented by the HeaterCooler, so the routing is dropped.
            aid_storage.async_set_accessory_type(entity_id, None)
        if not climate_supports_heater_cooler(state):
            return None
        if allow_auto and not aid_storage.entity_is_allocated(entity_id):
            conf[CONF_TYPE] = TYPE_HEATER_COOLER
            return TYPE_HEATER_COOLER
        self._candidates[entity_id] = state.name
        return None

    @callback
    def async_entity_removed(self, entity_id: str) -> None:
        """End the repair candidacy of a removed accessory.

        The resolver re-establishes it when the entity is recreated.
        """
        self._candidates.pop(entity_id, None)

    @callback
    def async_reset_candidates(self) -> None:
        """Forget all candidates before the accessories are rebuilt."""
        self._candidates.clear()

    @callback
    def async_update_issues(self) -> None:
        """Sync the HeaterCooler migration repairs with the current candidates.

        YAML configured bridges never get issues; their documented path is the
        ``type`` option in ``entity_config``.
        """
        entry = self._hass.config_entries.async_get_entry(self._entry_id)
        if entry is None or entry.source == SOURCE_IMPORT:
            async_delete_climate_type_issues(self._hass, self._entry_id)
            return
        keep = {
            async_climate_type_issue_id(self._entry_id, entity_id)
            for entity_id in self._candidates
        }
        async_delete_climate_type_issues(self._hass, self._entry_id, keep=keep)
        for entity_id, name in self._candidates.items():
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                async_climate_type_issue_id(self._entry_id, entity_id),
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_HEATER_COOLER_CANDIDATE,
                translation_placeholders={
                    "entity": name,
                    "entity_id": entity_id,
                    "bridge": self._bridge_name,
                },
                data={"entry_id": self._entry_id, "entity_id": entity_id},
            )
