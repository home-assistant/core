# Services

This skill covers registering and implementing service actions in Home Assistant integrations.

## When to Use

- Registering service actions for an integration
- Implementing entity services
- Creating service schemas

## Service Actions

- **Registration**: Register all service actions in `async_setup`, NOT in `async_setup_entry`
- **Validation**: Check config entry existence and loaded state:
  ```python
  async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
      async def service_action(call: ServiceCall) -> ServiceResponse:
          if not (entry := hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])):
              raise ServiceValidationError("Entry not found")
          if entry.state is not ConfigEntryState.LOADED:
              raise ServiceValidationError("Entry not loaded")
  ```
- **Exception Handling**: Raise appropriate exceptions:
  ```python
  # For invalid input
  if end_date < start_date:
      raise ServiceValidationError("End date must be after start date")

  # For service errors
  try:
      await client.set_schedule(start_date, end_date)
  except MyConnectionError as err:
      raise HomeAssistantError("Could not connect to the schedule") from err
  ```

## Service Registration Patterns

- **Entity Services**: Register on platform setup
  ```python
  platform.async_register_entity_service(
      "my_entity_service",
      {vol.Required("parameter"): cv.string},
      "handle_service_method"
  )
  ```
- **Service Schema**: Always validate input
  ```python
  SERVICE_SCHEMA = vol.Schema({
      vol.Required("entity_id"): cv.entity_ids,
      vol.Required("parameter"): cv.string,
      vol.Optional("timeout", default=30): cv.positive_int,
  })
  ```
- **Services File**: Create `services.yaml` with descriptions and field definitions

## Related Skills

- `async-programming` - Error handling patterns
- `write-tests` - Testing service actions
