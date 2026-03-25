"""Heiman I18N Enhancement.

Provides comprehensive internationalization support with:
- Dynamic language loading
- Multi-level translations (device types, services, properties, enums, events)
- Runtime language switching
- Fallback mechanism
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _read_translation_file(translation_path: Path) -> dict[str, Any]:
    """Read a translation file from disk."""
    with open(translation_path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


class HeimanI18nEnhanced:
    """Enhanced i18n system for Heiman Home integration."""

    # Supported languages
    SUPPORTED_LANGUAGES = {
        "de": "Deutsch",
        "en": "English",
        "es": "Español",
        "fr": "Français",
        "it": "Italiano",
        "ja": "日本語",
        "nl": "Nederlands",
        "pt": "Português",
        "pt-BR": "Português (Brasil)",
        "ru": "Русский",
        "tr": "Türkçe",
        "zh-Hans": "简体中文",
        "zh-Hant": "繁體中文",
    }

    # Default language
    DEFAULT_LANGUAGE = "en"

    def __init__(self, hass: HomeAssistant, language: str = DEFAULT_LANGUAGE):
        """Initialize enhanced i18n system.

        Args:
            hass: Home Assistant instance
            language: Default language code
        """
        self.hass = hass
        self.language = (
            language if language in self.SUPPORTED_LANGUAGES else self.DEFAULT_LANGUAGE
        )
        self._translations: dict[str, dict[str, Any]] = {}
        self._device_translations: dict[str, dict[str, Any]] = {}
        self._property_translations: dict[str, dict[str, Any]] = {}
        self._enum_translations: dict[str, dict[str, Any]] = {}
        self._event_translations: dict[str, dict[str, Any]] = {}
        self._loaded = False

    async def init_async(self) -> None:
        """Initialize i18n system asynchronously."""
        if self._loaded:
            return

        await self._load_language(self.language)
        self._loaded = True
        _LOGGER.info("I18n system initialized with language: %s", self.language)

    async def deinit_async(self) -> None:
        """Deinitialize i18n system."""
        self._translations.clear()
        self._device_translations.clear()
        self._property_translations.clear()
        self._enum_translations.clear()
        self._event_translations.clear()
        self._loaded = False

    async def switch_language(self, language: str) -> bool:
        """Switch to a different language.

        Args:
            language: New language code

        Returns:
            True if successful, False otherwise
        """
        if language not in self.SUPPORTED_LANGUAGES:
            _LOGGER.warning("Unsupported language: %s", language)
            return False

        if language == self.language:
            return True

        self.language = language
        await self._load_language(language)
        _LOGGER.info("Language switched to: %s", language)
        return True

    async def _load_language(self, language: str) -> None:
        """Load translations for a specific language.

        Args:
            language: Language code
        """
        try:
            # Load from translations directory
            translation_path = (
                Path(__file__).parent / "translations" / f"{language}.json"
            )

            if translation_path.exists():
                data = await asyncio.to_thread(_read_translation_file, translation_path)
                self._translations[language] = data
                _LOGGER.debug("Loaded translations for: %s", language)
            # Try fallback to English
            elif language != self.DEFAULT_LANGUAGE:
                _LOGGER.warning(
                    "Translation file not found for %s, falling back to %s",
                    language,
                    self.DEFAULT_LANGUAGE,
                )
                await self._load_language(self.DEFAULT_LANGUAGE)
            else:
                _LOGGER.error("Default translation file not found")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to load translations for %s: %s", language, err)

    def get_translation(
        self,
        key: str,
        default: str | None = None,
        language: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Get a translation by key.

        Args:
            key: Translation key (dot-separated path)
            default: Default value if translation not found
            language: Specific language to use (optional)
            **kwargs: Format arguments for the translation string

        Returns:
            Translated string or default
        """
        lang = language or self.language
        translations = self._translations.get(lang, {})

        if not translations:
            # Try fallback to English
            translations = self._translations.get(self.DEFAULT_LANGUAGE, {})

        # Navigate through nested dict
        result = translations
        for part in key.split("."):
            if isinstance(result, dict):
                result = result.get(part)
            else:
                result = None
                break

        if result is None:
            return default

        # Format with kwargs
        if isinstance(result, str) and kwargs:
            try:
                return result.format(**kwargs)
            except KeyError, ValueError:
                return result

        return result

    def get_device_name_translation(
        self,
        device_type: str,
        model: str | None = None,
        language: str | None = None,
    ) -> str:
        """Translate device type name.

        Args:
            device_type: Device type (e.g., 'temperature-sensor')
            model: Device model (optional)
            language: Language to use

        Returns:
            Translated device name
        """
        # Check device-specific translations
        key = f"device.{device_type}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        # Generate from device type
        return device_type.replace("-", " ").title()

    def get_property_name_translation(
        self,
        property_id: str,
        service: str | None = None,
        language: str | None = None,
    ) -> str:
        """Translate property name.

        Args:
            property_id: Property identifier
            service: Service name (optional)
            language: Language to use

        Returns:
            Translated property name
        """
        # Check property-specific translations
        if service:
            key = f"property.{service}.{property_id}"
            translated = self.get_translation(key, language=language)
            if translated:
                return translated

        key = f"property.{property_id}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        # Fallback to property ID
        return property_id

    def get_enum_translation(
        self,
        property_id: str,
        enum_value: Any,
        language: str | None = None,
    ) -> str:
        """Translate enum value.

        Args:
            property_id: Property identifier
            enum_value: Enum value to translate
            language: Language to use

        Returns:
            Translated enum value
        """
        key = f"enum.{property_id}.{enum_value}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        # Return value as string
        return str(enum_value)

    def get_event_translation(
        self,
        event_type: str,
        language: str | None = None,
    ) -> str:
        """Translate event description.

        Args:
            event_type: Event type identifier
            language: Language to use

        Returns:
            Translated event description
        """
        key = f"event.{event_type}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        return event_type

    def get_service_translation(
        self,
        service_name: str,
        language: str | None = None,
    ) -> str:
        """Translate service name.

        Args:
            service_name: Service name
            language: Language to use

        Returns:
            Translated service name
        """
        key = f"service.{service_name}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        return service_name

    def get_state_translation(
        self,
        entity_domain: str,
        entity_id: str,
        state_value: str,
        language: str | None = None,
    ) -> str:
        """Translate entity state value.

        Args:
            entity_domain: Entity domain (sensor, binary_sensor, etc.)
            entity_id: Entity identifier
            state_value: State value to translate
            language: Language to use

        Returns:
            Translated state value
        """
        key = f"state.{entity_domain}.{entity_id}.{state_value}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        # Try generic state translation
        key = f"state._.{state_value}"
        translated = self.get_translation(key, language=language)

        if translated:
            return translated

        return state_value

    def add_device_translations(
        self,
        device_type: str,
        translations: dict[str, str],
    ) -> None:
        """Add device type translations dynamically.

        Args:
            device_type: Device type
            translations: Dict of language -> translation
        """
        self._device_translations[device_type] = translations

    def add_property_translations(
        self,
        property_id: str,
        translations: dict[str, str],
    ) -> None:
        """Add property translations dynamically.

        Args:
            property_id: Property identifier
            translations: Dict of language -> translation
        """
        self._property_translations[property_id] = translations

    def add_enum_translations(
        self,
        property_id: str,
        enum_values: dict[Any, dict[str, str]],
    ) -> None:
        """Add enum value translations dynamically.

        Args:
            property_id: Property identifier
            enum_values: Dict of value -> {language -> translation}
        """
        self._enum_translations[property_id] = enum_values

    def get_all_supported_languages(self) -> dict[str, str]:
        """Get all supported languages.

        Returns:
            Dict of language code -> language name
        """
        return self.SUPPORTED_LANGUAGES.copy()

    def get_current_language(self) -> str:
        """Get current language.

        Returns:
            Current language code
        """
        return self.language

    def is_language_loaded(self, language: str | None = None) -> bool:
        """Check if a language is loaded.

        Args:
            language: Language to check (default: current language)

        Returns:
            True if loaded, False otherwise
        """
        lang = language or self.language
        return lang in self._translations


class HeimanI18nManager:
    """Manager for multiple i18n instances (multi-home support)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize i18n manager.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._instances: dict[str, HeimanI18nEnhanced] = {}

    def get_or_create_instance(
        self,
        entry_id: str,
        language: str,
    ) -> HeimanI18nEnhanced:
        """Get or create an i18n instance for a config entry.

        Args:
            entry_id: Config entry ID
            language: Language for this instance

        Returns:
            I18n instance
        """
        if entry_id not in self._instances:
            instance = HeimanI18nEnhanced(self.hass, language)
            self._instances[entry_id] = instance
        else:
            instance = self._instances[entry_id]
            if instance.language != language:
                instance.language = language

        return instance

    def remove_instance(self, entry_id: str) -> None:
        """Remove an i18n instance.

        Args:
            entry_id: Config entry ID
        """
        if entry_id in self._instances:
            del self._instances[entry_id]

    async def cleanup_async(self) -> None:
        """Cleanup all instances."""
        for instance in self._instances.values():
            await instance.deinit_async()
        self._instances.clear()
