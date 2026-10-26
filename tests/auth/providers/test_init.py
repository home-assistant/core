"""Tests for the auth provider base classes."""

import importlib
import pkgutil
from typing import get_origin, get_type_hints

from homeassistant.auth import providers
from homeassistant.auth.providers import AUTH_PROVIDERS, MfaLoginFlow


def test_login_flows_ask_for_mfa() -> None:
    """Test every login flow asks for MFA, except the trusted networks one.

    A provider must not quietly drop the second factor by picking the wrong
    login flow base class.
    """
    for module in pkgutil.iter_modules(providers.__path__):
        importlib.import_module(f"{providers.__name__}.{module.name}")

    login_flows = {
        provider_type: get_type_hints(provider.async_login_flow)["return"]
        for provider_type, provider in AUTH_PROVIDERS.items()
    }

    assert {
        provider_type
        for provider_type, login_flow in login_flows.items()
        if not issubclass(get_origin(login_flow) or login_flow, MfaLoginFlow)
    } == {"trusted_networks"}
