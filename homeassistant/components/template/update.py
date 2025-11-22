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
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.template import _SENTINEL
from homeassistant.helpers.trigger_template_entity import CONF_PICTURE
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
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
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._installed_version_template = config[CONF_INSTALLED_VERSION]
        self._latest_version_template = config[CONF_LATEST_VERSION]

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._in_progress_template = config.get(CONF_IN_PROGRESS)
        self._release_summary_template = config.get(CONF_RELEASE_SUMMARY)
        self._release_url_template = config.get(CONF_RELEASE_URL)
        self._title_template = config.get(CONF_TITLE)
        self._update_percentage_template = config.get(CONF_UPDATE_PERCENTAGE)

        self._attr_supported_features = UpdateEntityFeature(0)
        if config[CONF_BACKUP]:
            self._attr_supported_features |= UpdateEntityFeature.BACKUP
        if config[CONF_SPECIFIC_VERSION]:
            self._attr_supported_features |= UpdateEntityFeature.SPECIFIC_VERSION
        if (
            self._in_progress_template is not None
            or self._update_percentage_template is not None
        ):
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        self._optimistic_in_process = (
            self._in_progress_template is None
            and self._update_percentage_template is not None
        )

    @callback
    def _update_installed_version(self, result: Any) -> None:
        if result is None:
            self._attr_installed_version = None
            return

        self._attr_installed_version = cv.string(result)

    @callback
    def _update_latest_version(self, result: Any) -> None:
        if result is None:
            self._attr_latest_version = None
            return

        self._attr_latest_version = cv.string(result)

    @callback
    def _update_in_process(self, result: Any) -> None:
        try:
            self._attr_in_progress = cv.boolean(result)
        except vol.Invalid:
            _LOGGER.error(
                "Received invalid in_process value: %s for entity %s.  Expected: True, False",
                result,
                self.entity_id,
            )
            self._attr_in_progress = False

    @callback
    def _update_release_summary(self, result: Any) -> None:
        if result is None:
            self._attr_release_summary = None
            return

        self._attr_release_summary = cv.string(result)

    @callback
    def _update_release_url(self, result: Any) -> None:
        if result is None:
            self._attr_release_url = None
            return

        try:
            self._attr_release_url = cv.url(result)
        except vol.Invalid:
            _LOGGER.error(
                "Received invalid release_url: %s for entity %s",
                result,
                self.entity_id,
            )
            self._attr_release_url = None

    @callback
    def _update_title(self, result: Any) -> None:
        if result is None:
            self._attr_title = None
            return

        self._attr_title = cv.string(result)

    @callback
    def _update_update_percentage(self, result: Any) -> None:
        if result is None:
            if self._optimistic_in_process:
                self._attr_in_progress = False
            self._attr_update_percentage = None
            return

        try:
            percentage = vol.All(
                vol.Coerce(float),
                vol.Range(0, 100, min_included=True, max_included=True),
            )(result)
            if self._optimistic_in_process:
                self._attr_in_progress = True
            self._attr_update_percentage = percentage
        except vol.Invalid:
            _LOGGER.error(
                "Received invalid update_percentage: %s for entity %s",
                result,
                self.entity_id,
            )
            self._attr_update_percentage = None

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
        AbstractTemplateUpdate.__init__(self, config)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        # Scripts can be an empty list, therefore we need to check for None
        if (install_action := config.get(CONF_INSTALL)) is not None:
            self.add_script(CONF_INSTALL, install_action, name, DOMAIN)
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

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

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute(
            "_attr_installed_version",
            self._installed_version_template,
            None,
            self._update_installed_version,
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_attr_latest_version",
            self._latest_version_template,
            None,
            self._update_latest_version,
            none_on_template_error=True,
        )
        if self._in_progress_template is not None:
            self.add_template_attribute(
                "_attr_in_progress",
                self._in_progress_template,
                None,
                self._update_in_process,
                none_on_template_error=True,
            )
        if self._release_summary_template is not None:
            self.add_template_attribute(
                "_attr_release_summary",
                self._release_summary_template,
                None,
                self._update_release_summary,
                none_on_template_error=True,
            )
        if self._release_url_template is not None:
            self.add_template_attribute(
                "_attr_release_url",
                self._release_url_template,
                None,
                self._update_release_url,
                none_on_template_error=True,
            )
        if self._title_template is not None:
            self.add_template_attribute(
                "_attr_title",
                self._title_template,
                None,
                self._update_title,
                none_on_template_error=True,
            )
        if self._update_percentage_template is not None:
            self.add_template_attribute(
                "_attr_update_percentage",
                self._update_percentage_template,
                None,
                self._update_update_percentage,
                none_on_template_error=True,
            )
        super()._async_setup_templates()


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
        AbstractTemplateUpdate.__init__(self, config)

        for key in (
            CONF_INSTALLED_VERSION,
            CONF_LATEST_VERSION,
        ):
            self._to_render_simple.append(key)
            self._parse_result.add(key)

        # Scripts can be an empty list, therefore we need to check for None
        if (install_action := config.get(CONF_INSTALL)) is not None:
            self.add_script(
                CONF_INSTALL,
                install_action,
                self._rendered.get(CONF_NAME, DEFAULT_NAME),
                DOMAIN,
            )
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        for key in (
            CONF_IN_PROGRESS,
            CONF_RELEASE_SUMMARY,
            CONF_RELEASE_URL,
            CONF_TITLE,
            CONF_UPDATE_PERCENTAGE,
        ):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, updater in (
            (CONF_INSTALLED_VERSION, self._update_installed_version),
            (CONF_LATEST_VERSION, self._update_latest_version),
            (CONF_IN_PROGRESS, self._update_in_process),
            (CONF_RELEASE_SUMMARY, self._update_release_summary),
            (CONF_RELEASE_URL, self._update_release_url),
            (CONF_TITLE, self._update_title),
            (CONF_UPDATE_PERCENTAGE, self._update_update_percentage),
        ):
            if (rendered := self._rendered.get(key, _SENTINEL)) is not _SENTINEL:
                updater(rendered)
                write_ha_state = True

        if len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
