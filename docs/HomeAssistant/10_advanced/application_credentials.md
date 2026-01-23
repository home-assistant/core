---
title: "Application credentials"
---

Integrations may support [Configuration via OAuth2](/docs/config_entries_config_flow_handler#configuration-via-oauth2) allowing
users to link their accounts. Integrations may add a `application_credentials.py` file and implement the functions described below.

OAuth2 requires credentials that are shared between an application and provider. In Home Assistant, integration specific OAuth2 credentials are  provided using one or more approaches:

- *Local OAuth with Application Credentials Component*: Users create their own credentials with the cloud provider, often acting as an application developer, and register the credentials with Home Assistant and the integration. This approach is *required* by all integrations that support OAuth2.
- *Cloud Account Linking with Cloud Component*: Nabu Casa registers credentials with the cloud provider, providing a seamless user experience. This approach provides a seamless user experience and is *recommended* ([more info](/docs/config_entries_config_flow_handler#configuration-via-oauth2)).

## Adding support

Integrations support application credentials by adding a dependency on the `application_credentials` component in the `manifest.json`:
```json
{
  ...
  "dependencies": ["application_credentials"],
  ...
}
```

Then add a file in the integration folder called `application_credentials.py`  and implement the following:

```python
from homeassistant.core import HomeAssistant
from homeassistant.components.application_credentials import AuthorizationServer


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url="https://example.com/auth",
        token_url="https://example.com/oauth2/v4/token"
    )
```

### AuthorizationServer

An `AuthorizationServer` represents the [OAuth2 Authorization server](https://datatracker.ietf.org/doc/html/rfc6749) used for an integration.

| Name          | Type |                                                                                                    | Description |
| ------------- | ---- | -------------------------------------------------------------------------------------------------- | ----------- |
| authorize_url | str  | **Required** | The OAuth authorize URL that the user is redirected to during the configuration flow. |
| token_url     | str  | **Required** | The URL used for obtaining an access token.                                           |

### Custom OAuth2 Implementations

Integrations may alternatively provide a custom `AbstractOAuth2Implementation` in `application_credentials.py` like the following:

```python
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.components.application_credentials import AuthImplementation, AuthorizationServer, ClientCredential


class OAuth2Impl(AuthImplementation):
    """Custom OAuth2 implementation."""
    # ... Override AbstractOAuth2Implementation details

async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    return OAuth2Impl(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url="https://example.com/auth",
            token_url="https://example.com/oauth2/v4/token"
        )
    )
```

### Authorization flow with PKCE Support

If you want to support [PKCE](https://www.rfc-editor.org/rfc/rfc7636) you can return the `LocalOAuth2ImplementationWithPkce` in `application_credentials.py` as follows:

```python
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation, LocalOAuth2ImplementationWithPkce
from homeassistant.components.application_credentials import AuthImplementation, ClientCredential


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    return LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        authorize_url="https://example.com/auth",
        token_url="https://example.com/oauth2/v4/token",
        client_secret=credential.client_secret, # optional `""` is default
        code_verifier_length=128 # optional
    )
```

## Import YAML credentials

Credentials may be imported by integrations that used to accept YAML credentials using the import API `async_import_client_credential` provided by the application credentials integration.

Here is an example from an integration that used to accept YAML credentials:

```python
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)

# Example configuration.yaml schema for an integration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    if DOMAIN not in config:
        return True

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
        ),
    )
```

New integrations should not accept credentials in configuration.yaml as users
can instead enter credentials in the Application Credentials user interface.

### ClientCredential

A `ClientCredential` represents a client credential provided by the user.

| Name          | Type |                                                                           | Description |
| ------------- | ---- | ------------------------------------------------------------------------- | ----------- |
| client_id     | str  | **Required** | The OAuth Client ID provided by the user.     |
| client_secret | str  | **Required** | The OAuth Client Secret provided by the user. |

## Translations

Translations for Application Credentials are defined under the `application_credentials` key in the component translation file `strings.json`. As an example:

```json
{
    "application_credentials": {
        "description": "Navigate to the [developer console]({console_url}) to create credentials then enter them below.",
    }
}
```

You may optionally add description placeholder keys that are added to the message by adding a new method in `application_credentials.py` like the following:

```python
from homeassistant.core import HomeAssistant

async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "console_url": "https://example.com/developer/console",
    }
```

While developing locally, you will need to run `python3 -m script.translations develop` to see changes made to `strings.json` [More info on translating Home Assistant.](translations.md)
