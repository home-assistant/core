"""Ldap auth provider."""
from collections import OrderedDict
import logging
from pathlib import Path
import ssl
from typing import Any, Dict, Optional, cast

import ldap3
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

# Configuration labels
CONF_ALLOWED_GROUP_DNS = "allowed_group_dns"
CONF_BASE_DN = "base_dn"
CONF_BIND_TYPE = "bind_type"
CONF_BIND_TYPE_ANONYMOUS = "anonymous"
CONF_BIND_TYPE_AS_SERVICE_USER = "service-user"
CONF_BIND_TYPE_AS_USER = "user"
CONF_BIND_DN = "bind_dn"
CONF_BIND_PASSWORD = "bind_password"
CONF_CA_CERTS_FILE = "ca_certs_file"
CONF_CERT_VALIDATION = "validate_certificates"
CONF_ENCRYPTION = "encryption"
CONF_ENCRYPTION_LDAPS = "ldaps"
CONF_ENCRYPTION_NONE = "none"
CONF_ENCRYPTION_STARTTLS = "starttls"
CONF_PORT = "port"
CONF_SERVER = "server"
CONF_TIMEOUT = "timeout"
CONF_USERNAME_ATTR = "username_attribute"

# Default values
DEFAULT_CONF_BIND_TYPE = CONF_BIND_TYPE_AS_SERVICE_USER
DEFAULT_CONF_CERT_VALIDATION = True
DEFAULT_CONF_PORT = 636
DEFAULT_CONF_TIMEOUT = 10
DEFAULT_CONF_USERNAME_ATTR = "uid"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Optional(CONF_ALLOWED_GROUP_DNS, default=[]): vol.All(
            cv.ensure_list, [str]
        ),
        vol.Required(CONF_BASE_DN): str,
        vol.Required(CONF_BIND_TYPE, default=DEFAULT_CONF_BIND_TYPE): vol.In(
            [
                CONF_BIND_TYPE_ANONYMOUS,
                CONF_BIND_TYPE_AS_SERVICE_USER,
                CONF_BIND_TYPE_AS_USER,
            ]
        ),
        vol.Optional(CONF_BIND_DN): str,
        vol.Optional(CONF_BIND_PASSWORD): str,
        vol.Optional(CONF_CA_CERTS_FILE, default=None): str,
        vol.Required(CONF_CERT_VALIDATION, default=DEFAULT_CONF_CERT_VALIDATION): bool,
        vol.Required(CONF_ENCRYPTION, default=CONF_ENCRYPTION_LDAPS): vol.In(
            [CONF_ENCRYPTION_LDAPS, CONF_ENCRYPTION_NONE, CONF_ENCRYPTION_STARTTLS]
        ),
        vol.Required(CONF_PORT, default=DEFAULT_CONF_PORT): int,
        vol.Required(CONF_SERVER): str,
        vol.Required(CONF_TIMEOUT, default=DEFAULT_CONF_TIMEOUT): int,
        vol.Required(CONF_USERNAME_ATTR, default=DEFAULT_CONF_USERNAME_ATTR): str,
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
            tls = ldap3.Tls()
            tls.validate = (
                ssl.CERT_REQUIRED
                if self.config[CONF_CERT_VALIDATION]
                else ssl.CERT_NONE
            )

            ca_certs_file = self.config[CONF_CA_CERTS_FILE]
            if ca_certs_file:
                abs_path = None
                path = Path(ca_certs_file)
                if path.is_absolute():
                    abs_path = path
                else:
                    # Relative paths are relative to either cwd, or the config dir.
                    for path_candidate in [
                        Path.cwd().joinpath(path),
                        Path(self.hass.config.path(ca_certs_file)),
                    ]:
                        if path_candidate.exists():
                            abs_path = path_candidate
                            break

                if not abs_path:
                    _LOGGER.error("File %s doesn't exist", ca_certs_file)
                    return
                tls.ca_certs_file = abs_path.resolve()

            encryption = self.config[CONF_ENCRYPTION]
            # Server setup
            server = ldap3.Server(
                self.config[CONF_SERVER],
                port=self.config[CONF_PORT],
                use_ssl=encryption == CONF_ENCRYPTION_LDAPS,
                tls=tls,
                connect_timeout=self.config[CONF_TIMEOUT],
                get_info=ldap3.ALL,
            )

            base_dn = self.config[CONF_BASE_DN]
            bind_type = self.config[CONF_BIND_TYPE]
            bind_as_user = bind_type == CONF_BIND_TYPE_AS_USER
            username_attr = self.config[CONF_USERNAME_ATTR]

            if bind_type == CONF_BIND_TYPE_ANONYMOUS:
                _LOGGER.debug("Binding anonymously")
                conn = ldap3.Connection(server, auto_bind=False)
            else:
                bind_dn = (
                    f"{username_attr}={username},{base_dn}"
                    if bind_as_user
                    else self.config[CONF_BIND_DN]
                )
                bind_password = (
                    password if bind_as_user else self.config[CONF_BIND_PASSWORD]
                )
                _LOGGER.debug("Binding as %s", bind_dn)
                # LDAP bind
                conn = ldap3.Connection(
                    server, user=bind_dn, password=bind_password, auto_bind=False,
                )
            conn.open(read_server_info=False)
            # Upgrade connection with START_TLS if requested.
            if encryption == CONF_ENCRYPTION_STARTTLS:
                conn.start_tls(read_server_info=False)
            conn.bind()

            _LOGGER.debug("Server info: %s", server.info)
            _LOGGER.debug("Connection: %s", conn)

            # Query the directory server for the connecting user
            if not conn.search(
                base_dn,
                f"(&({username_attr}={username})(objectclass=person))",
                size_limit=1,
                time_limit=self.config[CONF_TIMEOUT],
                attributes=[username_attr, "displayName", "memberOf"],
            ):
                _LOGGER.error("LDAP self search returned no results.")
                raise LdapError
            # Get the account name from the directory.
            uid = getattr(conn.entries[0], username_attr).value
            # Full name: Firstname Lastname
            display_name = conn.entries[0].displayName.value
            _LOGGER.info("Found user %s (%s)", uid, display_name)

            # Check group membership
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
                        _LOGGER.debug(
                            "Group membership test passed. The user belongs to one the whitelisted groups."
                        )
                if not member:
                    _LOGGER.debug(
                        "Group membership test failed. The user is a member of NONE of the whitelisted groups."
                    )
                    raise InvalidAuthError(
                        "User {} is not a member of any of the required groups".format(
                            uid
                        )
                    )

            # Check credentials if we haven't done this already
            if not bind_as_user and not conn.rebind(
                user=conn.entries[0].entry_dn, password=password
            ):
                _LOGGER.error("Error in bind %s", conn.result)
                raise InvalidAuthError("Invalid LDAP credentials provided")

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
