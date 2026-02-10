"""Support for updates which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as UPDATE_DOMAIN,
    ENTITY_ID_FORMAT,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.trigger_template_entity import CONF_PICTURE
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator, validators as template_validators
from .const import DOMAIN
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Update"

ATTR_BACKUP = "backup"
ATTR_SPECIFIC_VERSION = "specific_version"

CONF_BACKUP = "backup"
CONF_IN_PROGRESS = "in_progress"
CONF_INSTALL = "install"
CONF_INSTALLED_VERSION = "installed_version"
CONF_LATEST_VERSION = "latest_version"
CONF_RELEASE_SUMMARY = "release_summary"
CONF_RELEASE_URL = "release_url"
CONF_SPECIFIC_VERSION = "specific_version"
CONF_TITLE = "title"
CONF_UPDATE_PERCENTAGE = "update_percentage"

UPDATE_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BACKUP, default=False): cv.boolean,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_IN_PROGRESS): cv.template,
        vol.Optional(CONF_INSTALL): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_INSTALLED_VERSION): cv.template,
        vol.Required(CONF_LATEST_VERSION): cv.template,
        vol.Optional(CONF_RELEASE_SUMMARY): cv.template,
        vol.Optional(CONF_RELEASE_URL): cv.template,
        vol.Optional(CONF_SPECIFIC_VERSION, default=False): cv.boolean,
        vol.Optional(CONF_TITLE): cv.template,
        vol.Optional(CONF_UPDATE_PERCENTAGE): cv.template,
    }
)

UPDATE_YAML_SCHEMA = UPDATE_COMMON_SCHEMA.extend(
    make_template_entity_common_modern_schema(UPDATE_DOMAIN, DEFAULT_NAME).schema
)

UPDATE_CONFIG_ENTRY_SCHEMA = UPDATE_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template update."""
    await async_setup_template_platform(
        hass,
        UPDATE_DOMAIN,
        config,
        StateUpdateEntity,
        TriggerUpdateEntity,
        async_add_entities,
        discovery_info,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateUpdateEntity,
        UPDATE_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_update(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateUpdateEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateUpdateEntity,
        UPDATE_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateUpdate(AbstractTemplateEntity, UpdateEntity):
    """Representation of a template update features."""

    _entity_id_format = ENTITY_ID_FORMAT

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        # Setup templates.
        self.setup_template(
            CONF_INSTALLED_VERSION,
            "_attr_installed_version",
            template_validators.string(self, CONF_INSTALLED_VERSION),
        )
        self.setup_template(
            CONF_LATEST_VERSION,
            "_attr_latest_version",
            template_validators.string(self, CONF_LATEST_VERSION),
        )
        self.setup_template(
            CONF_IN_PROGRESS,
            "_attr_in_progress",
            template_validators.boolean(self, CONF_IN_PROGRESS),
            self._update_in_progress,
        )
        self.setup_template(
            CONF_RELEASE_SUMMARY,
            "_attr_release_summary",
            template_validators.string(self, CONF_RELEASE_SUMMARY),
        )
        self.setup_template(
            CONF_RELEASE_URL,
            "_attr_release_url",
            template_validators.url(self, CONF_RELEASE_URL),
        )
        self.setup_template(
            CONF_TITLE,
            "_attr_title",
            template_validators.string(self, CONF_TITLE),
        )
        self.setup_template(
            CONF_UPDATE_PERCENTAGE,
            "_attr_update_percentage",
            template_validators.number(self, CONF_UPDATE_PERCENTAGE, 0.0, 100.0),
            self._update_update_percentage,
        )

        self._attr_supported_features = UpdateEntityFeature(0)
        if config[CONF_BACKUP]:
            self._attr_supported_features |= UpdateEntityFeature.BACKUP
        if config[CONF_SPECIFIC_VERSION]:
            self._attr_supported_features |= UpdateEntityFeature.SPECIFIC_VERSION
        if (
            CONF_IN_PROGRESS in self._templates
            or CONF_UPDATE_PERCENTAGE in self._templates
        ):
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        self._optimistic_in_process = (
            CONF_IN_PROGRESS not in self._templates
            and CONF_UPDATE_PERCENTAGE in self._templates
        )

        # Scripts can be an empty list, therefore we need to check for None
        if (install_action := config.get(CONF_INSTALL)) is not None:
            self.add_script(CONF_INSTALL, install_action, name, DOMAIN)
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

    @callback
    def _update_in_progress(self, result: bool | None) -> None:
        if result is None:
            template_validators.log_validation_result_error(
                self, CONF_IN_PROGRESS, result, "expected a boolean"
            )
        self._attr_in_progress = result or False

    @callback
    def _update_update_percentage(self, result: float | None) -> None:
        if result is None:
            if self._optimistic_in_process:
                self._attr_in_progress = False
            self._attr_update_percentage = None
            return

        if self._optimistic_in_process:
            self._attr_in_progress = True
        self._attr_update_percentage = result

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.async_run_script(
            self._action_scripts[CONF_INSTALL],
            run_variables={ATTR_SPECIFIC_VERSION: version, ATTR_BACKUP: backup},
            context=self._context,
        )


class StateUpdateEntity(TemplateEntity, AbstractTemplateUpdate):
    """Representation of a Template update."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template update."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateUpdate.__init__(self, name, config)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        # This is needed to override the base update entity functionality
        if self._attr_entity_picture is None:
            # The default picture for update entities would use `self.platform.platform_name` in
            # place of `template`.  This does not work when creating an entity preview because
            # the platform does not exist for that entity, therefore this is hardcoded as `template`.
            return "https://brands.home-assistant.io/_/template/icon.png"
        return self._attr_entity_picture


class TriggerUpdateEntity(TriggerEntity, AbstractTemplateUpdate):
    """Update entity based on trigger data."""

    domain = UPDATE_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateUpdate.__init__(self, name, config)

        # Ensure the entity picture can resolve None to produce the default picture.
        if CONF_PICTURE in config:
            self._parse_result.add(CONF_PICTURE)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and self._attr_installed_version is None
            and self._attr_latest_version is None
        ):
            self._attr_installed_version = last_state.attributes[ATTR_INSTALLED_VERSION]
            self._attr_latest_version = last_state.attributes[ATTR_LATEST_VERSION]
            self.restore_attributes(last_state)

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if (picture := self._rendered.get(CONF_PICTURE)) is None:
            return UpdateEntity.entity_picture.fget(self)  # type: ignore[attr-defined]
        return picture
