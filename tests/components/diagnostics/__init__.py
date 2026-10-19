"""Compatibility imports for the Home Assistant pytest helpers."""

from pytest_homeassistant.components.diagnostics import (
    DOMAIN as DOMAIN,
    ClientSessionGenerator as ClientSessionGenerator,
    ConfigEntry as ConfigEntry,
    DeviceEntry as DeviceEntry,
    HomeAssistant as HomeAssistant,
    HTTPStatus as HTTPStatus,
    JsonObjectType as JsonObjectType,
    _get_diagnostics_for_config_entry as _get_diagnostics_for_config_entry,
    _get_diagnostics_for_device as _get_diagnostics_for_device,
    async_setup_component as async_setup_component,
    cast as cast,
    get_diagnostics_for_config_entry as get_diagnostics_for_config_entry,
    get_diagnostics_for_device as get_diagnostics_for_device,
)
