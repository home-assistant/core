"""Application credentials platform for the OneDrive for Business integration."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import contextvars

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_tenant_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "onedrive_for_business_tenant_id"
)


@contextmanager
def tenant_id_context(tenant_id: str) -> Generator[None]:
    """Context manager for setting the active tenant ID."""
    token = _tenant_id_context.set(tenant_id)
    try:
        yield
    finally:
        _tenant_id_context.reset(token)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    tenant_id = _tenant_id_context.get()
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE.format(tenant_id=tenant_id),
        token_url=OAUTH2_TOKEN.format(tenant_id=tenant_id),
    )
