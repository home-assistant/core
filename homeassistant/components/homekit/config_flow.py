"""Config flow for HomeKit integration."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from operator import itemgetter
import random
import re
import string
from typing import Any, Final, TypedDict

import voluptuous as vol

from homeassistant.components import device_automation
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_DEVICES,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.loader import async_get_integrations

from .const import (
    CONF_ENTITY_CONFIG,
    CONF_EXCLUDE_ACCESSORY_MODE,
    CONF_FILTER,
    CONF_HOMEKIT_MODE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    DEFAULT_CONFIG_FLOW_PORT,
    DEFAULT_HOMEKIT_MODE,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODE_BRIDGE,
    HOMEKIT_MODES,
    SHORT_BRIDGE_NAME,
    VIDEO_CODEC_COPY,
)
from .util import async_find_next_available_port, state_needs_accessory_mode

CONF_CAMERA_AUDIO = "camera_audio"
CONF_CAMERA_COPY = "camera_copy"
CONF_INCLUDE_EXCLUDE_MODE = "include_exclude_mode"

MODE_INCLUDE = "include"
MODE_EXCLUDE = "exclude"

INCLUDE_EXCLUDE_MODES = [MODE_EXCLUDE, MODE_INCLUDE]

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
    "water_heater",
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


def _make_entity_filter(
    include_domains: list[str] | None = None,
    include_entities: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    exclude_entities: list[str] | None = None,
) -> EntityFilterDict:
    """Create a filter dict."""
    return EntityFilterDict(
        include_domains=include_domains or [],
        include_entities=include_entities or [],
        exclude_domains=exclude_domains or [],
        exclude_entities=exclude_entities or [],
    )


async def _async_domain_names(hass: HomeAssistant, domains: list[str]) -> str:
    """Build a list of integration names from domains."""
    name_to_type_map = await _async_name_to_type_map(hass)
    return ", ".join(
        [name for domain, name in name_to_type_map.items() if domain in domains]
    )


@callback
def _async_build_entities_filter(
    domains: list[str], entities: list[str]
) -> EntityFilterDict:
    """Build an entities filter from domains and entities."""
    # Include all of the domain if there are no entities
    # explicitly included as the user selected the domain
    return _make_entity_filter(
        include_domains=sorted(
            set(domains).difference(_domains_set_from_entities(entities))
        ),
        include_entities=entities,
    )


def _async_cameras_from_entities(entities: list[str]) -> dict[str, str]:
    return {
        entity_id: entity_id
        for entity_id in entities
        if entity_id.startswith(CAMERA_ENTITY_PREFIX)
    }


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose specific domains in bridge mode."""
        if user_input is not None:
            self.hk_data[CONF_FILTER] = _make_entity_filter(
                include_domains=user_input[CONF_INCLUDE_DOMAINS]
            )
            return await self.async_step_pairing()

        self.hk_data[CONF_HOMEKIT_MODE] = HOMEKIT_MODE_BRIDGE
        default_domains = (
            [] if self._async_current_entries(include_ignore=False) else DEFAULT_DOMAINS
        )
        name_to_type_map = await _async_name_to_type_map(self.hass)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_DOMAINS, default=default_domains
                    ): cv.multi_select(name_to_type_map),
                }
            ),
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
            description_placeholders={CONF_NAME: hk_data[CONF_NAME]},
        )

    async def _async_add_entries_for_accessory_mode_entities(
        self, last_assigned_port: int
    ) -> None:
        """Generate new flows for entities that need their own instances."""
        accessory_mode_entity_ids = _async_get_entity_ids_for_accessory_mode(
            self.hass, self.hk_data[CONF_FILTER][CONF_INCLUDE_DOMAINS]
        )
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
        name = state.attributes.get(ATTR_FRIENDLY_NAME) or state.entity_id

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

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from yaml."""
        if not self._async_is_unique_name_port(user_input):
            return self.async_abort(reason="port_name_in_use")
        return self.async_create_entry(
            title=f"{user_input[CONF_NAME]}:{user_input[CONF_PORT]}", data=user_input
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
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for homekit."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.hk_options: dict[str, Any] = {}
        self.included_cameras: dict[str, str] = {}

    async def async_step_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """No options for yaml managed entries."""
        if user_input is not None:
            # Apparently not possible to abort an options flow
            # at the moment
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(step_id="yaml")

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose advanced options."""
        hk_options = self.hk_options
        show_advanced_options = self.show_advanced_options
        bridge_mode = hk_options[CONF_HOMEKIT_MODE] == HOMEKIT_MODE_BRIDGE

        if not show_advanced_options or user_input is not None or not bridge_mode:
            if user_input:
                hk_options.update(user_input)
                if show_advanced_options and bridge_mode:
                    hk_options[CONF_DEVICES] = user_input[CONF_DEVICES]

            hk_options.pop(CONF_DOMAINS, None)
            hk_options.pop(CONF_ENTITIES, None)
            hk_options.pop(CONF_INCLUDE_EXCLUDE_MODE, None)
            return self.async_create_entry(title="", data=self.hk_options)

        all_supported_devices = await _async_get_supported_devices(self.hass)
        # Strip out devices that no longer exist to prevent error in the UI
        devices = [
            device_id
            for device_id in self.hk_options.get(CONF_DEVICES, [])
            if device_id in all_supported_devices
        ]
        return self.async_show_form(
            step_id="advanced",
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

            return await self.async_step_advanced()

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
                    CONF_CAMERA_COPY,
                    default=cameras_with_copy,
                ): cv.multi_select(self.included_cameras),
                vol.Optional(
                    CONF_CAMERA_AUDIO,
                    default=cameras_with_audio,
                ): cv.multi_select(self.included_cameras),
            }
        )
        return self.async_show_form(step_id="cameras", data_schema=data_schema)

    async def async_step_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose entity for the accessory."""
        hk_options = self.hk_options
        domains = hk_options[CONF_DOMAINS]
        entity_filter: EntityFilterDict

        if user_input is not None:
            entities = cv.ensure_list(user_input[CONF_ENTITIES])
            entity_filter = _async_build_entities_filter(domains, entities)
            self.included_cameras = _async_cameras_from_entities(entities)
            hk_options[CONF_FILTER] = entity_filter
            if self.included_cameras:
                return await self.async_step_cameras()
            return await self.async_step_advanced()

        entity_filter = hk_options.get(CONF_FILTER, {})
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])
        all_supported_entities = _async_get_matching_entities(
            self.hass, domains, include_entity_category=True, include_hidden=True
        )
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITIES, default=default_value): vol.In(
                        all_supported_entities
                    )
                }
            ),
        )

    async def async_step_include(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose entities to include from the domain on the bridge."""
        hk_options = self.hk_options
        domains = hk_options[CONF_DOMAINS]
        if user_input is not None:
            entities = cv.ensure_list(user_input[CONF_ENTITIES])
            self.included_cameras = _async_cameras_from_entities(entities)
            hk_options[CONF_FILTER] = _async_build_entities_filter(domains, entities)
            if self.included_cameras:
                return await self.async_step_cameras()
            return await self.async_step_advanced()

        entity_filter: EntityFilterDict = hk_options.get(CONF_FILTER, {})
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])
        all_supported_entities = _async_get_matching_entities(
            self.hass, domains, include_entity_category=True, include_hidden=True
        )
        # Strip out entities that no longer exist to prevent error in the UI
        default_value = [
            entity_id for entity_id in entities if entity_id in all_supported_entities
        ]

        return self.async_show_form(
            step_id="include",
            description_placeholders={
                "domains": await _async_domain_names(self.hass, domains)
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENTITIES, default=default_value): cv.multi_select(
                        all_supported_entities
                    )
                }
            ),
        )

    async def async_step_exclude(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose entities to exclude from the domain on the bridge."""
        hk_options = self.hk_options
        domains = hk_options[CONF_DOMAINS]

        if user_input is not None:
            self.included_cameras = {}
            entities = cv.ensure_list(user_input[CONF_ENTITIES])
            if CAMERA_DOMAIN in domains:
                camera_entities = _async_get_matching_entities(
                    self.hass, [CAMERA_DOMAIN]
                )
                self.included_cameras = {
                    entity_id: entity_id
                    for entity_id in camera_entities
                    if entity_id not in entities
                }
            hk_options[CONF_FILTER] = _make_entity_filter(
                include_domains=domains, exclude_entities=entities
            )
            if self.included_cameras:
                return await self.async_step_cameras()
            return await self.async_step_advanced()

        entity_filter = self.hk_options.get(CONF_FILTER, {})
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])

        all_supported_entities = _async_get_matching_entities(self.hass, domains)
        if not entities:
            entities = entity_filter.get(CONF_EXCLUDE_ENTITIES, [])

        # Strip out entities that no longer exist to prevent error in the UI
        default_value = [
            entity_id for entity_id in entities if entity_id in all_supported_entities
        ]

        return self.async_show_form(
            step_id="exclude",
            description_placeholders={
                "domains": await _async_domain_names(self.hass, domains)
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENTITIES, default=default_value): cv.multi_select(
                        all_supported_entities
                    )
                }
            ),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if self.config_entry.source == SOURCE_IMPORT:
            return await self.async_step_yaml(user_input)

        if user_input is not None:
            self.hk_options.update(user_input)
            if self.hk_options.get(CONF_HOMEKIT_MODE) == HOMEKIT_MODE_ACCESSORY:
                return await self.async_step_accessory()
            if user_input[CONF_INCLUDE_EXCLUDE_MODE] == MODE_INCLUDE:
                return await self.async_step_include()
            return await self.async_step_exclude()

        self.hk_options = deepcopy(dict(self.config_entry.options))
        homekit_mode = self.hk_options.get(CONF_HOMEKIT_MODE, DEFAULT_HOMEKIT_MODE)
        entity_filter: EntityFilterDict = self.hk_options.get(CONF_FILTER, {})
        include_exclude_mode = MODE_INCLUDE
        entities = entity_filter.get(CONF_INCLUDE_ENTITIES, [])
        if homekit_mode != HOMEKIT_MODE_ACCESSORY:
            include_exclude_mode = MODE_INCLUDE if entities else MODE_EXCLUDE
        domains = entity_filter.get(CONF_INCLUDE_DOMAINS, [])
        if include_entities := entity_filter.get(CONF_INCLUDE_ENTITIES):
            domains.extend(_domains_set_from_entities(include_entities))
        name_to_type_map = await _async_name_to_type_map(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOMEKIT_MODE, default=homekit_mode): vol.In(
                        HOMEKIT_MODES
                    ),
                    vol.Required(
                        CONF_INCLUDE_EXCLUDE_MODE, default=include_exclude_mode
                    ): vol.In(INCLUDE_EXCLUDE_MODES),
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
) -> dict[str, str]:
    """Fetch all entities or entities in the given domains."""
    ent_reg = er.async_get(hass)
    return {
        state.entity_id: (
            f"{state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id)} ({state.entity_id})"
        )
        for state in sorted(
            hass.states.async_all(domains and set(domains)),
            key=lambda item: item.entity_id,
        )
        if not _exclude_by_entity_registry(
            ent_reg, state.entity_id, include_entity_category, include_hidden
        )
    }


def _domains_set_from_entities(entity_ids: Iterable[str]) -> set[str]:
    """Build a set of domains for the given entity ids."""
    return {split_entity_id(entity_id)[0] for entity_id in entity_ids}


@callback
def _async_get_entity_ids_for_accessory_mode(
    hass: HomeAssistant, include_domains: Iterable[str]
) -> list[str]:
    """Build a list of entities that should be paired in accessory mode."""
    accessory_mode_domains = {
        domain for domain in include_domains if domain in DOMAINS_NEED_ACCESSORY_MODE
    }

    if not accessory_mode_domains:
        return []

    return [
        state.entity_id
        for state in hass.states.async_all(accessory_mode_domains)
        if state_needs_accessory_mode(state)
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
