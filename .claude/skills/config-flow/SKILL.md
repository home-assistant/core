# Config Flow

This skill covers implementing configuration flows for Home Assistant integrations.

## When to Use

- Adding UI configuration to an integration
- Implementing reauthentication or reconfiguration
- Handling device discovery

## Core Requirements

- All integrations must support configuration via UI
- Set `"config_flow": true` in `manifest.json`
- Always set `VERSION = 1` and `MINOR_VERSION = 1`

## Config Flow Patterns

### Version Control

```python
VERSION = 1
MINOR_VERSION = 1
```

### Unique ID Management

```python
await self.async_set_unique_id(device_unique_id)
self._abort_if_unique_id_configured()
```

## Data Storage

- **ConfigEntry.data**: Connection-critical config (host, credentials)
- **ConfigEntry.options**: Non-critical settings

## Validation

Always validate user input before creating entries.

## Config Entry Naming

- Do NOT allow users to set config entry names in config flows
- Names are automatically generated or can be customized later in UI
- Exception: Helper integrations MAY allow custom names in config flow

## Connection Testing

```python
try:
    await client.get_data()
except MyException:
    errors["base"] = "cannot_connect"
```

## Duplicate Prevention

```python
# Using unique ID
await self.async_set_unique_id(identifier)
self._abort_if_unique_id_configured()

# Using unique data
self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
```

## Reauthentication Support

- **Required Method**: Implement `async_step_reauth` in config flow
- **Credential Updates**: Allow users to update credentials without re-adding
- **Validation**: Verify account matches existing unique ID:

```python
await self.async_set_unique_id(user_id)
self._abort_if_unique_id_mismatch(reason="wrong_account")
return self.async_update_reload_and_abort(
    self._get_reauth_entry(),
    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
)
```

## Reconfiguration Flow

- **Purpose**: Allow configuration updates without removing device
- **Implementation**: Add `async_step_reconfigure` method
- **Validation**: Prevent changing underlying account with `_abort_if_unique_id_mismatch`

## Error Handling

- Define errors in `strings.json` under `config.error`
- Bare exceptions (`except Exception:`) are allowed in config flows for robustness

## Related Skills

- `device-discovery` - Add discovery support to config flow
- `write-tests` - 100% config flow test coverage required
