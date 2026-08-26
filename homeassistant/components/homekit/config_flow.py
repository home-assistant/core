"""Config flow for HomeKit integration."""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from operator import itemgetter
import random
import re
import string
from typing import Any, Final, TypedDict, override

import voluptuous as vol

from homeassistant.components import device_automation
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)
from homeassistant.loader import async_get_integrations

from .accessories import get_accessory_type
from .const import (
    CONF_ENTITY_CONFIG,
    CONF_EXCLUDE_ACCESSORY_MODE,
    CONF_EXCLUDE_TARGETS,
    CONF_FILTER,
    CONF_HOMEKIT_MODE,
    CONF_INCLUDE_TARGETS,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    DEFAULT_CONFIG_FLOW_PORT,
    DEFAULT_HOMEKIT_MODE,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODE_BRIDGE,
    HOMEKIT_MODES,
    SHORT_BRIDGE_NAME,
    TYPE_HEATER_COOLER,
    TYPE_THERMOSTAT,
    VIDEO_CODEC_COPY,
)
from .models import HomeKitEntryData
from .target import (
    TargetEntityFilter,
    async_is_bridge_target_entity,
    async_target_entity_ids_by_type,
    should_include_entity,
)
from .util import async_find_next_available_port, state_needs_accessory_mode

CONF_CAMERA_AUDIO = "camera_audio"
CONF_CAMERA_COPY = "camera_copy"

CLIMATE_TYPE_AUTOMATIC = "automatic"
# Display names for the accessory classes a climate entity can use
CLIMATE_ACCESSORY_NAMES = {
    "Thermostat": "Thermostat",
    "HeaterCooler": "Heater Cooler",
}

DOMAINS_NEED_ACCESSORY_MODE = {
    CAMERA_DOMAIN,
    LOCK_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    REMOTE_DOMAIN,
}
NEVER_BRIDGED_DOMAINS = {CAMERA_DOMAIN}

CAMERA_ENTITY_PREFIX = f"{CAMERA_DOMAIN}."

SUPPORTED_DOMAINS = [
    "alarm_control_panel",
    "automation",
    "binary_sensor",
    "button",
    CAMERA_DOMAIN,
    "climate",
    "cover",
    "demo",
    "device_tracker",
    "fan",
    "humidifier",
    "input_boolean",
    "input_button",
    "input_select",
    "light",
    "lock",
    MEDIA_PLAYER_DOMAIN,
    "person",
    REMOTE_DOMAIN,
    "scene",
    "script",
    "select",
    "sensor",
    "switch",
    "vacuum",
    "lawn_mower",
    "water_heater",
    VALVE_DOMAIN,
]

DEFAULT_DOMAINS = [
    "alarm_control_panel",
    "climate",
    CAMERA_DOMAIN,
    "cover",
    "humidifier",
    "fan",
    "light",
    "lock",
    MEDIA_PLAYER_DOMAIN,
    REMOTE_DOMAIN,
    "switch",
    "vacuum",
    "lawn_mower",
    "water_heater",
]

CONF_INCLUDE_DOMAINS: Final = "include_domains"
CONF_INCLUDE_ENTITIES: Final = "include_entities"
CONF_EXCLUDE_DOMAINS: Final = "exclude_domains"
CONF_EXCLUDE_ENTITIES: Final = "exclude_entities"


class EntityFilterDict(TypedDict, total=False):
    """Entity filter dict."""

    include_domains: list[str]
    include_entities: list[str]
    exclude_domains: list[str]
    exclude_entities: list[str]
    include_targets: dict[str, list[str]]
    exclude_targets: dict[str, list[str]]


def _make_entity_filter(
    include_domains: list[str] | None = None,
    include_entities: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    exclude_entities: list[str] | None = None,
    include_targets: dict[str, list[str]] | None = None,
    exclude_targets: dict[str, list[str]] | None = None,
) -> EntityFilterDict:
    """Create a filter dict."""
    entity_filter = EntityFilterDict(
        include_domains=include_domains or [],
        include_entities=include_entities or [],
        exclude_domains=exclude_domains or [],
        exclude_entities=exclude_entities or [],
    )
    if include_targets:
        entity_filter["include_targets"] = include_targets
    if exclude_targets:
        entity_filter["exclude_targets"] = exclude_targets
    return entity_filter


async def _async_domain_names(hass: HomeAssistant, domains: list[str]) -> str:
    """Build a list of integration names from domains."""
    name_to_type_map = await _async_name_to_type_map(hass)
    return ", ".join(
        [name for domain, name in name_to_type_map.items() if domain in domains]
    )


@callback
def _async_build_entities_filter(
    domains: list[str], targets: dict[str, list[str]]
) -> EntityFilterDict:
    """Build an additive entities filter from domains and targets."""
    return _make_entity_filter(include_domains=sorted(domains), include_targets=targets)


def _async_entity_ids_matching_filter(
    hass: HomeAssistant,
    entity_filter: EntityFilterDict,
    domains: Iterable[str],
    entity_config: Mapping[str, dict[str, Any]] | None = None,
    *,
    target_entity_filter: TargetEntityFilter | None = async_is_bridge_target_entity,
) -> list[str]:
    """Return supported entities selected by the shared precedence rules."""
    include_targets = entity_filter.get("include_targets", {})
    exclude_targets = entity_filter.get("exclude_targets", {})
    included_entity_ids = async_target_entity_ids_by_type(
        hass, include_targets, entity_filter=target_entity_filter
    )
    excluded_entity_ids = async_target_entity_ids_by_type(
        hass, exclude_targets, entity_filter=target_entity_filter
    )
    explicitly_included = {
        *entity_filter.get(CONF_INCLUDE_ENTITIES, []),
        *include_targets.get(CONF_ENTITY_ID, []),
    }
    ent_reg = er.async_get(hass)
    entity_config = entity_config or {}
    has_include_rules = bool(
        any(
            entity_filter.get(key)
            for key in (
                CONF_INCLUDE_DOMAINS,
                CONF_INCLUDE_ENTITIES,
                "include_entity_globs",
            )
        )
        or any(include_targets.values())
    )
    return [
        entity_id
        for entity_id in _async_get_matching_entities(
            hass,
            list(domains),
            include_entity_category=True,
            include_hidden=True,
        )
        if (state := hass.states.get(entity_id)) is not None
        and get_accessory_type(
            state, entity_config.get(entity_id, {}), log_errors=False
        )
        is not None
        and (
            entity_id in explicitly_included
            or not _exclude_by_entity_registry(ent_reg, entity_id, False, False)
        )
        and should_include_entity(
            entity_id,
            entity_filter,
            included_entity_ids,
            excluded_entity_ids,
            has_include_rules,
        )
    ]


def _entity_review_schema(entity_ids: list[str]) -> vol.Schema:
    """Return a read-only entity selector for reviewing selected entities."""
    return vol.Schema(
        {
            vol.Optional(CONF_ENTITIES, default=entity_ids): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=entity_ids,
                    multiple=True,
                    read_only=True,
                )
            )
        }
    )


def _async_entities_in_domain(entities: Iterable[str], domain: str) -> list[str]:
    return [
        entity_id for entity_id in entities if split_entity_id(entity_id)[0] == domain
    ]


async def _async_name_to_type_map(hass: HomeAssistant) -> dict[str, str]:
    """Create a mapping of types of devices/entities HomeKit can support."""
    integrations = await async_get_integrations(hass, SUPPORTED_DOMAINS)
    return {
        domain: integration_or_exception.name
        if (integration_or_exception := integrations[domain])
        and not isinstance(integration_or_exception, Exception)
        else domain
        for domain in SUPPORTED_DOMAINS
    }


class HomeKitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeKit."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.hk_data: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose specific domains in bridge mode."""
        if user_input is not None:
            self.hk_data[CONF_DOMAINS] = user_input[CONF_INCLUDE_DOMAINS]
            return await self.async_step_include()

        self.hk_data[CONF_HOMEKIT_MODE] = HOMEKIT_MODE_BRIDGE
        default_domains = (
            [] if self._async_current_entries(include_ignore=False) else DEFAULT_DOMAINS
        )
        name_to_type_map = await _async_name_to_type_map(self.hass)
        return self.async_show_form(
            step_id="user",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_DOMAINS, default=default_domains
                    ): cv.multi_select(name_to_type_map),
                }
            ),
        )

    async def async_step_include(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose targets to include and exclude on the bridge."""
        domains = self.hk_data[CONF_DOMAINS]
        if user_input is not None:
            include_targets: dict[str, list[str]] = user_input.get(
                CONF_INCLUDE_TARGETS, {}
            )
            entity_filter = (
                _async_build_entities_filter(domains, include_targets)
                if include_targets
                else _make_entity_filter(include_domains=domains)
            )
            if exclude_targets := user_input.get(CONF_EXCLUDE_TARGETS, {}):
                entity_filter["exclude_targets"] = exclude_targets
            self.hk_data[CONF_FILTER] = entity_filter
            self.hk_data.pop(CONF_DOMAINS)
            return await self.async_step_review()

        target_selector = selector.TargetSelector(
            selector.TargetSelectorConfig(
                entity={"domain": SUPPORTED_DOMAINS},
                primary_entities_only=True,
            )
        )
        return self.async_show_form(
            step_id="include",
            last_step=False,
            description_placeholders={
                "domains": await _async_domain_names(self.hass, domains)
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_INCLUDE_TARGETS): target_selector,
                    vol.Optional(CONF_EXCLUDE_TARGETS): target_selector,
                }
            ),
        )

    async def async_step_review(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review the selected entities."""
        if user_input is not None:
            return await self.async_step_pairing()

        entity_ids = _async_entity_ids_matching_filter(
            self.hass, self.hk_data[CONF_FILTER], SUPPORTED_DOMAINS
        )
        return self.async_show_form(
            step_id="review",
            last_step=False,
            description_placeholders={"count": str(len(entity_ids))},
            data_schema=_entity_review_schema(entity_ids),
        )

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pairing instructions."""
        hk_data = self.hk_data

        if user_input is not None:
            port = async_find_next_available_port(self.hass, DEFAULT_CONFIG_FLOW_PORT)
            await self._async_add_entries_for_accessory_mode_entities(port)
            hk_data[CONF_PORT] = port
            conf_filter: EntityFilterDict = hk_data[CONF_FILTER]
            conf_filter[CONF_INCLUDE_DOMAINS] = [
                domain
                for domain in conf_filter[CONF_INCLUDE_DOMAINS]
                if domain not in NEVER_BRIDGED_DOMAINS
            ]
            return self.async_create_entry(
                title=f"{hk_data[CONF_NAME]}:{hk_data[CONF_PORT]}",
                data=hk_data,
            )

        hk_data[CONF_NAME] = self._async_available_name(SHORT_BRIDGE_NAME)
        hk_data[CONF_EXCLUDE_ACCESSORY_MODE] = True
        return self.async_show_form(
            step_id="pairing",
            last_step=True,
            description_placeholders={CONF_NAME: hk_data[CONF_NAME]},
        )

    async def _async_add_entries_for_accessory_mode_entities(
        self, last_assigned_port: int
    ) -> None:
        """Generate new flows for entities that need their own instances."""
        conf_filter = self.hk_data[CONF_FILTER]
        accessory_mode_entity_ids = [
            entity_id
            for domain in DOMAINS_NEED_ACCESSORY_MODE
            for entity_id in _async_entity_ids_matching_filter(
                self.hass, conf_filter, [domain]
            )
            if (state := self.hass.states.get(entity_id)) is not None
            and state_needs_accessory_mode(state)
        ]

        exiting_entity_ids_accessory_mode = _async_entity_ids_with_accessory_mode(
            self.hass
        )
        next_port_to_check = last_assigned_port + 1
        for entity_id in accessory_mode_entity_ids:
            if entity_id in exiting_entity_ids_accessory_mode:
                continue
            port = async_find_next_available_port(self.hass, next_port_to_check)
            next_port_to_check = port + 1
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "accessory"},
                    data={CONF_ENTITY_ID: entity_id, CONF_PORT: port},
                )
            )

    async def async_step_accessory(
        self, accessory_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle creation a single accessory in accessory mode."""
        entity_id = accessory_input[CONF_ENTITY_ID]
        port = accessory_input[CONF_PORT]

        state = self.hass.states.get(entity_id)
        assert state is not None
        name = (
            state.attributes.get(EntityStateAttribute.FRIENDLY_NAME) or state.entity_id
        )

        entry_data = {
            CONF_PORT: port,
            CONF_NAME: self._async_available_name(name),
            CONF_HOMEKIT_MODE: HOMEKIT_MODE_ACCESSORY,
            CONF_FILTER: _make_entity_filter(include_entities=[entity_id]),
        }
        if entity_id.startswith(CAMERA_ENTITY_PREFIX):
            entry_data[CONF_ENTITY_CONFIG] = {
                entity_id: {CONF_VIDEO_CODEC: VIDEO_CODEC_COPY}
            }

        return self.async_create_entry(
            title=f"{name}:{entry_data[CONF_PORT]}", data=entry_data
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from yaml."""
        if not self._async_is_unique_name_port(import_data):
            return self.async_abort(reason="port_name_in_use")
        return self.async_create_entry(
            title=f"{import_data[CONF_NAME]}:{import_data[CONF_PORT]}", data=import_data
        )

    @callback
    def _async_current_names(self) -> set[str]:
        """Return a set of bridge names."""
        return {
            entry.data[CONF_NAME]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_NAME in entry.data
        }

    @callback
    def _async_available_name(self, requested_name: str) -> str:
        """Return an available for the bridge."""
        current_names = self._async_current_names()
        valid_mdns_name = re.sub("[^A-Za-z0-9 ]+", " ", requested_name)

        if valid_mdns_name not in current_names:
            return valid_mdns_name

        acceptable_mdns_chars = string.ascii_uppercase + string.digits
        suggested_name: str | None = None
        while not suggested_name or suggested_name in current_names:
            trailer = "".join(random.choices(acceptable_mdns_chars, k=2))
            suggested_name = f"{valid_mdns_name} {trailer}"

        return suggested_name

    @callback
    def _async_is_unique_name_port(self, user_input: dict[str, Any]) -> bool:
        """Determine is a name or port is already used."""
        name = user_input[CONF_NAME]
        port = user_input[CONF_PORT]
        return not any(
            entry.data[CONF_NAME] == name or entry.data[CONF_PORT] == port
            for entry in self._async_current_entries(include_ignore=False)
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for homekit."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.hk_options: dict[str, Any] = {}
        self.included_cameras: list[str] = []
        self.included_climates: list[str] = []
        # Maps the displayed climate field label back to its entity id.
        self._climate_choices: dict[str, str] = {}

    async def async_step_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the accessory type for climate entities."""
        if not self.included_climates:
            return await self.async_step_bridged_device_triggers()

        hk_options = self.hk_options
        all_entity_config: dict[str, dict[str, Any]]

        if user_input is not None:
            all_entity_config = hk_options[CONF_ENTITY_CONFIG]
            for label, entity_id in self._climate_choices.items():
                entity_config = all_entity_config.setdefault(entity_id, {})

                if (choice := user_input[label]) == CLIMATE_TYPE_AUTOMATIC:
                    entity_config.pop(CONF_TYPE, None)
                else:
                    entity_config[CONF_TYPE] = choice

                if not entity_config:
                    all_entity_config.pop(entity_id)

            if not all_entity_config:
                del hk_options[CONF_ENTITY_CONFIG]

            return await self.async_step_bridged_device_triggers()

        # Field labels come from the schema keys, so key the form by the
        # friendly name and map back to the entity id on submit. The
        # accessory a bridged entity currently uses is shown so Automatic
        # is not a mystery.
        current_accessories = self._async_current_climate_accessories()
        self._climate_choices = {}
        for entity_id in self.included_climates:
            state = self.hass.states.get(entity_id)
            label = f"{state.name} ({entity_id})" if state else entity_id
            if current := current_accessories.get(entity_id):
                label = f"{label} [{current}]"
            self._climate_choices[label] = entity_id

        all_entity_config = hk_options.setdefault(CONF_ENTITY_CONFIG, {})
        type_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    CLIMATE_TYPE_AUTOMATIC,
                    TYPE_THERMOSTAT,
                    TYPE_HEATER_COOLER,
                ],
                translation_key="climate_accessory_type",
            )
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    label,
                    default=all_entity_config.get(entity_id, {}).get(
                        CONF_TYPE, CLIMATE_TYPE_AUTOMATIC
                    ),
                ): type_selector
                for label, entity_id in self._climate_choices.items()
            }
        )
        return self.async_show_form(
            step_id="climate",
            last_step=hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_ACCESSORY,
            data_schema=data_schema,
        )

    @callback
    def _async_current_climate_accessories(self) -> dict[str, str]:
        """Map bridged climate entities to their current accessory name."""
        entry_data: HomeKitEntryData | None = getattr(
            self.config_entry, "runtime_data", None
        )
        if entry_data is None:
            return {}
        homekit = entry_data.homekit
        accessories: Iterable[Any]
        if homekit.bridge is not None:
            accessories = homekit.bridge.accessories.values()
        elif homekit.driver is not None and homekit.driver.accessory is not None:
            accessories = [homekit.driver.accessory]
        else:
            return {}
        return {
            entity_id: CLIMATE_ACCESSORY_NAMES[accessory_name]
            for accessory in accessories
            if (entity_id := getattr(accessory, "entity_id", None)) is not None
            and (accessory_name := type(accessory).__name__) in CLIMATE_ACCESSORY_NAMES
        }

    async def async_step_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """No options for yaml managed entries."""
        if user_input is not None:
            # Apparently not possible to abort an options flow
            # at the moment
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(step_id="yaml", last_step=True)

    async def async_step_bridged_device_triggers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose bridged device triggers options."""
        hk_options = self.hk_options
        bridge_mode = hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_BRIDGE

        if user_input is not None or not bridge_mode:
            if user_input:
                hk_options.update(user_input)
                if bridge_mode:
                    hk_options[CONF_DEVICES] = user_input[CONF_DEVICES]

            hk_options.pop(CONF_DOMAINS, None)
            hk_options.pop(CONF_ENTITIES, None)
            return self.async_create_entry(title="", data=self.hk_options)

        all_supported_devices = await _async_get_supported_devices(self.hass)
        # Strip out devices that no longer exist to prevent error in the UI
        devices = [
            device_id
            for device_id in self.hk_options.get(CONF_DEVICES, [])
            if device_id in all_supported_devices
        ]
        return self.async_show_form(
            step_id="bridged_device_triggers",
            last_step=True,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEVICES, default=devices): cv.multi_select(
                        all_supported_devices
                    )
                }
            ),
        )

    async def async_step_cameras(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose camera config."""
        if not self.included_cameras:
            return await self.async_step_climate()

        hk_options = self.hk_options
        all_entity_config: dict[str, dict[str, Any]]

        if user_input is not None:
            all_entity_config = hk_options[CONF_ENTITY_CONFIG]
            for entity_id in self.included_cameras:
                entity_config = all_entity_config.setdefault(entity_id, {})

                if entity_id in user_input[CONF_CAMERA_COPY]:
                    entity_config[CONF_VIDEO_CODEC] = VIDEO_CODEC_COPY
                elif CONF_VIDEO_CODEC in entity_config:
                    del entity_config[CONF_VIDEO_CODEC]

                if entity_id in user_input[CONF_CAMERA_AUDIO]:
                    entity_config[CONF_SUPPORT_AUDIO] = True
                elif CONF_SUPPORT_AUDIO in entity_config:
                    del entity_config[CONF_SUPPORT_AUDIO]

                if not entity_config:
                    all_entity_config.pop(entity_id)

            return await self.async_step_climate()

        cameras_with_audio = []
        cameras_with_copy = []
        all_entity_config = hk_options.setdefault(CONF_ENTITY_CONFIG, {})
        for entity in self.included_cameras:
            entity_config = all_entity_config.get(entity, {})
            if entity_config.get(CONF_VIDEO_CODEC) == VIDEO_CODEC_COPY:
                cameras_with_copy.append(entity)
            if entity_config.get(CONF_SUPPORT_AUDIO):
                cameras_with_audio.append(entity)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CAMERA_COPY, default=cameras_with_copy
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        multiple=True,
                        include_entities=(self.included_cameras),
                    )
                ),
                vol.Optional(
                    CONF_CAMERA_AUDIO, default=cameras_with_audio
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        multiple=True,
                        include_entities=(self.included_cameras),
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="cameras",
            last_step=hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_ACCESSORY,
            data_schema=data_schema,
        )

    async def async_step_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose entity for the accessory."""
        hk_options = self.hk_options
        domains = hk_options[CONF_DOMAINS]
        entity_filter: EntityFilterDict

        if user_input is not None:
            entities = cv.ensure_list(user_input[CONF_ENTITIES])
            entity_filter = _make_entity_filter(include_entities=entities)
            self.included_cameras = _async_entities_in_domain(entities, CAMERA_DOMAIN)
            self.included_climates = _async_entities_in_domain(entities, CLIMATE_DOMAIN)
            hk_options[CONF_FILTER] = entity_filter
            return await self.async_step_review()

        entity_filter = hk_options.get(CONF_FILTER, {})
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])
        entity_config = hk_options.get(CONF_ENTITY_CONFIG, {})
        all_supported_entities = [
            entity_id
            for entity_id in _async_get_matching_entities(
                self.hass, domains, include_entity_category=True, include_hidden=True
            )
            if (state := self.hass.states.get(entity_id)) is not None
            and get_accessory_type(
                state, entity_config.get(entity_id, {}), log_errors=False
            )
            is not None
        ]
        # In accessory mode we can only have one
        default_value = next(
            iter(
                entity_id
                for entity_id in entities
                if entity_id in all_supported_entities
            ),
            None,
        )

        return self.async_show_form(
            step_id="accessory",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTITIES, default=default_value
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            include_entities=all_supported_entities,
                        )
                    ),
                }
            ),
        )

    async def async_step_include(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose entities to include and exclude on the bridge."""
        hk_options = self.hk_options
        domains = hk_options[CONF_DOMAINS]
        if user_input is not None:
            include_targets: dict[str, list[str]] = user_input.get(
                CONF_INCLUDE_TARGETS, {}
            )
            previous_filter = hk_options.get(CONF_FILTER, {})
            entity_filter = _async_build_entities_filter(domains, include_targets)
            exclude_targets = user_input.get(CONF_EXCLUDE_TARGETS)
            if exclude_targets is None:
                exclude_targets = deepcopy(
                    previous_filter.get(CONF_EXCLUDE_TARGETS, {})
                )
                if legacy_excludes := previous_filter.get(CONF_EXCLUDE_ENTITIES):
                    valid_legacy_excludes = [
                        entity_id
                        for entity_id in legacy_excludes
                        if self.hass.states.get(entity_id) is not None
                    ]
                    if valid_legacy_excludes:
                        exclude_targets.setdefault(CONF_ENTITY_ID, []).extend(
                            valid_legacy_excludes
                        )
            if exclude_targets:
                entity_filter["exclude_targets"] = exclude_targets
            hk_options[CONF_FILTER] = entity_filter
            entity_config = hk_options.get(CONF_ENTITY_CONFIG)
            self.included_cameras = _async_entity_ids_matching_filter(
                self.hass, entity_filter, [CAMERA_DOMAIN], entity_config
            )
            self.included_climates = _async_entity_ids_matching_filter(
                self.hass, entity_filter, [CLIMATE_DOMAIN], entity_config
            )
            return await self.async_step_review()

        entity_filter = hk_options.get(CONF_FILTER, {})
        include_targets = deepcopy(entity_filter.get(CONF_INCLUDE_TARGETS, {}))
        exclude_targets = deepcopy(entity_filter.get(CONF_EXCLUDE_TARGETS, {}))
        all_supported_entities = _async_get_matching_entities(
            self.hass,
            SUPPORTED_DOMAINS,
            include_entity_category=True,
            include_hidden=True,
        )
        if legacy_entities := entity_filter.get(CONF_INCLUDE_ENTITIES):
            if valid_entities := [
                entity_id
                for entity_id in legacy_entities
                if entity_id in all_supported_entities
            ]:
                include_targets.setdefault(CONF_ENTITY_ID, []).extend(valid_entities)
        if legacy_excludes := entity_filter.get(CONF_EXCLUDE_ENTITIES):
            if valid_legacy_excludes := [
                entity_id
                for entity_id in legacy_excludes
                if entity_id in all_supported_entities
            ]:
                exclude_targets.setdefault(CONF_ENTITY_ID, []).extend(
                    valid_legacy_excludes
                )

        target_selector = selector.TargetSelector(
            selector.TargetSelectorConfig(
                entity={"domain": SUPPORTED_DOMAINS},
                primary_entities_only=True,
            )
        )
        return self.async_show_form(
            step_id="include",
            last_step=False,
            description_placeholders={
                "domains": await _async_domain_names(self.hass, domains)
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_TARGETS, default=include_targets
                    ): target_selector,
                    vol.Optional(
                        CONF_EXCLUDE_TARGETS, default=exclude_targets
                    ): target_selector,
                }
            ),
        )

    async def async_step_review(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review the selected entities."""
        if user_input is not None:
            return await self.async_step_cameras()

        entity_ids = _async_entity_ids_matching_filter(
            self.hass,
            self.hk_options[CONF_FILTER],
            SUPPORTED_DOMAINS,
            self.hk_options.get(CONF_ENTITY_CONFIG),
        )
        bridge_mode = self.hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_BRIDGE
        return self.async_show_form(
            step_id="review",
            last_step=not bridge_mode
            and not (self.included_cameras or self.included_climates),
            description_placeholders={"count": str(len(entity_ids))},
            data_schema=_entity_review_schema(entity_ids),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if self.config_entry.source == SOURCE_IMPORT:
            return await self.async_step_yaml(user_input)

        if user_input is not None:
            self.hk_options.update(user_input)
            if self.hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_ACCESSORY:
                return await self.async_step_accessory()
            return await self.async_step_include()

        self.hk_options = deepcopy(dict(self.config_entry.options))
        homekit_mode = self.hk_options.get(CONF_HOMEKIT_MODE, DEFAULT_HOMEKIT_MODE)
        entity_filter: EntityFilterDict = self.hk_options.get(CONF_FILTER, {})
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])
        domains = list(entity_filter.get(CONF_INCLUDE_DOMAINS, []))
        if homekit_mode == HOMEKIT_MODE_ACCESSORY and entities:
            domains.extend(_domains_set_from_entities(entities))
        name_to_type_map = await _async_name_to_type_map(self.hass)
        return self.async_show_form(
            step_id="init",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOMEKIT_MODE, default=homekit_mode): vol.In(
                        HOMEKIT_MODES
                    ),
                    vol.Required(
                        CONF_DOMAINS,
                        default=domains,
                    ): cv.multi_select(name_to_type_map),
                }
            ),
        )


async def _async_get_supported_devices(hass: HomeAssistant) -> dict[str, str]:
    """Return all supported devices."""
    results = await device_automation.async_get_device_automations(
        hass, device_automation.DeviceAutomationType.TRIGGER
    )
    dev_reg = dr.async_get(hass)
    unsorted: dict[str, str] = {}
    for device_id in results:
        entry = dev_reg.async_get(device_id)
        unsorted[device_id] = entry.name or device_id if entry else device_id
    return dict(sorted(unsorted.items(), key=itemgetter(1)))


def _domains_set_from_entities(entity_ids: Iterable[str]) -> set[str]:
    """Build a set of domains for the given entity ids."""
    return {split_entity_id(entity_id)[0] for entity_id in entity_ids}


def _exclude_by_entity_registry(
    ent_reg: er.EntityRegistry,
    entity_id: str,
    include_entity_category: bool,
    include_hidden: bool,
) -> bool:
    """Filter out hidden entities and ones with entity category (unless specified)."""
    return bool(
        (entry := ent_reg.async_get(entity_id))
        and (
            (not include_hidden and entry.hidden_by is not None)
            or (not include_entity_category and entry.entity_category is not None)
        )
    )


def _async_get_matching_entities(
    hass: HomeAssistant,
    domains: list[str] | None = None,
    include_entity_category: bool = False,
    include_hidden: bool = False,
) -> list[str]:
    """Fetch all entities or entities in the given domains."""
    ent_reg = er.async_get(hass)
    return [
        state.entity_id
        for state in sorted(
            hass.states.async_all(domains and set(domains)),
            key=lambda item: item.entity_id,
        )
        if not _exclude_by_entity_registry(
            ent_reg, state.entity_id, include_entity_category, include_hidden
        )
    ]


@callback
def _async_entity_ids_with_accessory_mode(hass: HomeAssistant) -> set[str]:
    """Return a set of entity ids that have config entries in accessory mode."""

    entity_ids: set[str] = set()

    current_entries = hass.config_entries.async_entries(DOMAIN)
    for entry in current_entries:
        # We have to handle the case where the data has not yet
        # been migrated to options because the data was just
        # imported and the entry was never started
        target = entry.options if CONF_HOMEKIT_MODE in entry.options else entry.data
        if target.get(CONF_HOMEKIT_MODE) != HOMEKIT_MODE_ACCESSORY:
            continue

        entity_ids.add(target[CONF_FILTER][CONF_INCLUDE_ENTITIES][0])

    return entity_ids
