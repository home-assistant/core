"""Application credentials platform for Bosch Smart Home Camera.

Bosch's OSS residential app OAuth2 client (`oss_residential_app`) is a
public, non-rotatable client embedded identically in every Android APK
(see `config_flow.py`'s `CLIENT_ID`/`CLIENT_SECRET`) — not a per-user secret
a customer registers themselves. There is no Bosch developer portal where a
user could obtain their own client credentials.

To still satisfy HA-core's `application_credentials` requirement for
OAuth-based Core integrations (this integration is being prepared for
`home-assistant/core` submission), the fixed credential is auto-imported as
the default `ClientCredential` in `async_setup()` (`__init__.py`), the same
pattern used by other Core integrations with a single built-in public OAuth
client (e.g. `overkiz`, `vicare`, `ondilo_ico`). This means:

  * A fresh install works with zero extra user setup — no visit to
    Settings → Application Credentials is required, matching the
    pre-application_credentials UX exactly.
  * An admin COULD still override the credential via Settings →
    Application Credentials if Bosch ever offers per-user client
    registration — `async_get_auth_implementation` below always builds the
    implementation from whatever `ClientCredential` HA-core resolved (the
    auto-imported default, or a user override), not from the module-level
    constants directly.

We implement `async_get_auth_implementation` (not the simpler
`async_get_authorization_server`) because Bosch's Keycloak flow needs PKCE
support and a Bosch-specific display name — `BoschOAuth2Implementation`
already provides both (see `config_flow.py`).
"""

from __future__ import annotations

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
)

from .config_flow import BoschOAuth2Implementation


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return a custom PKCE-capable auth implementation for Bosch SingleKey ID."""
    return BoschOAuth2Implementation(
        hass, credential.client_id, credential.client_secret
    )
