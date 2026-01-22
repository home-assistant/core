# Config Flow Reference

Configuration flows allow users to set up integrations via the UI.

## Basic Config Flow

```python
"""Config flow for My Integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_API_KEY
from homeassistant.helpers.selector import TextSelector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_API_KEY): TextSelector(),
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
            try:
                # Test connection
                client = MyClient(user_input[CONF_HOST], user_input[CONF_API_KEY])
                info = await client.get_device_info()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID and abort if already configured
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

## Version Control

Always set version numbers:

```python
VERSION = 1        # Bump for breaking changes requiring migration
MINOR_VERSION = 1  # Bump for backward-compatible changes
```

## Unique ID Management

```python
# Set unique ID and abort if exists
await self.async_set_unique_id(device_serial)
self._abort_if_unique_id_configured()

# Or abort if data matches (when no unique ID available)
self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
```

## Reauthentication Flow

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
                user_input[CONF_API_KEY]
            )
            info = await client.get_device_info()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info.serial_number)
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

## Reconfiguration Flow

```python
async def async_step_reconfigure(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Handle reconfiguration."""
    errors: dict[str, str] = {}
    reconfigure_entry = self._get_reconfigure_entry()

    if user_input is not None:
        try:
            client = MyClient(user_input[CONF_HOST], reconfigure_entry.data[CONF_API_KEY])
            info = await client.get_device_info()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            await self.async_set_unique_id(info.serial_number)
            self._abort_if_unique_id_mismatch(reason="wrong_device")
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates={CONF_HOST: user_input[CONF_HOST]},
            )

    return self.async_show_form(
        step_id="reconfigure",
        data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=reconfigure_entry.data[CONF_HOST]): str
        }),
        errors=errors,
    )
```

## Discovery Flows

### Zeroconf Discovery

```python
async def async_step_zeroconf(
    self, discovery_info: ZeroconfServiceInfo
) -> ConfigFlowResult:
    """Handle zeroconf discovery."""
    serial = discovery_info.properties.get("serialno")
    if not serial:
        return self.async_abort(reason="no_serial")

    await self.async_set_unique_id(serial)
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: str(discovery_info.host)}
    )

    self._discovered_host = str(discovery_info.host)
    self._discovered_name = discovery_info.name.removesuffix("._mydevice._tcp.local.")

    return await self.async_step_discovery_confirm()

async def async_step_discovery_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Confirm discovery."""
    if user_input is not None:
        return self.async_create_entry(
            title=self._discovered_name,
            data={CONF_HOST: self._discovered_host},
        )

    self._set_confirm_only()
    return self.async_show_form(
        step_id="discovery_confirm",
        description_placeholders={"name": self._discovered_name},
    )
```

## strings.json for Config Flow

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to device",
        "description": "Enter your device credentials.",
        "data": {
          "host": "Host",
          "api_key": "API key"
        }
      },
      "reauth_confirm": {
        "title": "Reauthenticate",
        "description": "Please enter a new API key for {name}.",
        "data": {
          "api_key": "API key"
        }
      },
      "discovery_confirm": {
        "title": "Discovered device",
        "description": "Do you want to set up {name}?"
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Device is already configured",
      "wrong_account": "Wrong account",
      "wrong_device": "Wrong device"
    }
  }
}
```

## Key Rules

1. **Never allow user-configurable entry names** (except helper integrations)
2. **Always test connection** before creating entry
3. **Always set unique ID** when possible
4. **Handle all exceptions** - bare `except Exception:` is allowed in config flows
5. **100% test coverage required** for all flow paths
