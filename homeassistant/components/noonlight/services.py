"""Service registration and handlers for the Noonlight integration.

Services are domain-level (registered once, shared across config entries). The
optional ``account`` field selects which entry/coordinator handles the call;
when only one entry is configured it can be omitted.
"""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ALL_NOONLIGHT_SERVICES,
    ATTR_ACCOUNT,
    ATTR_ENTRY_DELAY,
    ATTR_INSTRUCTIONS,
    ATTR_REASON,
    CONF_SERVICES_GRANTED,
    DISPATCH_SERVICE_MAP,
    DOMAIN,
    MAX_ENTRY_DELAY,
    MIN_ENTRY_DELAY,
    SVC_CANCEL,
    SVC_TEST_DISPATCH,
)
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator

_LOGGER = logging.getLogger(__name__)

_DISPATCH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_DELAY): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_ENTRY_DELAY, max=MAX_ENTRY_DELAY)
        ),
        vol.Optional(ATTR_INSTRUCTIONS): cv.string,
        vol.Optional(ATTR_ACCOUNT): cv.string,
    }
)

_CANCEL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_REASON): cv.string,
        vol.Optional(ATTR_ACCOUNT): cv.string,
    }
)

_TEST_SCHEMA = vol.Schema({vol.Optional(ATTR_ACCOUNT): cv.string})


def _resolve_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> NoonlightCoordinator:
    """Pick the coordinator targeted by a service call.

    Services are domain-level, so the candidate coordinators are discovered by
    iterating the loaded config entries and reading their ``runtime_data``.
    """
    entries: list[NoonlightConfigEntry] = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not entries:
        raise ServiceValidationError("No Noonlight accounts are configured")

    account = call.data.get(ATTR_ACCOUNT)
    if account is not None:
        entry = next(
            (e for e in entries if e.entry_id == account),
            None,
        )
        if entry is None:
            # Allow matching by human title as a convenience.
            entry = next(
                (e for e in entries if e.title == account),
                None,
            )
        if entry is None:
            raise ServiceValidationError(f"No Noonlight account matches '{account}'")
        return entry.runtime_data

    if len(entries) > 1:
        raise ServiceValidationError(
            "Multiple Noonlight accounts configured; specify 'account'"
        )
    return entries[0].runtime_data


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all Noonlight services (idempotent)."""
    if hass.services.has_service(DOMAIN, SVC_CANCEL):
        return  # already registered

    for service_name, noonlight_services in DISPATCH_SERVICE_MAP.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            _make_dispatch_handler(hass, list(noonlight_services)),
            schema=_DISPATCH_SCHEMA,
        )

    hass.services.async_register(
        DOMAIN, SVC_CANCEL, _make_cancel_handler(hass), schema=_CANCEL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SVC_TEST_DISPATCH,
        _make_test_handler(hass),
        schema=_TEST_SCHEMA,
    )


def _make_dispatch_handler(hass: HomeAssistant, requested: list[str]):
    async def _handle(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        granted = coordinator.entry.options.get(
            CONF_SERVICES_GRANTED, ALL_NOONLIGHT_SERVICES
        )
        services = [svc for svc in requested if svc in granted]
        if not services:
            raise ServiceValidationError(
                "None of the requested Noonlight services are granted for "
                f"account '{coordinator.entry.title}'"
            )
        if len(services) < len(requested):
            _LOGGER.warning(
                "Noonlight dispatch limited to granted services: %s",
                ", ".join(services),
            )
        await coordinator.async_dispatch(
            services,
            call.data.get(ATTR_ENTRY_DELAY),
            call.data.get(ATTR_INSTRUCTIONS),
        )

    return _handle


def _make_cancel_handler(hass: HomeAssistant):
    async def _handle(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        await coordinator.async_cancel(call.data.get(ATTR_REASON))

    return _handle


def _make_test_handler(hass: HomeAssistant):
    async def _handle(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        try:
            await coordinator.async_test_dispatch()
        except Exception as err:
            raise HomeAssistantError(f"Noonlight test dispatch failed: {err}") from err

    return _handle
