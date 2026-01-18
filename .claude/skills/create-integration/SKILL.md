# Create Integration

This skill guides you through creating a new Home Assistant integration from scratch.

## When to Use

- Creating a brand new integration for a device or service
- Understanding the structure and requirements of an integration
- Setting up the foundation before adding platforms

## Standard Integration Structure

```
homeassistant/components/my_integration/
├── __init__.py          # Entry point with async_setup_entry
├── manifest.json        # Integration metadata and dependencies
├── const.py            # Domain and constants
├── config_flow.py      # UI configuration flow
├── coordinator.py      # Data update coordinator (if needed)
├── entity.py          # Base entity class (if shared patterns)
├── sensor.py          # Sensor platform
├── strings.json        # User-facing text and translations
├── services.yaml       # Service definitions (if applicable)
└── quality_scale.yaml  # Quality scale rule status
```

## Code Organization

### Core Locations
- Shared constants: `homeassistant/const.py` (use these instead of hardcoding)
- Integration structure:
  - `homeassistant/components/{domain}/const.py` - Constants
  - `homeassistant/components/{domain}/models.py` - Data models
  - `homeassistant/components/{domain}/coordinator.py` - Update coordinator
  - `homeassistant/components/{domain}/config_flow.py` - Configuration flow
  - `homeassistant/components/{domain}/{platform}.py` - Platform implementations

### Common Modules
- **coordinator.py**: Centralize data fetching logic
  ```python
  class MyCoordinator(DataUpdateCoordinator[MyData]):
      def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
          super().__init__(
              hass,
              logger=LOGGER,
              name=DOMAIN,
              update_interval=timedelta(minutes=1),
              config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
          )
  ```
- **entity.py**: Base entity definitions to reduce duplication
  ```python
  class MyEntity(CoordinatorEntity[MyCoordinator]):
      _attr_has_entity_name = True
  ```

## Manifest Requirements

- **Required Fields**: `domain`, `name`, `codeowners`, `integration_type`, `documentation`, `requirements`
- **Integration Types**: `device`, `hub`, `service`, `system`, `helper`
- **IoT Class**: Always specify connectivity method (e.g., `cloud_polling`, `local_polling`, `local_push`)
- **Discovery Methods**: Add when applicable: `zeroconf`, `dhcp`, `bluetooth`, `ssdp`, `usb`
- **Dependencies**: Include platform dependencies (e.g., `application_credentials`, `bluetooth_adapters`)

## Integration Ownership

- **manifest.json**: Add GitHub usernames to `codeowners`:
  ```json
  {
    "domain": "my_integration",
    "name": "My Integration",
    "codeowners": ["@me"]
  }
  ```

## Runtime Data Storage

- **Use ConfigEntry.runtime_data**: Store non-persistent runtime data
  ```python
  type MyIntegrationConfigEntry = ConfigEntry[MyClient]
  
  async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
      client = MyClient(entry.data[CONF_HOST])
      entry.runtime_data = client
  ```

## Setup Validation

- **Test Before Setup**: Verify integration can be set up in `async_setup_entry`
- **Exception Handling**:
  - `ConfigEntryNotReady`: Device offline or temporary failure
  - `ConfigEntryAuthFailed`: Authentication issues
  - `ConfigEntryError`: Unresolvable setup problems

## Config Entry Unloading

- **Required**: Implement `async_unload_entry` for runtime removal/reload
- **Platform Unloading**: Use `hass.config_entries.async_unload_platforms`
- **Cleanup**: Register callbacks with `entry.async_on_unload`:
  ```python
  async def async_unload_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
      """Unload a config entry."""
      if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
          entry.runtime_data.listener()  # Clean up resources
      return unload_ok
  ```

## Minimal Integration Checklist

- [ ] `manifest.json` with required fields (domain, name, codeowners, etc.)
- [ ] `__init__.py` with `async_setup_entry` and `async_unload_entry`
- [ ] `config_flow.py` with UI configuration support
- [ ] `const.py` with `DOMAIN` constant
- [ ] `strings.json` with at least config flow text
- [ ] Platform files (`sensor.py`, etc.) as needed
- [ ] `quality_scale.yaml` with rule status tracking

## Related Skills

- `code-standards` - Python requirements, code style, logging, writing style
- `config-flow` - Implement configuration flows
- `coordinator` - Data update coordinator patterns
- `entity` - Entity development
- `write-tests` - Testing patterns
- `quality-scale` - Quality requirements
