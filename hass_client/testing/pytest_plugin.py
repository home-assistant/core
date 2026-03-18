"""Pytest bridge for running Home Assistant core tests against hass-client."""

from __future__ import annotations

from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path

from hass_client.runtime import RemoteHomeAssistant


def _build_exception_message_fallback(original):
    """Build a fallback that reads strings.json when translations are not generated."""

    def async_get_exception_message(
        translation_domain: str,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> str:
        message = original(
            translation_domain,
            translation_key,
            translation_placeholders,
        )
        if message != translation_key:
            return message

        spec = importlib.util.find_spec(
            f"homeassistant.components.{translation_domain}"
        )
        if spec is None or spec.origin is None:
            return message

        strings_path = Path(spec.origin).with_name("strings.json")
        if not strings_path.is_file():
            return message

        data = json.loads(strings_path.read_text())
        component_message = (
            data.get("exceptions", {}).get(translation_key, {}).get("message")
        )
        if not component_message:
            return message

        component_message = component_message.rstrip(".")
        if not translation_placeholders:
            return component_message

        try:
            return component_message.format(**translation_placeholders)
        except KeyError:
            return component_message

    return async_get_exception_message


def pytest_configure() -> None:
    """Patch the core test fixture to use RemoteHomeAssistant."""
    try:
        import homeassistant.core as ha_core
        import homeassistant.exceptions as ha_exceptions
        import homeassistant.helpers.translation as translation_helper
        import tests.common as tests_common
        import tests.conftest as tests_conftest
    except ImportError:
        return

    if getattr(tests_common, "_hass_client_patched", False):
        return

    original_async_test_home_assistant = tests_common.async_test_home_assistant
    fallback_exception_message = _build_exception_message_fallback(
        translation_helper.async_get_exception_message
    )

    tests_common.HomeAssistant = RemoteHomeAssistant
    ha_core.HomeAssistant = RemoteHomeAssistant
    translation_helper.async_get_exception_message = fallback_exception_message
    ha_exceptions._function_cache["async_get_exception_message"] = (
        fallback_exception_message
    )

    @asynccontextmanager
    async def async_test_home_assistant(*args, **kwargs):
        async with original_async_test_home_assistant(*args, **kwargs) as hass:
            if isinstance(hass, RemoteHomeAssistant):
                await hass.async_setup_remote()
            try:
                yield hass
            finally:
                if isinstance(hass, RemoteHomeAssistant):
                    await hass.async_teardown_remote()

    tests_common.async_test_home_assistant = async_test_home_assistant
    tests_conftest.async_test_home_assistant = async_test_home_assistant
    tests_common._hass_client_patched = True
