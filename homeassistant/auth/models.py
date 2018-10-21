"""Auth models."""
from datetime import datetime, timedelta
from typing import Dict, List, NamedTuple, Optional  # noqa: F401
import uuid

import attr

from homeassistant.util import dt as dt_util

from .util import generate_secret

TOKEN_TYPE_NORMAL = 'normal'
TOKEN_TYPE_SYSTEM = 'system'
TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN = 'long_lived_access_token'


@attr.s(slots=True)
class User:
    """A user."""

    name = attr.ib(type=str)  # type: Optional[str]
    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    is_owner = attr.ib(type=bool, default=False)
    is_active = attr.ib(type=bool, default=False)
    system_generated = attr.ib(type=bool, default=False)

    # List of credentials of a user.
    credentials = attr.ib(
        type=list, factory=list, cmp=False
    )  # type: List[Credentials]

    # Tokens associated with a user.
    refresh_tokens = attr.ib(
        type=dict, factory=dict, cmp=False
    )  # type: Dict[str, RefreshToken]


@attr.s(slots=True)
class RefreshToken:
    """RefreshToken for a user to grant new access tokens."""

    user = attr.ib(type=User)
    client_id = attr.ib(type=Optional[str])
    access_token_expiration = attr.ib(type=timedelta)
    client_name = attr.ib(type=Optional[str], default=None)
    client_icon = attr.ib(type=Optional[str], default=None)
    token_type = attr.ib(type=str, default=TOKEN_TYPE_NORMAL,
                         validator=attr.validators.in_((
                             TOKEN_TYPE_NORMAL, TOKEN_TYPE_SYSTEM,
                             TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN)))
    id = attr.ib(type=str, factory=lambda: uuid.uuid4().hex)
    created_at = attr.ib(type=datetime, factory=dt_util.utcnow)
    token = attr.ib(type=str, factory=lambda: generate_secret(64))
    jwt_key = attr.ib(type=str, factory=lambda: generate_secret(64))

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


UserMeta = NamedTuple("UserMeta",
                      [('name', Optional[str]), ('is_active', bool)])
