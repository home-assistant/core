# Config Flow Patterns

## Basic Structure

```python
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_connection(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # Allowed in config flow
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
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

## Unique ID Management

```python
# Set unique ID and abort if already configured
await self.async_set_unique_id(device_unique_id)
self._abort_if_unique_id_configured()

# Or match on specific data
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
            user_id = await self._validate_credentials(user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
            )

    return self.async_show_form(
        step_id="reauth_confirm",
        data_schema=vol.Schema({
            vol.Required(CONF_API_TOKEN): str,
        }),
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
        # Prevent changing underlying account
        self._abort_if_unique_id_mismatch()
        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates=user_input,
        )

    return self.async_show_form(
        step_id="reconfigure",
        data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=reconfigure_entry.data[CONF_HOST]): str,
        }),
        errors=errors,
    )
```

## Discovery Flow (Zeroconf Example)

```python
async def async_step_zeroconf(
    self, discovery_info: ZeroconfServiceInfo
) -> ConfigFlowResult:
    """Handle zeroconf discovery."""
    await self.async_set_unique_id(discovery_info.properties["serialno"])
    self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

    self._discovered_host = discovery_info.host
    self._discovered_name = discovery_info.name

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

## Options Flow

```python
class MyOptionsFlow(OptionsFlow):
    """Handle options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }),
        )
```

## Error Handling

Define errors in `strings.json`:
```json
{
  "config": {
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Device is already configured",
      "wrong_account": "Wrong account"
    }
  }
}
```

## Key Rules

- **Version control**: Always set `VERSION = 1` and `MINOR_VERSION = 1`
- **Config entry naming**: Do NOT allow users to set names in config flows (exception: helper integrations)
- **Connection testing**: Always test connection during config flow
- **Duplicate prevention**: Use unique ID or data matching
