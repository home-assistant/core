# Service Patterns

## Registration Location

Register all service actions in `async_setup`, NOT in `async_setup_entry`:

```python
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""

    async def service_action(call: ServiceCall) -> ServiceResponse:
        """Handle service call."""
        if not (entry := hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )):
            raise ServiceValidationError("Entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Entry not loaded")

        # Service logic here
        return {"result": "success"}

    hass.services.async_register(
        DOMAIN,
        "my_service",
        service_action,
        schema=SERVICE_SCHEMA,
    )

    return True
```

## Service Schema

Always validate input:
```python
SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required("parameter"): cv.string,
    vol.Optional("timeout", default=30): cv.positive_int,
})
```

## Entity Services

Register on platform setup:
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "my_entity_service",
        {vol.Required("parameter"): cv.string},
        "handle_service_method"
    )
```

Entity method:
```python
class MyEntity(Entity):
    async def handle_service_method(self, parameter: str) -> None:
        """Handle the service call."""
        await self.device.do_something(parameter)
```

## Exception Handling

```python
async def service_action(call: ServiceCall) -> ServiceResponse:
    """Handle service call."""
    # For invalid input
    if call.data["end_date"] < call.data["start_date"]:
        raise ServiceValidationError("End date must be after start date")

    # For service errors
    try:
        await client.set_schedule(
            call.data["start_date"],
            call.data["end_date"]
        )
    except MyConnectionError as err:
        raise HomeAssistantError("Could not connect to the schedule") from err
```

## Services File

Create `services.yaml` with descriptions:
```yaml
my_service:
  name: My service
  description: Does something useful
  fields:
    parameter:
      name: Parameter
      description: The parameter to use
      required: true
      example: "value"
      selector:
        text:
    timeout:
      name: Timeout
      description: Timeout in seconds
      default: 30
      selector:
        number:
          min: 1
          max: 300
          unit_of_measurement: seconds
```

## Service Response (returning data)

```python
async def service_action(call: ServiceCall) -> ServiceResponse:
    """Handle service call with response."""
    result = await client.get_data()
    return {
        "status": "success",
        "data": result,
    }
```

Register with `supports_response`:
```python
hass.services.async_register(
    DOMAIN,
    "my_service",
    service_action,
    schema=SERVICE_SCHEMA,
    supports_response=SupportsResponse.OPTIONAL,
)
```
