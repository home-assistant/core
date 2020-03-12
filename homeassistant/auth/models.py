"""Auth models."""
from datetime import datetime, timedelta
import secrets
from typing import Dict, List, NamedTuple, Optional
import uuid

import attr

from homeassistant.util import dt as dt_util

from . import permissions as perm_mdl
from .const import GROUP_ID_ADMIN

TOKEN_TYPE_NORMAL = "normal"
TOKEN_TYPE_SYSTEM = "system"
TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN = "long_lived_access_token"


@attr.s(slots=True)
class Group:
    """A group."""

    name = attr.ib(type=Optional[str])
    policy = attr.ib(type=perm_mdl.PolicyType)
    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    system_generated = attr.ib(type=bool, default=False)


@attr.s(slots=True)
class User:
    """A user."""

    name = attr.ib(type=Optional[str])
    perm_lookup = attr.ib(type=perm_mdl.PermissionLookup, eq=False, order=False)
    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    is_owner = attr.ib(type=bool, default=False)
    is_active = attr.ib(type=bool, default=False)
    system_generated = attr.ib(type=bool, default=False)

    groups = attr.ib(type=List[Group], factory=list, eq=False, order=False)

    # List of credentials of a user.
    credentials = attr.ib(type=List["Credentials"], factory=list, eq=False, order=False)

    # Tokens associated with a user.
    refresh_tokens = attr.ib(
        type=Dict[str, "RefreshToken"], factory=dict, eq=False, order=False
    )

    _permissions = attr.ib(
        type=Optional[perm_mdl.PolicyPermissions],
        init=False,
        eq=False,
        order=False,
        default=None,
    )

    @property
    def permissions(self) -> perm_mdl.AbstractPermissions:
        """Return permissions object for user."""
        if self.is_owner:
            return perm_mdl.OwnerPermissions

        if self._permissions is not None:
            return self._permissions

        self._permissions = perm_mdl.PolicyPermissions(
            perm_mdl.merge_policies([group.policy for group in self.groups]),
            self.perm_lookup,
        )

        return self._permissions

    @property
    def is_admin(self) -> bool:
        """Return if user is part of the admin group."""
        if self.is_owner:
            return True

        return self.is_active and any(gr.id == GROUP_ID_ADMIN for gr in self.groups)

    def invalidate_permission_cache(self) -> None:
        """Invalidate permission cache."""
        self._permissions = None


@attr.s(slots=True)
class RefreshToken:
    """RefreshToken for a user to grant new access tokens."""

    user = attr.ib(type=User)
    client_id = attr.ib(type=Optional[str])
    access_token_expiration = attr.ib(type=timedelta)
    client_name = attr.ib(type=Optional[str], default=None)
    client_icon = attr.ib(type=Optional[str], default=None)
    token_type = attr.ib(
        type=str,
        default=TOKEN_TYPE_NORMAL,
        validator=attr.validators.in_(
            (TOKEN_TYPE_NORMAL, TOKEN_TYPE_SYSTEM, TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN)
        ),
    )
    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    created_at = attr.ib(type=datetime, factory=dt_util.utcnow)
    token = attr.ib(type=str, factory=lambda: secrets.token_hex(64))
    jwt_key = attr.ib(type=str, factory=lambda: secrets.token_hex(64))

    last_used_at = attr.ib(type=Optional[datetime], default=None)
    last_used_ip = attr.ib(type=Optional[str], default=None)


@attr.s(slots=True)
class Credentials:
    """Credentials for a user on an auth provider."""

    auth_provider_type = attr.ib(type=str)
    auth_provider_id = attr.ib(type=Optional[str])

    # Allow the auth provider to store data to represent their auth.
    data = attr.ib(type=dict)

    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    is_new = attr.ib(type=bool, default=True)


UserMeta = NamedTuple("UserMeta", [("name", Optional[str]), ("is_active", bool)])
