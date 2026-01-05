# Skill: Add Config Flow

Use this skill when implementing or extending config flows for a Home Assistant integration.

## Workflow

### Step 1: Set up manifest

In `manifest.json`:
```json
{
  "config_flow": true
}
```

### Step 2: Create config_flow.py

```python
"""Config flow for My Integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_API_KEY

from .const import DOMAIN


class MyConfigFlow(ConfigFlow, domain=DOMAIN):
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
                info = await client.get_info()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # Allowed in config flow
                errors["base"] = "unknown"
            else:
                # Set unique ID and check for duplicates
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors,
        )
```

### Step 3: Add strings.json

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to device",
        "description": "Enter the connection details.",
        "data": {
          "host": "Host",
          "api_key": "API key"
        },
        "data_description": {
          "host": "IP address or hostname",
          "api_key": "Found in device settings"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Device is already configured"
    }
  }
}
```

### Step 4: Add reauthentication (Silver+)

```python
async def async_step_reauth(
    self, entry_data: Mapping[str, Any]
) -> ConfigFlowResult:
    """Handle reauthentication."""
    return await self.async_step_reauth_confirm()

async def async_step_reauth_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Confirm reauthentication."""
    errors: dict[str, str] = {}

    if user_input is not None:
        reauth_entry = self._get_reauth_entry()
        try:
            client = MyClient(
                reauth_entry.data[CONF_HOST],
                user_input[CONF_API_KEY]
            )
            info = await client.get_info()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            await self.async_set_unique_id(info.serial)
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                reauth_entry,
                data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
            )

    return self.async_show_form(
        step_id="reauth_confirm",
        data_schema=vol.Schema({
            vol.Required(CONF_API_KEY): str,
        }),
        errors=errors,
    )
```

### Step 5: Add reconfiguration (Silver+)

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
            info = await client.get_info()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            await self.async_set_unique_id(info.serial)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates={CONF_HOST: user_input[CONF_HOST]},
            )

    return self.async_show_form(
        step_id="reconfigure",
        data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=reconfigure_entry.data[CONF_HOST]): str,
        }),
        errors=errors,
    )
```

### Step 6: Add discovery (optional)

For zeroconf discovery, add to manifest:
```json
{
  "zeroconf": ["_mydevice._tcp.local."]
}
```

Add discovery handler:
```python
async def async_step_zeroconf(
    self, discovery_info: ZeroconfServiceInfo
) -> ConfigFlowResult:
    """Handle zeroconf discovery."""
    await self.async_set_unique_id(discovery_info.properties["serial"])
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: str(discovery_info.ip_address)}
    )

    self._discovered_host = str(discovery_info.ip_address)
    self._discovered_name = discovery_info.name.removesuffix("._mydevice._tcp.local.")

    return await self.async_step_discovery_confirm()

async def async_step_discovery_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Confirm discovery."""
    if user_input is not None:
        return self.async_create_entry(
            title=self._discovered_name,
            data={
                CONF_HOST: self._discovered_host,
                CONF_API_KEY: user_input[CONF_API_KEY],
            },
        )

    self._set_confirm_only()
    return self.async_show_form(
        step_id="discovery_confirm",
        data_schema=vol.Schema({
            vol.Required(CONF_API_KEY): str,
        }),
        description_placeholders={"name": self._discovered_name},
    )
```

### Step 7: Write tests (100% coverage required)

Test all flow paths:
- User flow success
- User flow errors (connect, auth, unknown)
- Already configured abort
- Reauth flow
- Reconfigure flow
- Discovery flow (if applicable)

See `.claude/docs/testing-patterns.md` for test examples.

### Step 8: Validate

```bash
pre-commit run --all-files
pytest ./tests/components/<domain>/test_config_flow.py -v
python -m script.hassfest
python -m script.translations develop --all
```

## Key Rules

- **VERSION = 1, MINOR_VERSION = 1** always
- **No user-configurable names** (except helper integrations)
- **Test connection** before creating entry
- **Prevent duplicates** with unique ID or data matching
- **Bare exceptions allowed** in config flow for robustness

## Reference

For detailed patterns, see `.claude/docs/config-flow-patterns.md`.
