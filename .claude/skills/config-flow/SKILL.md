# Config Flow

This skill covers implementing configuration flows for Home Assistant integrations.

## When to Use

- Adding UI configuration to an integration
- Implementing reauthentication or reconfiguration
- Adding device discovery support

## Core Requirements

- All integrations must support configuration via UI
- Set `"config_flow": true` in `manifest.json`
- Always set `VERSION = 1` and `MINOR_VERSION = 1`

## Basic Config Flow

```python
"""Config flow for My Integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_API_KEY

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class MyIntegrationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for My Integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Test connection
            try:
                client = MyClient(user_input[CONF_HOST], user_input[CONF_API_KEY])
                device_info = await client.async_get_info()
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                # Set unique ID and prevent duplicates
                await self.async_set_unique_id(device_info.serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_info.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

## Data Storage

- **ConfigEntry.data**: Connection-critical config (host, credentials)
- **ConfigEntry.options**: Non-critical settings

## Unique ID Management

```python
# Set unique ID from device identifier
await self.async_set_unique_id(device.serial_number)

# Prevent duplicate configurations
self._abort_if_unique_id_configured()

# Or update existing entry with new data
self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

# For data-based matching (when no unique ID available)
self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
```

## Config Entry Naming

- Do NOT allow users to set config entry names in config flows
- Names are automatically generated or can be customized later in UI
- Exception: Helper integrations MAY allow custom names

## Reauthentication

```python
async def async_step_reauth(
    self, entry_data: Mapping[str, Any]
) -> ConfigFlowResult:
    """Handle reauthentication."""
    return await self.async_step_reauth_confirm()

async def async_step_reauth_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Handle reauthentication confirmation."""
    errors: dict[str, str] = {}

    if user_input is not None:
        try:
            client = MyClient(
                self._get_reauth_entry().data[CONF_HOST],
                user_input[CONF_API_KEY],
            )
            user_info = await client.async_get_user()
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        else:
            # Verify same account
            await self.async_set_unique_id(user_info.user_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")

            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
            )

    return self.async_show_form(
        step_id="reauth_confirm",
        data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
        errors=errors,
    )
```

## Reconfiguration

```python
async def async_step_reconfigure(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Handle reconfiguration."""
    errors: dict[str, str] = {}

    if user_input is not None:
        try:
            client = MyClient(user_input[CONF_HOST])
            device_info = await client.async_get_info()
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        else:
            # Prevent changing to different device
            await self.async_set_unique_id(device_info.serial)
            self._abort_if_unique_id_mismatch(reason="wrong_device")

            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=user_input,
            )

    return self.async_show_form(
        step_id="reconfigure",
        data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
        errors=errors,
    )
```

## strings.json

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to device",
        "data": {
          "host": "Host",
          "api_key": "API key"
        },
        "data_description": {
          "host": "Hostname or IP address of your device",
          "api_key": "API key from the device settings"
        }
      },
      "reauth_confirm": {
        "title": "Reauthenticate",
        "description": "Please enter your new API key for {name}",
        "data": {
          "api_key": "API key"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Device is already configured",
      "wrong_account": "The credentials belong to a different account",
      "wrong_device": "Cannot change to a different device"
    }
  }
}
```

## Exception Handling

- Bare exceptions (`except Exception:`) are allowed in config flows for robustness
- Always provide user-friendly error messages
- Define all errors in `strings.json` under `config.error`

## Related Skills

- `device-discovery` - Add discovery support to config flow
- `write-tests` - 100% config flow test coverage required
