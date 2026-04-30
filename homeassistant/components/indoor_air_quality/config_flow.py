"""Config flow for the Indoor Air Quality integration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector

from .const import (
    CONF_CO,
    CONF_CO2,
    CONF_HCHO,
    CONF_HUMIDITY,
    CONF_NO2,
    CONF_PM,
    CONF_RADON,
    CONF_SOURCES,
    CONF_STANDARD,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    DEFAULT_STANDARD,
    DOMAIN,
    STANDARDS,
)

_LOGGER = logging.getLogger(__name__)

CONF_SHOW_SOURCE_OPTIONS = "show_source_options"
DEFAULT_NAME = "Indoor Air Quality"

PM_DEVICE_CLASSES = {
    SensorDeviceClass.PM1,
    SensorDeviceClass.PM10,
    SensorDeviceClass.PM25,
}
PM_DEVICE_CLASS_VALUES = {str(device_class) for device_class in PM_DEVICE_CLASSES}

SOURCE_DEVICE_CLASSES = {
    SensorDeviceClass.TEMPERATURE: CONF_TEMPERATURE,
    SensorDeviceClass.HUMIDITY: CONF_HUMIDITY,
    SensorDeviceClass.CO2: CONF_CO2,
    SensorDeviceClass.CO: CONF_CO,
    SensorDeviceClass.NITROGEN_DIOXIDE: CONF_NO2,
}

TVOC_DEVICE_CLASSES = {
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
}
TVOC_DEVICE_CLASS_VALUES = {str(device_class) for device_class in TVOC_DEVICE_CLASSES}

DEVICE_SELECTOR = selector.DeviceSelector(
    selector.DeviceSelectorConfig(
        entity=selector.EntityFilterSelectorConfig(domain=SENSOR_DOMAIN),
    )
)

STANDARD_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(STANDARDS),
        translation_key=CONF_STANDARD,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

# Source configuration options
SOURCE_SELECTORS = {
    CONF_TEMPERATURE: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=SensorDeviceClass.TEMPERATURE,
        )
    ),
    CONF_HUMIDITY: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=SensorDeviceClass.HUMIDITY,
        )
    ),
    CONF_CO2: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=SensorDeviceClass.CO2,
        )
    ),
    CONF_TVOC: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=list(TVOC_DEVICE_CLASSES),
        )
    ),
    CONF_VOC_INDEX: selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
    ),
    CONF_PM: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=list(PM_DEVICE_CLASSES),
            multiple=True,
        )
    ),
    CONF_NO2: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        )
    ),
    CONF_CO: selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN,
            device_class=SensorDeviceClass.CO,
        )
    ),
    CONF_HCHO: selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
    ),
    CONF_RADON: selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
    ),
}


def _source_schema_fields(
    defaults: dict[str, Any] | None = None,
) -> dict[vol.Optional, selector.EntitySelector]:
    """Return flat source selector fields for config and options flows."""
    defaults = defaults or {}

    return {
        vol.Optional(source, default=defaults[source])
        if source in defaults
        else vol.Optional(source): source_selector
        for source, source_selector in SOURCE_SELECTORS.items()
    }


def _has_at_least_one_source(sources: dict[str, Any]) -> bool:
    """Check if at least one source is configured."""
    return any(sources.values())


def _validate_voc_sources(sources: dict[str, Any]) -> dict[str, str]:
    """Validate that only one of TVOC or VOC_INDEX is provided."""
    errors = {}

    if sources.get(CONF_TVOC) and sources.get(CONF_VOC_INDEX):
        errors["base"] = "only_one_voc_sensor"

    return errors


def _clean_sources(sources: dict[str, Any] | None) -> dict[str, Any]:
    """Remove empty source selections."""
    if not sources:
        return {}

    return {key: value for key, value in sources.items() if value}


def _device_name(hass: HomeAssistant, device_id: str | None) -> str | None:
    """Return the best available friendly name for a device."""
    if not device_id:
        return None

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        return None

    return device_entry.name_by_user or device_entry.name


def _sources_from_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return source selections submitted by the user."""
    if CONF_SOURCES in user_input:
        return _clean_sources(user_input.get(CONF_SOURCES))

    return _clean_sources(
        {source: user_input.get(source) for source in SOURCE_SELECTORS}
    )


def _entity_labels(entry: er.RegistryEntry) -> str:
    """Return searchable labels for an entity registry entry."""
    return " ".join(
        str(value).lower().replace("_", " ")
        for value in (
            entry.entity_id,
            entry.name,
            entry.original_name,
            entry.translation_key,
        )
        if value
    )


def _entity_device_classes(entry: er.RegistryEntry) -> set[str]:
    """Return all available device classes for an entity registry entry."""
    return {
        str(device_class)
        for device_class in (entry.device_class, entry.original_device_class)
        if device_class
    }


def _source_key_from_entry(labels: str, device_classes: set[str]) -> str | None:
    """Return a source key for an entity registry entry."""
    for device_class, source_key in SOURCE_DEVICE_CLASSES.items():
        if str(device_class) in device_classes:
            return source_key

    if "hcho" in labels or "formaldehyde" in labels:
        return CONF_HCHO
    if "radon" in labels:
        return CONF_RADON

    return None


def _is_voc_index_entry(labels: str) -> bool:
    """Return whether labels describe a VOC index sensor."""
    return "voc index" in labels or "vocindex" in labels


def _is_tvoc_entry(labels: str, device_classes: set[str]) -> bool:
    """Return whether labels or device classes describe a tVOC sensor."""
    return bool(device_classes & TVOC_DEVICE_CLASS_VALUES) or bool(
        "tvoc" in labels or "volatile organic" in labels
    )


def _sources_from_device(hass: HomeAssistant, device_id: str) -> dict[str, Any]:
    """Build source configuration from sensors attached to a device."""
    entity_registry = er.async_get(hass)
    sources: dict[str, Any] = {}
    pm_sources: list[str] = []
    tvoc_source = None
    voc_index_source = None

    for entry in er.async_entries_for_device(entity_registry, device_id):
        if entry.domain != SENSOR_DOMAIN:
            continue

        labels = _entity_labels(entry)
        device_classes = _entity_device_classes(entry)

        if device_classes & PM_DEVICE_CLASS_VALUES:
            pm_sources.append(entry.entity_id)
            continue

        if labels and not voc_index_source and _is_voc_index_entry(labels):
            voc_index_source = entry.entity_id
            continue

        if _is_tvoc_entry(labels, device_classes):
            tvoc_source = tvoc_source or entry.entity_id
            continue

        if source_key := _source_key_from_entry(labels, device_classes):
            sources.setdefault(source_key, entry.entity_id)

    if pm_sources:
        sources[CONF_PM] = sorted(pm_sources)

    if voc_index_source:
        sources[CONF_VOC_INDEX] = voc_index_source
    elif tvoc_source:
        sources[CONF_TVOC] = tvoc_source

    return sources


def _sources_from_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Build source configuration from a selected device and manual overrides."""
    sources = {}
    if device_id := user_input.get(CONF_DEVICE_ID):
        sources.update(_sources_from_device(hass, device_id))

    sources.update(_sources_from_user_input(user_input))
    return sources


def _unique_id_from_input(user_input: dict[str, Any], name: str) -> str:
    """Return the config entry unique ID for the selected input.

    For a device-based entry the device id is used directly. For a manual
    setup the unique id is a stable hash of the user-provided name so that
    the entry id stays stable even if the user later renames the entry.
    """
    if device_id := user_input.get(CONF_DEVICE_ID):
        return device_id

    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


class IndoorAirQualityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Indoor Air Quality."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._device_id: str | None = None
        self._detected_sources: dict[str, Any] = {}
        self._name = DEFAULT_NAME
        self._standard: str = DEFAULT_STANDARD

    async def _async_create_config_entry(
        self,
        user_input: dict[str, Any],
        sources: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Validate input and create a config entry."""
        errors = {}

        if not _has_at_least_one_source(sources):
            errors["base"] = (
                "no_matching_sources"
                if user_input.get(CONF_DEVICE_ID)
                else "no_sources"
            )
        else:
            errors.update(_validate_voc_sources(sources))

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(),
                errors=errors,
            )

        name = (
            user_input.get(CONF_NAME)
            or _device_name(self.hass, user_input.get(CONF_DEVICE_ID))
            or DEFAULT_NAME
        )

        data: dict[str, Any] = {
            CONF_SOURCES: sources,
            CONF_STANDARD: user_input.get(CONF_STANDARD, DEFAULT_STANDARD),
        }
        if device_id := user_input.get(CONF_DEVICE_ID):
            data[CONF_DEVICE_ID] = device_id

        await self.async_set_unique_id(_unique_id_from_input(user_input, name))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data=data,
        )

    def _user_schema(self) -> vol.Schema:
        """Return the first-step config schema."""
        return vol.Schema(
            {
                vol.Optional(CONF_DEVICE_ID): DEVICE_SELECTOR,
                vol.Optional(
                    CONF_STANDARD, default=DEFAULT_STANDARD
                ): STANDARD_SELECTOR,
                vol.Optional(
                    CONF_SHOW_SOURCE_OPTIONS,
                    default=False,
                ): selector.BooleanSelector(),
            }
        )

    def _sources_schema(self) -> vol.Schema:
        """Return the manual source selection schema."""
        return vol.Schema(
            {
                vol.Optional(CONF_NAME, default=self._name): str,
                **_source_schema_fields(self._detected_sources),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._standard = user_input.get(CONF_STANDARD, DEFAULT_STANDARD)
            device_id = user_input.get(CONF_DEVICE_ID)
            sources = _sources_from_input(self.hass, user_input)

            if _sources_from_user_input(user_input):
                return await self._async_create_config_entry(user_input, sources)

            if user_input.get(CONF_SHOW_SOURCE_OPTIONS):
                self._device_id = device_id
                self._detected_sources = sources
                self._name = _device_name(self.hass, device_id) or DEFAULT_NAME
                return await self.async_step_sources()

            if not device_id:
                errors["base"] = "device_or_sources"
            else:
                return await self._async_create_config_entry(user_input, sources)

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the optional manual source selection step."""
        errors = {}

        if user_input is not None:
            sources = self._detected_sources | _sources_from_user_input(user_input)
            errors.update(_validate_voc_sources(sources))

            if not _has_at_least_one_source(sources):
                errors["base"] = "no_sources"

            if not errors:
                return await self._async_create_config_entry(
                    {
                        CONF_NAME: user_input.get(CONF_NAME) or self._name,
                        CONF_DEVICE_ID: self._device_id,
                        CONF_STANDARD: self._standard,
                    },
                    sources,
                )

        return self.async_show_form(
            step_id="sources",
            data_schema=self._sources_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to reconfigure standard and sources of an entry."""
        entry = self._get_reconfigure_entry()
        current_sources = entry.data.get(CONF_SOURCES, {})
        current_standard = entry.data.get(CONF_STANDARD, DEFAULT_STANDARD)

        errors: dict[str, str] = {}

        if user_input is not None:
            sources = _sources_from_user_input(user_input)

            if not _has_at_least_one_source(sources):
                errors["base"] = "no_sources"
            else:
                errors.update(_validate_voc_sources(sources))

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_SOURCES: sources,
                        CONF_STANDARD: user_input.get(CONF_STANDARD, current_standard),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_STANDARD, default=current_standard
                    ): STANDARD_SELECTOR,
                    **_source_schema_fields(current_sources),
                }
            ),
            errors=errors,
        )
