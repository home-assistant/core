"""Ldap auth provider."""
from collections import OrderedDict
import logging
import re
import ssl
from typing import Any, Dict, Optional, cast

import ldap3
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

CONF_ACTIVE_DIRECTORY = "active_directory"
CONF_BASE_DN = "base_dn"
CONF_DISABLE_CERT_VALIDATION = "disable_cert_validation"
CONF_DISABLE_TLS = "disable_tls"
CONF_ALLOWED_GROUP_DNS = "allowed_group_dns"
CONF_PORT = "port"
CONF_SERVER = "server"
CONF_TIMEOUT = "timeout"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_ACTIVE_DIRECTORY, default=False): bool,
        vol.Required(CONF_BASE_DN): str,
        vol.Required(CONF_DISABLE_CERT_VALIDATION, default=False): bool,
        vol.Required(CONF_DISABLE_TLS, default=False): bool,
        vol.Required(CONF_PORT, default=636): int,
        vol.Required(CONF_SERVER): str,
        vol.Required(CONF_TIMEOUT, default=10): int,
        vol.Optional(CONF_ALLOWED_GROUP_DNS, default=[]): vol.All(
            cv.ensure_list, [str]
        ),
    },
    extra=vol.PREVENT_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


class LdapError(HomeAssistantError):
    """Raised when an LDAP error has been encountered."""


@AUTH_PROVIDERS.register("ldap")
class LdapAuthProvider(AuthProvider):
    """LDAP auth provider."""

    DEFAULT_TITLE = "LDAP Authentication"

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        return LdapLoginFlow(self)

    @callback
    def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""
        try:
            # Server setup
            tls = ldap3.Tls()
            if self.config[CONF_DISABLE_CERT_VALIDATION]:
                # Disable cert validation
                tls.validate = ssl.CERT_NONE
            server = ldap3.Server(
                self.config[CONF_SERVER],
                port=self.config[CONF_PORT],
                use_ssl=not self.config[CONF_DISABLE_TLS],
                tls=tls,
                connect_timeout=self.config[CONF_TIMEOUT],
                get_info=ldap3.ALL,
            )

            # LDAP bind
            if self.config[CONF_ACTIVE_DIRECTORY]:
                attrs = ["sAMAccountName", "displayName", "memberOf"]
                conn = ldap3.Connection(
                    server, user=username, password=password, authentication=ldap3.NTLM,
                )
            else:
                attrs = ["uid", "displayName", "memberOf"]
                conn = ldap3.Connection(
                    server,
                    user=f"uid={username},{self.config[CONF_BASE_DN]}",
                    password=password,
                    auto_bind=True,
                )

            whoami = conn.extend.standard.who_am_i()

            _LOGGER.debug("Server info: %s", server.info)
            _LOGGER.debug("Connection: %s", conn)
            _LOGGER.debug("whoami: %s", whoami)

            match = re.match("dn: (.+)", whoami, re.IGNORECASE)
            if not match:
                raise LdapError("Unable to determine DN of bind user.")
            dn_self = match.group(1)
            _LOGGER.debug("DN of the logged user: %s", dn_self)

            if not conn.search(
                dn_self,
                "(objectclass=person)",
                size_limit=1,
                time_limit=self.config[CONF_TIMEOUT],
                attributes=attrs,
            ):
                _LOGGER.error("LDAP self search returned no results.")
                raise LdapError
            uid = (
                conn.entries[0].sAMAccountName.value
                if self.config[CONF_ACTIVE_DIRECTORY]
                else conn.entries[0].uid.value
            )
            display_name = conn.entries[0].displayName.value
            _LOGGER.info("Logged in as %s (%s)", display_name, uid)

            if self.config[CONF_ALLOWED_GROUP_DNS]:
                _LOGGER.debug(
                    "Checking if user is a member of any of the following groups: %s",
                    self.config[CONF_ALLOWED_GROUP_DNS],
                )
                user_groups = conn.entries[0].memberOf.value
                _LOGGER.info("User %s is member of %s", uid, user_groups)

                member = False
                for group in self.config[CONF_ALLOWED_GROUP_DNS]:
                    if group.lower() in [g.lower() for g in user_groups]:
                        member = True
                if not member:
                    raise InvalidAuthError(
                        "User %s is not a member of any of the required groups", uid,
                    )

        except ldap3.core.exceptions.LDAPBindError as exc:
            _LOGGER.error("Bind failed: %s", exc)
            raise InvalidAuthError

    async def async_get_or_create_credentials(
        self, flow_result: Dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        username = flow_result["username"]

        for credential in await self.async_credentials():
            if credential.data["username"] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({"username": username})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        return UserMeta(name=credentials.data["username"], is_active=True)


class LdapLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                cast(LdapAuthProvider, self._auth_provider).async_validate_login(
                    user_input["username"], user_input["password"]
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            # FIXME
            except LdapError:
                errors["base"] = "error"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        schema: Dict[str, type] = OrderedDict()
        schema["username"] = str
        schema["password"] = str

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
