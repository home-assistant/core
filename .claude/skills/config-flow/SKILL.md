# Config Flow

This skill covers implementing configuration flows for Home Assistant integrations.

## When to Use

- Adding UI configuration to an integration
- Implementing reauthentication or reconfiguration
- Handling device discovery

## Configuration Flow

- **UI Setup Required**: All integrations must support configuration via UI
- **Manifest**: Set `"config_flow": true` in `manifest.json`
- **Data Storage**:
  - Connection-critical config: Store in `ConfigEntry.data`
  - Non-critical settings: Store in `ConfigEntry.options`
- **Validation**: Always validate user input before creating entries
- **Config Entry Naming**: 
  - ❌ Do NOT allow users to set config entry names in config flows
  - Names are automatically generated or can be customized later in UI
  - ✅ Exception: Helper integrations MAY allow custom names in config flow
- **Connection Testing**: Test device/service connection during config flow:
  ```python
  try:
      await client.get_data()
  except MyException:
      errors["base"] = "cannot_connect"
  ```
- **Duplicate Prevention**: Prevent duplicate configurations:
  ```python
  # Using unique ID
  await self.async_set_unique_id(identifier)
  self._abort_if_unique_id_configured()
  
  # Using unique data
  self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
  ```

## Config Flow Patterns

- **Version Control**: Always set `VERSION = 1` and `MINOR_VERSION = 1`
- **Unique ID Management**:
  ```python
  await self.async_set_unique_id(device_unique_id)
  self._abort_if_unique_id_configured()
  ```
- **Error Handling**: Define errors in `strings.json` under `config.error`
- **Step Methods**: Use standard naming (`async_step_user`, `async_step_discovery`, etc.)

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

## Related Skills

- `device-discovery` - Add discovery support to config flow
- `write-tests` - 100% config flow test coverage required
