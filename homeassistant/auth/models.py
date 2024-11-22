"""Auth models."""

from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address
import secrets
from typing import Any, NamedTuple
import uuid

import attr
from attr import Attribute
from attr.setters import validate
from propcache import cached_property

from homeassistant.const import __version__
from homeassistant.data_entry_flow import FlowContext, FlowResult
from homeassistant.util import dt as dt_util

from . import permissions as perm_mdl
from .const import GROUP_ID_ADMIN

TOKEN_TYPE_NORMAL = "normal"
TOKEN_TYPE_SYSTEM = "system"
TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN = "long_lived_access_token"


class AuthFlowContext(FlowContext, total=False):
    """Typed context dict for auth flow."""

    credential_only: bool
    ip_address: IPv4Address | IPv6Address
    redirect_uri: str


AuthFlowResult = FlowResult[AuthFlowContext, tuple[str, str]]


@attr.s(slots=True)
class Group:
    """A group."""

    name: str | None = attr.ib()
    policy: perm_mdl.PolicyType = attr.ib()
    id: str = attr.ib(factory=lambda: uuid.uuid4().hex)
    system_generated: bool = attr.ib(default=False)


def _handle_permissions_change(self: User, user_attr: Attribute, new: Any) -> Any:
    """Handle a change to a permissions."""
    self.invalidate_cache()
    return validate(self, user_attr, new)


@attr.s(slots=False)
class User:
    """A user."""

    name: str | None = attr.ib()
    perm_lookup: perm_mdl.PermissionLookup = attr.ib(eq=False, order=False)
    id: str = attr.ib(factory=lambda: uuid.uuid4().hex)
    is_owner: bool = attr.ib(default=False, on_setattr=_handle_permissions_change)
    is_active: bool = attr.ib(default=False, on_setattr=_handle_permissions_change)
    system_generated: bool = attr.ib(default=False)
    local_only: bool = attr.ib(default=False)

    groups: list[Group] = attr.ib(
        factory=list, eq=False, order=False, on_setattr=_handle_permissions_change
    )

    # List of credentials of a user.
    credentials: list[Credentials] = attr.ib(factory=list, eq=False, order=False)

    # Tokens associated with a user.
    refresh_tokens: dict[str, RefreshToken] = attr.ib(
        factory=dict, eq=False, order=False
    )

    @cached_property
    def permissions(self) -> perm_mdl.AbstractPermissions:
        """Return permissions object for user."""
        if self.is_owner:
            return perm_mdl.OwnerPermissions
        return perm_mdl.PolicyPermissions(
            perm_mdl.merge_policies([group.policy for group in self.groups]),
            self.perm_lookup,
        )

    @cached_property
    def is_admin(self) -> bool:
        """Return if user is part of the admin group."""
        return self.is_owner or (
            self.is_active and any(gr.id == GROUP_ID_ADMIN for gr in self.groups)
        )

    def invalidate_cache(self) -> None:
        """Invalidate permission and is_admin cache."""
        for attr_to_invalidate in ("permissions", "is_admin"):
            self.__dict__.pop(attr_to_invalidate, None)


@attr.s(slots=True)
class RefreshToken:
    """RefreshToken for a user to grant new access tokens."""

    user: User = attr.ib()
    client_id: str | None = attr.ib()
    access_token_expiration: timedelta = attr.ib()
    client_name: str | None = attr.ib(default=None)
    client_icon: str | None = attr.ib(default=None)
    token_type: str = attr.ib(
        default=TOKEN_TYPE_NORMAL,
        validator=attr.validators.in_(
            (TOKEN_TYPE_NORMAL, TOKEN_TYPE_SYSTEM, TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN)
        ),
    )
    id: str = attr.ib(factory=lambda: uuid.uuid4().hex)
    created_at: datetime = attr.ib(factory=dt_util.utcnow)
    token: str = attr.ib(factory=lambda: secrets.token_hex(64))
    jwt_key: str = attr.ib(factory=lambda: secrets.token_hex(64))

    last_used_at: datetime | None = attr.ib(default=None)
    last_used_ip: str | None = attr.ib(default=None)

    expire_at: float | None = attr.ib(default=None)

    credential: Credentials | None = attr.ib(default=None)

    version: str | None = attr.ib(default=__version__)


@attr.s(slots=True)
class Credentials:
    """Credentials for a user on an auth provider."""

    auth_provider_type: str = attr.ib()
    auth_provider_id: str | None = attr.ib()

    # Allow the auth provider to store data to represent their auth.
    data: dict = attr.ib()

    id: str = attr.ib(factory=lambda: uuid.uuid4().hex)
    is_new: bool = attr.ib(default=True)


class UserMeta(NamedTuple):
    """User metadata."""

    name: str | None
    is_active: bool
    group: str | None = None
    local_only: bool | None = None
