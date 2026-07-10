"""Template entity base class."""

from abc import abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, override

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_OPTIMISTIC,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import Template, TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ATTRIBUTES, CONF_DEFAULT_ENTITY_ID, CONF_PICTURE

_SENTINEL = object()


@dataclass
class EntityTemplate:
    """Information class for properly handling template results."""

    attribute: str
    template: Template
    validator: Callable[[Any], Any] | None
    on_update: Callable[[Any], None] | None
    none_on_template_error: bool


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    _entity_id_format: str
    _optimistic_entity: bool = False
    _extra_optimistic_options: tuple[str, ...] | None = None
    _state_option: str | None = None
    _restore_state_extra_data: Any | None = None

    # Restore state properties. The state will be restored if set to None.
    # If a tuple is supplied, all properties must be None for the state to restore.
    _restore_state_properties: tuple[str, ...] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""

        self.hass = hass
        self._config = config
        self._templates: dict[str, EntityTemplate] = {}
        self._action_scripts: dict[str, Script] = {}
        self._attr_extra_state_attributes = {}
        self._attribute_templates: dict[str, Template] | None = config.get(
            CONF_ATTRIBUTES
        )

        if self._optimistic_entity:
            optimistic = config.get(CONF_OPTIMISTIC)

            if self._state_option is not None:
                assumed_optimistic = config.get(self._state_option) is None
                if self._extra_optimistic_options:
                    assumed_optimistic = assumed_optimistic and all(
                        config.get(option) is None
                        for option in self._extra_optimistic_options
                    )

                self._attr_assumed_state = optimistic or (
                    optimistic is None and assumed_optimistic
                )

        if (default_entity_id := config.get(CONF_DEFAULT_ENTITY_ID)) is not None:
            _, _, object_id = default_entity_id.partition(".")
            self.entity_id = async_generate_entity_id(
                self._entity_id_format, object_id, hass=self.hass
            )

        device_registry = dr.async_get(hass)
        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            self.device_entry = device_registry.async_get(device_id)

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @callback
    @abstractmethod
    def _render_script_variables(self) -> dict:
        """Render configured variables."""

    @abstractmethod
    def setup_state_template(
        self,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
    ) -> None:
        """Set up a template that manages the main state of the entity.

        Requires _state_option to be set on the inheriting
        class. _state_option represents the configuration
        option that derives the state. E.g. Template weather
        entities main state option is 'condition', where
        switch is 'state'.
        """

    @abstractmethod
    def setup_template(
        self,
        option: str,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
        render_complex: bool = False,
        none_on_template_error: bool = True,
    ) -> None:
        """Set up a template that manages any property or attribute of the entity.

        Parameters
        ----------
        option
            The configuration key provided by ConfigFlow or the yaml option
        attribute
            The name of the attribute to link to. This attribute must exist
            unless a custom on_update method is supplied.
        validator:
            Optional function that validates the rendered result.
        on_update:
            Called to store the template result rather than storing it
            the supplied attribute. Passed the result of the validator.
        render_complex (default=False):
            This signals trigger based template entities to render the template
            as a complex result. State based template entities always render
            complex results.
        none_on_template_error (default=True)
            If set to false, template errors will be supplied in the result to
            on_update.
        """

    def add_template(
        self,
        option: str,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
        none_on_template_error: bool = False,
        add_if_static: bool = True,
    ) -> Template | None:
        """Add a template."""
        if (template := self._config.get(option)) and isinstance(template, Template):
            if add_if_static or (not template.is_static):
                self._templates[option] = EntityTemplate(
                    attribute,
                    template,
                    validator,
                    on_update,
                    none_on_template_error,
                )
            return template

        return None

    def add_script(
        self,
        script_id: str,
        config: Sequence[dict[str, Any]],
        name: str,
        domain: str,
    ):
        """Add an action script."""

        self._action_scripts[script_id] = Script(
            self.hass,
            config,
            f"{name} {script_id}",
            domain,
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up scripts when removing from Home Assistant."""
        if not self.registry_entry or self.registry_entry.entity_id == self.entity_id:
            # Entity ID not changed, unload scripts as they will not be reused.
            for action_script in self._action_scripts.values():
                await action_script.async_unload()
        else:
            # Entity ID changed, just stop scripts
            for action_script in self._action_scripts.values():
                await action_script.async_stop()

    async def async_run_script(
        self,
        script: Script,
        *,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
    ) -> None:
        """Run an action script."""
        if run_variables is None:
            run_variables = {}
        await script.async_run(
            run_variables={
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
                **self._render_script_variables(),
                **run_variables,
            },
            context=context,
        )

    async def _async_get_last_template_data(
        self,
    ) -> Any | None:
        """Get the last template data."""
        if self._restore_state_extra_data is None or not hasattr(
            self, "async_get_last_extra_data"
        ):
            return _SENTINEL

        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None

        return self._restore_state_extra_data.from_dict(
            restored_last_extra_data.as_dict()
        )

    def restore_extra_data(self, extra_data: Any) -> None:
        """Restore extra data from the last state."""

    async def async_restore_last_state(self) -> None:
        """Restore the state from the last state."""
        if not hasattr(self, "async_get_last_state"):
            return

        last_state: State | None = await self.async_get_last_state()
        if last_state is None:
            return

        # Handle extra data.
        extra_data = _SENTINEL
        if self._restore_state_extra_data is not None:
            extra_data = await self._async_get_last_template_data()

        if (
            extra_data is None
            or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            or (
                self._restore_state_properties is not None
                and any(
                    getattr(self, attr) is not None
                    for attr in self._restore_state_properties
                )
            )
        ):
            return

        if not self.restore_last_state_state(last_state):
            return

        self.restore_last_state_attributes(last_state)

        # Extra data should be loaded last
        if extra_data is not _SENTINEL:
            self.restore_extra_data(extra_data)

    def restore_last_state_state(self, last_state: State) -> bool:
        """Restore the state from the last state."""
        return True

    @abstractmethod
    def restore_attribute(self, conf_attr: str, attr: str, restored_value: Any) -> None:
        """Restore an attribute from the last value."""

    def restore_last_state_attributes(self, last_state: State) -> None:
        """Restore attributes from the last state."""
        # Restore built-in attributes from templates
        for conf_key, attr, _attr in (
            (CONF_ICON, EntityStateAttribute.ICON, "_attr_icon"),
            (CONF_NAME, EntityStateAttribute.FRIENDLY_NAME, "_attr_name"),
            (CONF_PICTURE, EntityStateAttribute.ENTITY_PICTURE, "_attr_entity_picture"),
        ):
            if conf_key not in self._config or attr not in last_state.attributes:
                continue
            value = last_state.attributes[attr]
            self.restore_attribute(conf_key, _attr, value)

        self._attr_extra_state_attributes = {}
        # Restore attributes from template attributes
        if self._attribute_templates:
            for attr in self._config[CONF_ATTRIBUTES]:
                if attr not in last_state.attributes:
                    continue
                self._attr_extra_state_attributes[attr] = last_state.attributes[attr]
