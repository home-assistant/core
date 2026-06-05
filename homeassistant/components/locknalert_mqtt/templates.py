"""MQTT payload template rendering for the LocknAlert integration."""

from ast import literal_eval
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import TemplateVarsType

from .const import DOMAIN, TEMPLATE_ERRORS
from .models import PayloadSentinel, PublishPayloadType

_LOGGER = logging.getLogger(__name__)

ATTR_THIS = "this"


def convert_outgoing_mqtt_payload(
    payload: PublishPayloadType,
) -> PublishPayloadType:
    r"""Convert a quoted bytes literal string to raw bytes before publishing.

    When a Jinja2 template renders a ``bytes`` value it produces a string
    such as ``"b'\x00\x01'"`` rather than the raw bytes object.  This
    function detects that pattern and evaluates it back to ``bytes`` using
    :func:`ast.literal_eval`.  All other payload types are returned unchanged.

    Args:
        payload (PublishPayloadType): The value to check and optionally
            convert.  May be ``str``, ``bytes``, ``int``, ``float``, or
            ``None``.

    Returns:
        PublishPayloadType: Raw ``bytes`` if *payload* was a quoted bytes
            literal, otherwise the original *payload* unchanged.
    """
    if isinstance(payload, str) and payload.startswith(("b'", 'b"')):
        try:
            native_object = literal_eval(payload)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            pass
        else:
            if isinstance(native_object, bytes):
                return native_object

    return payload


class MqttCommandTemplateException(ServiceValidationError):
    """Raised when a command template fails to render a publish payload.

    Wraps the underlying :class:`~homeassistant.exceptions.TemplateError`
    with additional context (entity id, template source, value) so that
    the error appears as a user-readable service validation failure in the
    Home Assistant UI.

    Args:
        base_exception (Exception): The original template rendering error.
        command_template (str): The Jinja2 template source that failed.
        value (PublishPayloadType): The payload value passed to the template.
        entity_id (str | None): The entity id whose command triggered the
            rendering, or ``None`` if called outside an entity context.
    """

    _message: str

    def __init__(
        self,
        *args: object,
        base_exception: Exception,
        command_template: str,
        value: PublishPayloadType,
        entity_id: str | None = None,
    ) -> None:
        """Initialise with structured translation placeholders and a log message."""
        super().__init__(base_exception, *args)
        value_log = str(value)
        self.translation_domain = DOMAIN
        self.translation_key = "command_template_error"
        self.translation_placeholders = {
            "error": str(base_exception),
            "entity_id": str(entity_id),
            "command_template": command_template,
        }
        entity_id_log = "" if entity_id is None else f" for entity '{entity_id}'"
        self._message = (
            f"{type(base_exception).__name__}: {base_exception} rendering template{entity_id_log}"
            f", template: '{command_template}' and payload: {value_log}"
        )

    def __str__(self) -> str:
        """Return exception message string."""
        return self._message


class MqttCommandTemplate:
    """Renders Jinja2 command templates into MQTT publish payloads.

    Wraps a Home Assistant :class:`~homeassistant.helpers.template.Template`
    and injects ``value``, ``entity_id``, ``name``, and ``this`` variables
    automatically so entity actions can produce dynamic payloads without
    boilerplate.

    Args:
        command_template (template.Template | None): The Jinja2 template to
            render, or ``None`` to pass values through unchanged.
        entity (Entity | None): The entity whose state is exposed as ``this``
            inside the template, or ``None`` for template-only contexts.
    """

    def __init__(
        self,
        command_template: template.Template | None,
        *,
        entity: Entity | None = None,
    ) -> None:
        """Initialise the template wrapper and optional entity reference."""
        self._template_state: template.TemplateStateFromEntityId | None = None
        self._command_template = command_template
        self._entity = entity

    @callback
    def async_render(
        self,
        value: PublishPayloadType = None,
        variables: TemplateVarsType = None,
    ) -> PublishPayloadType:
        """Render the command template and return the resulting publish payload.

        If no template was supplied the *value* is returned directly.
        The template receives ``value``, ``entity_id``, ``name``, ``this``,
        and any extra *variables* as its render context.

        Args:
            value (PublishPayloadType): The base value exposed as ``value``
                inside the template.  Defaults to ``None``.
            variables (TemplateVarsType): Additional variables merged into
                the render context, or ``None`` for no extras.

        Returns:
            PublishPayloadType: The rendered payload, already passed through
                :func:`convert_outgoing_mqtt_payload` to handle bytes literals.

        Raises:
            MqttCommandTemplateException: If the template raises a
                :class:`~homeassistant.exceptions.TemplateError`.
        """
        if self._command_template is None:
            return value

        values: dict[str, Any] = {"value": value}
        if self._entity:
            values[ATTR_ENTITY_ID] = self._entity.entity_id
            values[ATTR_NAME] = self._entity.name
            if not self._template_state and self._command_template.hass is not None:
                self._template_state = template.TemplateStateFromEntityId(
                    self._entity.hass, self._entity.entity_id
                )
            values[ATTR_THIS] = self._template_state

        if variables is not None:
            values.update(variables)
        _LOGGER.debug(
            "Rendering outgoing payload with template %s",
            self._command_template,
        )
        try:
            return convert_outgoing_mqtt_payload(
                self._command_template.async_render(values, parse_result=False)
            )
        except TemplateError as exc:
            raise MqttCommandTemplateException(
                base_exception=exc,
                command_template=self._command_template.template,
                value=value,
                entity_id=self._entity.entity_id if self._entity is not None else None,
            ) from exc


class MqttValueTemplateException(TemplateError):
    """Raised when a value template fails to render a received MQTT payload.

    Wraps the underlying template error with the entity id, template source,
    default value, and incoming payload so the failure can be logged with
    enough context to diagnose the problem.

    Args:
        base_exception (Exception): The original template rendering error.
        value_template (str): The Jinja2 template source that failed.
        default (ReceivePayloadType | PayloadSentinel): The fallback value
            that would have been used on failure, for logging purposes.
        payload (ReceivePayloadType): The raw MQTT payload that was passed
            to the template.
        entity_id (str | None): The entity id being updated, or ``None``
            if called outside an entity context.
    """

    _message: str

    def __init__(
        self,
        *args: object,
        base_exception: Exception,
        value_template: str,
        default: ReceivePayloadType | PayloadSentinel,
        payload: ReceivePayloadType,
        entity_id: str | None = None,
    ) -> None:
        """Initialise with a human-readable error message."""
        super().__init__(base_exception, *args)
        entity_id_log = "" if entity_id is None else f" for entity '{entity_id}'"
        default_log = str(default)
        default_payload_log = (
            "" if default is PayloadSentinel.NONE else f", default value: {default_log}"
        )
        payload_log = str(payload)
        self._message = (
            f"{type(base_exception).__name__}: {base_exception} rendering template{entity_id_log}"
            f", template: '{value_template}'{default_payload_log} and payload: {payload_log}"
        )

    def __str__(self) -> str:
        """Return exception message string."""
        return self._message


class MqttValueTemplate:
    """Renders Jinja2 value templates against incoming MQTT payloads.

    Wraps a Home Assistant :class:`~homeassistant.helpers.template.Template`
    and injects ``entity_id``, ``name``, ``this``, and any static
    *config_attributes* so that entity state sensors can transform raw
    payloads into HA-compatible values without boilerplate.

    Args:
        value_template (template.Template | None): The Jinja2 template to
            render, or ``None`` to pass payloads through unchanged.
        entity (Entity | None): The entity whose state is exposed as ``this``
            inside the template, or ``None`` for template-only contexts.
        config_attributes (TemplateVarsType): Static variables merged into
            the render context at construction time, or ``None`` for none.
    """

    def __init__(
        self,
        value_template: template.Template | None,
        *,
        entity: Entity | None = None,
        config_attributes: TemplateVarsType = None,
    ) -> None:
        """Initialise the template wrapper, entity reference, and static attributes."""
        self._template_state: template.TemplateStateFromEntityId | None = None
        self._value_template = value_template
        self._config_attributes = config_attributes
        self._entity = entity

    @callback
    def async_render_with_possible_json_value(
        self,
        payload: ReceivePayloadType,
        default: ReceivePayloadType | PayloadSentinel = PayloadSentinel.NONE,
        variables: TemplateVarsType = None,
    ) -> ReceivePayloadType:
        """Render the value template against an incoming MQTT payload.

        If no template was supplied the *payload* is returned directly.
        The template is rendered with HA's JSON-aware method, which
        automatically parses JSON payloads and exposes their fields as
        template variables.  When *default* is ``PayloadSentinel.NONE`` any
        template error raises an exception; otherwise the error is logged and
        *default* is returned.

        Args:
            payload (ReceivePayloadType): The raw MQTT message payload
                (``str`` or ``bytes``) to render the template against.
            default (ReceivePayloadType | PayloadSentinel): The value to
                return on template error, or ``PayloadSentinel.NONE`` to
                raise instead.
            variables (TemplateVarsType): Extra variables merged into the
                render context, or ``None`` for none.

        Returns:
            ReceivePayloadType: The rendered result, which may be a
                ``str``, ``int``, ``float``, ``list``, ``dict``, or the
                *default* value on error.

        Raises:
            MqttValueTemplateException: If the template raises and *default*
                is ``PayloadSentinel.NONE``.
        """
        rendered_payload: ReceivePayloadType

        if self._value_template is None:
            return payload

        values: dict[str, Any] = {}

        if variables is not None:
            values.update(variables)

        if self._config_attributes is not None:
            values.update(self._config_attributes)

        if self._entity:
            values[ATTR_ENTITY_ID] = self._entity.entity_id
            values[ATTR_NAME] = self._entity.name
            if not self._template_state and self._value_template.hass:
                self._template_state = template.TemplateStateFromEntityId(
                    self._value_template.hass, self._entity.entity_id
                )
            values[ATTR_THIS] = self._template_state

        if default is PayloadSentinel.NONE:
            _LOGGER.debug(
                "Rendering incoming payload '%s' with template %s",
                payload,
                self._value_template,
            )
            try:
                rendered_payload = (
                    self._value_template.async_render_with_possible_json_value(
                        payload, variables=values
                    )
                )
            except TEMPLATE_ERRORS as exc:
                raise MqttValueTemplateException(
                    base_exception=exc,
                    value_template=self._value_template.template,
                    default=default,
                    payload=payload,
                    entity_id=self._entity.entity_id if self._entity else None,
                ) from exc
            return rendered_payload

        _LOGGER.debug(
            "Rendering incoming payload '%s' with default '%s' and template %s",
            payload,
            default,
            self._value_template,
        )
        try:
            rendered_payload = (
                self._value_template.async_render_with_possible_json_value(
                    payload, default, variables=values
                )
            )
        except TEMPLATE_ERRORS as exc:
            raise MqttValueTemplateException(
                base_exception=exc,
                value_template=self._value_template.template,
                default=default,
                payload=payload,
                entity_id=self._entity.entity_id if self._entity else None,
            ) from exc
        return rendered_payload
