"""Update entities for blueprints."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components import automation, script
from homeassistant.components.blueprint import importer, models
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import CONF_SOURCE_URL, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import event as event_helper
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN as BLUEPRINT_DOMAIN
from .errors import BlueprintException

_LOGGER = logging.getLogger(__name__)

_LATEST_VERSION_PLACEHOLDER: Final = "remote"
DATA_UPDATE_MANAGER: Final = "update_manager"


@dataclass(slots=True)
class BlueprintUsage:
    """Details about a blueprint currently in use."""

    domain: str
    path: str
    domain_blueprints: models.DomainBlueprints
    blueprint: models.Blueprint
    entities: list[str]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the blueprint update platform."""
    data = hass.data.setdefault(BLUEPRINT_DOMAIN, {})

    if (manager := data.get(DATA_UPDATE_MANAGER)) is None:
        manager = BlueprintUpdateManager(hass, async_add_entities)
        data[DATA_UPDATE_MANAGER] = manager
        await manager.async_start()
        return

    manager.replace_add_entities(async_add_entities)
    await manager.async_recreate_entities()


class BlueprintUpdateManager:
    """Manage blueprint update entities based on blueprint usage."""

    def __init__(
        self, hass: HomeAssistant, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._async_add_entities = async_add_entities
        self._entities: dict[tuple[str, str], BlueprintUpdateEntity] = {}
        self._lock = asyncio.Lock()
        self._refresh_cancel: CALLBACK_TYPE | None = None
        self._unsubscribers: list[CALLBACK_TYPE] = []
        self._started = False

    async def async_start(self) -> None:
        """Start tracking blueprint usage."""
        if self._started:
            return
        self._started = True

        self._register_listeners()
        await self.async_refresh_entities()

    def replace_add_entities(self, async_add_entities: AddEntitiesCallback) -> None:
        """Update the callback used to register entities."""
        self._async_add_entities = async_add_entities

    async def async_recreate_entities(self) -> None:
        """Recreate entities after the platform has been reloaded."""
        async with self._lock:
            entities = list(self._entities.values())
            self._entities.clear()

        for entity in entities:
            await entity.async_remove()

        await self.async_refresh_entities()

    def _register_listeners(self) -> None:
        """Register listeners for detecting blueprint usage changes."""

        self._unsubscribers.append(
            event_helper.async_track_state_added_domain(
                self.hass, (automation.DOMAIN, script.DOMAIN), self._handle_state_change
            )
        )
        self._unsubscribers.append(
            event_helper.async_track_state_removed_domain(
                self.hass, (automation.DOMAIN, script.DOMAIN), self._handle_state_change
            )
        )
        self._unsubscribers.append(
            self.hass.bus.async_listen(
                automation.EVENT_AUTOMATION_RELOADED, self._handle_event
            )
        )
        self._unsubscribers.append(
            self.hass.bus.async_listen(
                script.EVENT_SCRIPT_RELOADED, self._handle_event
            )
        )
        self._unsubscribers.append(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._handle_started
            )
        )

    async def async_refresh_entities(self) -> None:
        """Refresh update entities based on current blueprint usage."""
        async with self._lock:
            usage_map = await self._async_collect_in_use_blueprints()

            current_keys = set(self._entities)
            new_keys = set(usage_map)

            for key in current_keys - new_keys:
                entity = self._entities.pop(key)
                await entity.async_remove()

            new_entities: list[BlueprintUpdateEntity] = []

            for key in new_keys - current_keys:
                usage = usage_map[key]
                entity = BlueprintUpdateEntity(self, usage)
                self._entities[key] = entity
                new_entities.append(entity)

            for key in new_keys & current_keys:
                self._entities[key].update_usage(usage_map[key])
                self._entities[key].async_write_ha_state()

            if new_entities:
                self._async_add_entities(new_entities)

    def async_schedule_refresh(self) -> None:
        """Schedule an asynchronous refresh."""
        if self._refresh_cancel is not None:
            return

        self._refresh_cancel = event_helper.async_call_later(
            self.hass, 0, self._handle_scheduled_refresh
        )

    @callback
    def _handle_scheduled_refresh(self, _now: Any) -> None:
        """Run a scheduled refresh task."""
        self._refresh_cancel = None
        self.hass.async_create_task(self.async_refresh_entities())

    @callback
    def _handle_state_change(self, _event: Event) -> None:
        """Handle entity additions or removals."""
        self.async_schedule_refresh()

    @callback
    def _handle_event(self, _event: Event) -> None:
        """Handle domain-specific reload events."""
        self.async_schedule_refresh()

    @callback
    def _handle_started(self, _event: Event) -> None:
        """Refresh once Home Assistant has started."""
        self.async_schedule_refresh()

    async def _async_collect_in_use_blueprints(self) -> dict[tuple[str, str], BlueprintUsage]:
        """Collect blueprint usage information for automations and scripts."""

        usage_keys: set[tuple[str, str]] = set()

        if automation.DATA_COMPONENT in self.hass.data:
            component = self.hass.data[automation.DATA_COMPONENT]
            for automation_entity in list(component.entities):
                if (path := getattr(automation_entity, "referenced_blueprint", None)):
                    usage_keys.add((automation.DOMAIN, path))

        if script.DOMAIN in self.hass.data:
            component = self.hass.data[script.DOMAIN]
            for script_entity in list(component.entities):
                if (path := getattr(script_entity, "referenced_blueprint", None)):
                    usage_keys.add((script.DOMAIN, path))

        domain_blueprints_map = self.hass.data.get(BLUEPRINT_DOMAIN, {})
        usage_map: dict[tuple[str, str], BlueprintUsage] = {}

        for domain, path in usage_keys:
            domain_blueprints: models.DomainBlueprints | None = domain_blueprints_map.get(
                domain
            )

            if domain_blueprints is None:
                continue

            if not domain_blueprints.blueprint_in_use(path):
                continue

            try:
                blueprint = await domain_blueprints.async_get_blueprint(path)
            except BlueprintException:
                continue

            if domain == automation.DOMAIN:
                entities = automation.automations_with_blueprint(self.hass, path)
            elif domain == script.DOMAIN:
                entities = script.scripts_with_blueprint(self.hass, path)
            else:
                entities = []

            usage_map[(domain, path)] = BlueprintUsage(
                domain=domain,
                path=path,
                domain_blueprints=domain_blueprints,
                blueprint=blueprint,
                entities=entities,
            )

        return usage_map


class BlueprintUpdateEntity(UpdateEntity):
    """Define a blueprint update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, manager: BlueprintUpdateManager, usage: BlueprintUsage) -> None:
        """Initialize the update entity."""
        self._manager = manager
        self._domain = usage.domain
        self._path = usage.path
        self._domain_blueprints = usage.domain_blueprints
        self._blueprint = usage.blueprint
        self._entities_in_use = usage.entities
        self._source_url = usage.blueprint.metadata.get(CONF_SOURCE_URL)
        self._attr_unique_id = f"{self._domain}:{self._path}"
        self._attr_in_progress: bool | None = False

        self.update_usage(usage)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "blueprint_path": self._path,
            "domain": self._domain,
            "entities": sorted(self._entities_in_use),
            "source_url": self._source_url,
        }

    def update_usage(self, usage: BlueprintUsage) -> None:
        """Update the entity with latest usage information."""
        self._domain_blueprints = usage.domain_blueprints
        self._blueprint = usage.blueprint
        self._entities_in_use = usage.entities
        self._source_url = usage.blueprint.metadata.get(CONF_SOURCE_URL)

        self._attr_name = usage.blueprint.name
        self._attr_release_summary = usage.blueprint.metadata.get("description")
        self._attr_installed_version = usage.blueprint.metadata.get("version")
        self._attr_release_url = self._source_url
        self._attr_available = self._source_url is not None
        self._attr_latest_version = (
            _LATEST_VERSION_PLACEHOLDER
            if self._source_url is not None
            else self._attr_installed_version
        )

    async def async_install(self, version: str | None, backup: bool) -> None:
        """Install (refresh) the blueprint from its source."""
        if self._source_url is None:
            raise HomeAssistantError("Blueprint does not define a source URL")

        self._attr_in_progress = True
        self.async_write_ha_state()
        usage: BlueprintUsage | None = None

        try:
            imported = await importer.fetch_blueprint_from_url(
                self.hass, self._source_url
            )
            blueprint = imported.blueprint

            if blueprint.domain != self._domain:
                raise HomeAssistantError(
                    "Downloaded blueprint domain does not match the existing blueprint"
                )

            await self._domain_blueprints.async_add_blueprint(
                blueprint, self._path, allow_override=True
            )

            usage = BlueprintUsage(
                domain=self._domain,
                path=self._path,
                domain_blueprints=self._domain_blueprints,
                blueprint=blueprint,
                entities=self._entities_in_use,
            )

        except HomeAssistantError:
            raise
        except Exception as err:  # noqa: BLE001 - Provide context for unexpected errors
            raise HomeAssistantError("Failed to update blueprint from source") from err
        finally:
            self._attr_in_progress = False

            if usage is not None:
                self.update_usage(usage)

            self.async_write_ha_state()

        self._manager.async_schedule_refresh()
