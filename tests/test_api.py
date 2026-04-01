"""Tests for websocket error translation."""

from __future__ import annotations

import voluptuous as vol

from hass_client.api import _translate_command_error
from hass_client.exceptions import FailedCommand
from homeassistant.components.websocket_api import const as websocket_api_const
from homeassistant.exceptions import (
    ServiceNotFound,
    ServiceValidationError,
    TemplateError,
)


def test_translate_call_service_not_found() -> None:
    """Translate remote service lookup failures into ServiceNotFound."""
    exception = _translate_command_error(
        {"type": "call_service", "domain": "light", "service": "turn_on"},
        {
            "code": websocket_api_const.ERR_NOT_FOUND,
            "message": "Service light.turn_on not found.",
            "translation_domain": "homeassistant",
            "translation_key": "service_not_found",
        },
    )

    assert isinstance(exception, ServiceNotFound)
    assert exception.domain == "light"
    assert exception.service == "turn_on"


def test_translate_call_service_validation_error() -> None:
    """Translate remote validation failures into ServiceValidationError."""
    exception = _translate_command_error(
        {"type": "call_service", "domain": "light", "service": "turn_on"},
        {
            "code": websocket_api_const.ERR_SERVICE_VALIDATION_ERROR,
            "message": "Validation error: return_response can only be used with blocking calls",
            "translation_domain": "homeassistant",
            "translation_key": "service_should_be_blocking",
            "translation_placeholders": {
                "return_response": "return_response=True",
                "non_blocking_argument": "blocking=False",
            },
        },
    )

    assert isinstance(exception, ServiceValidationError)
    assert exception.translation_domain == "homeassistant"
    assert exception.translation_key == "service_should_be_blocking"
    assert exception.translation_placeholders == {
        "return_response": "return_response=True",
        "non_blocking_argument": "blocking=False",
    }


def test_translate_call_service_invalid_format() -> None:
    """Translate websocket invalid format errors into vol.Invalid."""
    exception = _translate_command_error(
        {"type": "call_service", "domain": "light", "service": "turn_on"},
        {
            "code": websocket_api_const.ERR_INVALID_FORMAT,
            "message": "extra keys not allowed @ data['invalid']",
        },
    )

    assert isinstance(exception, vol.Invalid)


def test_translate_generic_error_falls_back_to_failed_command() -> None:
    """Keep generic websocket failures as FailedCommand when there is no HA analogue."""
    exception = _translate_command_error(
        {"type": "config/entity_registry/get", "entity_id": "light.kitchen"},
        {
            "code": websocket_api_const.ERR_NOT_FOUND,
            "message": "Entity not found",
        },
    )

    assert isinstance(exception, FailedCommand)
    assert exception.command == "config/entity_registry/get"
    assert exception.code == websocket_api_const.ERR_NOT_FOUND


def test_translate_template_error() -> None:
    """Translate template websocket failures into TemplateError."""
    exception = _translate_command_error(
        {"type": "render_template"},
        {
            "code": websocket_api_const.ERR_TEMPLATE_ERROR,
            "message": "Template rendered invalid output",
        },
    )

    assert isinstance(exception, TemplateError)
