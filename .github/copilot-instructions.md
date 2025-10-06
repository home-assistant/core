# GitHub Copilot & Claude Code Instructions

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Integration Quality Scale

Home Assistant uses an Integration Quality Scale to ensure code quality and consistency. The quality level determines which rules apply:

### Quality Scale Levels
- **Bronze**: Basic requirements (ALL Bronze rules are mandatory)
- **Silver**: Enhanced functionality 
- **Gold**: Advanced features
- **Platinum**: Highest quality standards

### How Rules Apply
1. **Check `manifest.json`**: Look for `"quality_scale"` key to determine integration level
2. **Bronze Rules**: Always required for any integration with quality scale
3. **Higher Tier Rules**: Only apply if integration targets that tier or higher
4. **Rule Status**: Check `quality_scale.yaml` in integration folder for:
   - `done`: Rule implemented
   - `exempt`: Rule doesn't apply (with reason in comment)
   - `todo`: Rule needs implementation

### Example `quality_scale.yaml` Structure
```yaml
rules:
  # Bronze (mandatory)
  config-flow: done
  entity-unique-id: done
  action-setup:
    status: exempt
    comment: Integration does not register custom actions.
  
  # Silver (if targeting Silver+)
  entity-unavailable: done
  parallel-updates: done
  
  # Gold (if targeting Gold+)
  devices: done
  diagnostics: done
  
  # Platinum (if targeting Platinum)
  strict-typing: done
```

**When Reviewing/Creating Code**: 
- Always check the integration's quality scale level and exemption status before applying rules. 
- Make sure to verify if the quality_scale.yaml is up to date with the introduced changes. 
- A PR adding a new feature might also require updating the quality scale file
  - Example: An integration previously being `exempt` status in `actions-exceptions` because it only had read only platforms (like sensors and binary sensors) might introduce a platform that contains actions (a switch for example) and therefore this rule would need to change to `todo` or `done`, depending on if the feature has been implemented in the PR or not.

## Code Review Guidelines

**When reviewing code, do NOT comment on:**
- **Missing imports** - We use static analysis tooling to catch that
- **Code formatting** - We have ruff as a formatting tool that will catch those if needed (unless specifically instructed otherwise in these instructions)

## Python Requirements

- **Compatibility**: Python 3.13+
- **Language Features**: Use the newest features when possible:
  - Pattern matching
  - Type hints
  - f-strings (preferred over `%` or `.format()`)
  - Dataclasses
  - Walrus operator

### Strict Typing (Platinum)
- **Comprehensive Type Hints**: Add type hints to all functions, methods, and variables
- **Custom Config Entry Types**: When using runtime_data:
  ```python
  type MyIntegrationConfigEntry = ConfigEntry[MyClient]
  ```
- **Library Requirements**: Include `py.typed` file for PEP-561 compliance

## Code Quality Standards

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Testing**: pytest with plain functions and fixtures
- **Language**: American English for all code, comments, and documentation (use sentence case, including titles)

### Writing Style Guidelines
- **Tone**: Friendly and informative
- **Perspective**: Use second-person ("you" and "your") for user-facing messages
- **Inclusivity**: Use objective, non-discriminatory language
- **Clarity**: Write for non-native English speakers
- **Formatting in Messages**:
  - Use backticks for: file paths, filenames, variable names, field entries
  - Use sentence case for titles and messages (capitalize only the first word and proper nouns)
  - Avoid abbreviations when possible

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

### Runtime Data Storage
- **Use ConfigEntry.runtime_data**: Store non-persistent runtime data
  ```python
  type MyIntegrationConfigEntry = ConfigEntry[MyClient]
  
  async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
      client = MyClient(entry.data[CONF_HOST])
      entry.runtime_data = client
  ```

### Manifest Requirements
- **Required Fields**: `domain`, `name`, `codeowners`, `integration_type`, `documentation`, `requirements`
- **Integration Types**: `device`, `hub`, `service`, `system`, `helper`
- **IoT Class**: Always specify connectivity method (e.g., `cloud_polling`, `local_polling`, `local_push`)
- **Discovery Methods**: Add when applicable: `zeroconf`, `dhcp`, `bluetooth`, `ssdp`, `usb`
- **Dependencies**: Include platform dependencies (e.g., `application_credentials`, `bluetooth_adapters`)

### Config Flow Patterns
- **Version Control**: Always set `VERSION = 1` and `MINOR_VERSION = 1`
- **Unique ID Management**:
  ```python
  await self.async_set_unique_id(device_unique_id)
  self._abort_if_unique_id_configured()
  ```
- **Error Handling**: Define errors in `strings.json` under `config.error`
- **Step Methods**: Use standard naming (`async_step_user`, `async_step_discovery`, etc.)

### Integration Ownership
- **manifest.json**: Add GitHub usernames to `codeowners`:
  ```json
  {
    "domain": "my_integration",
    "name": "My Integration",
    "codeowners": ["@me"]
  }
  ```

### Documentation Standards
- **File Headers**: Short and concise
  ```python
  """Integration for Peblar EV chargers."""
  ```
- **Method/Function Docstrings**: Required for all
  ```python
  async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
      """Set up Peblar from a config entry."""
  ```
- **Comment Style**:
  - Use clear, descriptive comments
  - Explain the "why" not just the "what"
  - Keep code block lines under 80 characters when possible
  - Use progressive disclosure (simple explanation first, complex details later)

## Async Programming

- All external I/O operations must be async
- **Best Practices**:
  - Avoid sleeping in loops
  - Avoid awaiting in loops - use `gather` instead
  - No blocking calls
  - Group executor jobs when possible - switching between event loop and executor is expensive

### Async Dependencies (Platinum)
- **Requirement**: All dependencies must use asyncio
- Ensures efficient task handling without thread context switching

### WebSession Injection (Platinum)
- **Pass WebSession**: Support passing web sessions to dependencies
  ```python
  async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
      """Set up integration from config entry."""
      client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
  ```
- For cookies: Use `async_create_clientsession` (aiohttp) or `create_async_httpx_client` (httpx)

### Blocking Operations
- **Use Executor**: For blocking I/O operations
  ```python
  result = await hass.async_add_executor_job(blocking_function, args)
  ```
- **Never Block Event Loop**: Avoid file operations, `time.sleep()`, blocking HTTP calls
- **Replace with Async**: Use `asyncio.sleep()` instead of `time.sleep()`

### Thread Safety
- **@callback Decorator**: For event loop safe functions
  ```python
  @callback
  def async_update_callback(self, event):
      """Safe to run in event loop."""
      self.async_write_ha_state()
  ```
- **Sync APIs from Threads**: Use sync versions when calling from non-event loop threads
- **Registry Changes**: Must be done in event loop thread

### Data Update Coordinator
- **Standard Pattern**: Use for efficient data management
  ```python
  class MyCoordinator(DataUpdateCoordinator):
      def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
          super().__init__(
              hass,
              logger=LOGGER,
              name=DOMAIN,
              update_interval=timedelta(minutes=5),
              config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
          )
          self.client = client
      
      async def _async_update_data(self):
          try:
              return await self.client.fetch_data()
          except ApiError as err:
              raise UpdateFailed(f"API communication error: {err}")
  ```
- **Error Types**: Use `UpdateFailed` for API errors, `ConfigEntryAuthFailed` for auth issues
- **Config Entry**: Always pass `config_entry` parameter to coordinator - it's accepted and recommended

## Integration Guidelines

### Configuration Flow
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

### Reauthentication Support
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

### Reconfiguration Flow
- **Purpose**: Allow configuration updates without removing device
- **Implementation**: Add `async_step_reconfigure` method
- **Validation**: Prevent changing underlying account with `_abort_if_unique_id_mismatch`

### Device Discovery
- **Manifest Configuration**: Add discovery method (zeroconf, dhcp, etc.)
  ```json
  {
    "zeroconf": ["_mydevice._tcp.local."]
  }
  ```
- **Discovery Handler**: Implement appropriate `async_step_*` method:
  ```python
  async def async_step_zeroconf(self, discovery_info):
      """Handle zeroconf discovery."""
      await self.async_set_unique_id(discovery_info.properties["serialno"])
      self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
  ```
- **Network Updates**: Use discovery to update dynamic IP addresses

### Network Discovery Implementation
- **Zeroconf/mDNS**: Use async instances
  ```python
  aiozc = await zeroconf.async_get_async_instance(hass)
  ```
- **SSDP Discovery**: Register callbacks with cleanup
  ```python
  entry.async_on_unload(
      ssdp.async_register_callback(
          hass, _async_discovered_device, 
          {"st": "urn:schemas-upnp-org:device:ZonePlayer:1"}
      )
  )
  ```

### Bluetooth Integration
- **Manifest Dependencies**: Add `bluetooth_adapters` to dependencies
- **Connectable**: Set `"connectable": true` for connection-required devices
- **Scanner Usage**: Always use shared scanner instance
  ```python
  scanner = bluetooth.async_get_scanner()
  entry.async_on_unload(
      bluetooth.async_register_callback(
          hass, _async_discovered_device,
          {"service_uuid": "example_uuid"},
          bluetooth.BluetoothScanningMode.ACTIVE
      )
  )
  ```
- **Connection Handling**: Never reuse `BleakClient` instances, use 10+ second timeouts

### Setup Validation
- **Test Before Setup**: Verify integration can be set up in `async_setup_entry`
- **Exception Handling**:
  - `ConfigEntryNotReady`: Device offline or temporary failure
  - `ConfigEntryAuthFailed`: Authentication issues
  - `ConfigEntryError`: Unresolvable setup problems

### Config Entry Unloading
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

### Service Actions
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

### Service Registration Patterns
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

### Polling
- Use update coordinator pattern when possible
- **Polling intervals are NOT user-configurable**: Never add scan_interval, update_interval, or polling frequency options to config flows or config entries
- **Integration determines intervals**: Set `update_interval` programmatically based on integration logic, not user input
- **Minimum Intervals**:
  - Local network: 5 seconds
  - Cloud services: 60 seconds
- **Parallel Updates**: Specify number of concurrent updates:
  ```python
  PARALLEL_UPDATES = 1  # Serialize updates to prevent overwhelming device
  # OR
  PARALLEL_UPDATES = 0  # Unlimited (for coordinator-based or read-only)
  ```

### Error Handling
- **Exception Types**: Choose most specific exception available
  - `ServiceValidationError`: User input errors (preferred over `ValueError`)
  - `HomeAssistantError`: Device communication failures
  - `ConfigEntryNotReady`: Temporary setup issues (device offline)
  - `ConfigEntryAuthFailed`: Authentication problems
  - `ConfigEntryError`: Permanent setup issues
- **Try/Catch Best Practices**:
  - Only wrap code that can throw exceptions
  - Keep try blocks minimal - process data after the try/catch
  - **Avoid bare exceptions** except in specific cases:
    - ❌ Generally not allowed: `except:` or `except Exception:`
    - ✅ Allowed in config flows to ensure robustness
    - ✅ Allowed in functions/methods that run in background tasks
  - Bad pattern:
    ```python
    try:
        data = await device.get_data()  # Can throw
        # ❌ Don't process data inside try block
        processed = data.get("value", 0) * 100
        self._attr_native_value = processed
    except DeviceError:
        _LOGGER.error("Failed to get data")
    ```
  - Good pattern:
    ```python
    try:
        data = await device.get_data()  # Can throw
    except DeviceError:
        _LOGGER.error("Failed to get data")
        return
    
    # ✅ Process data outside try block
    processed = data.get("value", 0) * 100
    self._attr_native_value = processed
    ```
- **Bare Exception Usage**:
  ```python
  # ❌ Not allowed in regular code
  try:
      data = await device.get_data()
  except Exception:  # Too broad
      _LOGGER.error("Failed")
  
  # ✅ Allowed in config flow for robustness
  async def async_step_user(self, user_input=None):
      try:
          await self._test_connection(user_input)
      except Exception:  # Allowed here
          errors["base"] = "unknown"
  
  # ✅ Allowed in background tasks
  async def _background_refresh():
      try:
          await coordinator.async_refresh()
      except Exception:  # Allowed in task
          _LOGGER.exception("Unexpected error in background task")
  ```
- **Setup Failure Patterns**:
  ```python
  try:
      await device.async_setup()
  except (asyncio.TimeoutError, TimeoutException) as ex:
      raise ConfigEntryNotReady(f"Timeout connecting to {device.host}") from ex
  except AuthFailed as ex:
      raise ConfigEntryAuthFailed(f"Credentials expired for {device.name}") from ex
  ```
- **Action Exceptions (Silver)**: In this quality scale item, ensure that all actions, both in services and entity services (e.g. `async_turn_on` action in a switch entity), raise `ServiceValidationError` for user input errors and `HomeAssistantError` for operational errors.

### Logging
- **Format Guidelines**:
  - No periods at end of messages
  - No integration names/domains (added automatically)
  - No sensitive data (keys, tokens, passwords)
- Use debug level for non-user-facing messages
- **Use Lazy Logging**:
  ```python
  _LOGGER.debug("This is a log message with %s", variable)
  ```

### Unavailability Logging
- **Log Once**: When device/service becomes unavailable (info level)
- **Log Recovery**: When device/service comes back online
- **Implementation Pattern**:
  ```python
  _unavailable_logged: bool = False
  
  if not self._unavailable_logged:
      _LOGGER.info("The sensor is unavailable: %s", ex)
      self._unavailable_logged = True
  # On recovery:
  if self._unavailable_logged:
      _LOGGER.info("The sensor is back online")
      self._unavailable_logged = False
  ```

## Entity Development

### Unique IDs
- **Required**: Every entity must have a unique ID for registry tracking
- Must be unique per platform (not per integration)
- Don't include integration domain or platform in ID
- **Implementation**:
  ```python
  class MySensor(SensorEntity):
      def __init__(self, device_id: str) -> None:
          self._attr_unique_id = f"{device_id}_temperature"
  ```

**Acceptable ID Sources**:
- Device serial numbers
- MAC addresses (formatted using `format_mac` from device registry)
- Physical identifiers (printed/EEPROM)
- Config entry ID as last resort: `f"{entry.entry_id}-battery"`

**Never Use**:
- IP addresses, hostnames, URLs
- Device names
- Email addresses, usernames

### Entity Descriptions
- **Lambda/Anonymous Functions**: Often used in EntityDescription for value transformation
- **Multiline Lambdas**: When lambdas exceed line length, wrap in parentheses for readability
- **Bad pattern**:
  ```python
  SensorEntityDescription(
      key="temperature",
      name="Temperature",
      value_fn=lambda data: round(data["temp_value"] * 1.8 + 32, 1) if data.get("temp_value") is not None else None,  # ❌ Too long
  )
  ```
- **Good pattern**:
  ```python
  SensorEntityDescription(
      key="temperature", 
      name="Temperature",
      value_fn=lambda data: (  # ✅ Parenthesis on same line as lambda
          round(data["temp_value"] * 1.8 + 32, 1)
          if data.get("temp_value") is not None
          else None
      ),
  )
  ```

### Entity Naming
- **Use has_entity_name**: Set `_attr_has_entity_name = True`
- **For specific fields**:
  ```python
  class MySensor(SensorEntity):
      _attr_has_entity_name = True
      def __init__(self, device: Device, field: str) -> None:
          self._attr_device_info = DeviceInfo(
              identifiers={(DOMAIN, device.id)},
              name=device.name,
          )
          self._attr_name = field  # e.g., "temperature", "humidity"
  ```
- **For device itself**: Set `_attr_name = None`

### Event Lifecycle Management
- **Subscribe in `async_added_to_hass`**:
  ```python
  async def async_added_to_hass(self) -> None:
      """Subscribe to events."""
      self.async_on_remove(
          self.client.events.subscribe("my_event", self._handle_event)
      )
  ```
- **Unsubscribe in `async_will_remove_from_hass`** if not using `async_on_remove`
- Never subscribe in `__init__` or other methods

### State Handling
- Unknown values: Use `None` (not "unknown" or "unavailable")
- Availability: Implement `available()` property instead of using "unavailable" state

### Entity Availability
- **Mark Unavailable**: When data cannot be fetched from device/service
- **Coordinator Pattern**:
  ```python
  @property
  def available(self) -> bool:
      """Return if entity is available."""
      return super().available and self.identifier in self.coordinator.data
  ```
- **Direct Update Pattern**:
  ```python
  async def async_update(self) -> None:
      """Update entity."""
      try:
          data = await self.client.get_data()
      except MyException:
          self._attr_available = False
      else:
          self._attr_available = True
          self._attr_native_value = data.value
  ```

### Extra State Attributes
- All attribute keys must always be present
- Unknown values: Use `None`
- Provide descriptive attributes

## Device Management

### Device Registry
- **Create Devices**: Group related entities under devices
- **Device Info**: Provide comprehensive metadata:
  ```python
  _attr_device_info = DeviceInfo(
      connections={(CONNECTION_NETWORK_MAC, device.mac)},
      identifiers={(DOMAIN, device.id)},
      name=device.name,
      manufacturer="My Company",
      model="My Sensor",
      sw_version=device.version,
  )
  ```
- For services: Add `entry_type=DeviceEntryType.SERVICE`

### Dynamic Device Addition
- **Auto-detect New Devices**: After initial setup
- **Implementation Pattern**:
  ```python
  def _check_device() -> None:
      current_devices = set(coordinator.data)
      new_devices = current_devices - known_devices
      if new_devices:
          known_devices.update(new_devices)
          async_add_entities([MySensor(coordinator, device_id) for device_id in new_devices])
  
  entry.async_on_unload(coordinator.async_add_listener(_check_device))
  ```

### Stale Device Removal
- **Auto-remove**: When devices disappear from hub/account
- **Device Registry Update**:
  ```python
  device_registry.async_update_device(
      device_id=device.id,
      remove_config_entry_id=self.config_entry.entry_id,
  )
  ```
- **Manual Deletion**: Implement `async_remove_config_entry_device` when needed

## Diagnostics and Repairs

### Integration Diagnostics
- **Required**: Implement diagnostic data collection
- **Implementation**:
  ```python
  TO_REDACT = [CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE]
  
  async def async_get_config_entry_diagnostics(
      hass: HomeAssistant, entry: MyConfigEntry
  ) -> dict[str, Any]:
      """Return diagnostics for a config entry."""
      return {
          "entry_data": async_redact_data(entry.data, TO_REDACT),
          "data": entry.runtime_data.data,
      }
  ```
- **Security**: Never expose passwords, tokens, or sensitive coordinates

### Repair Issues
- **Actionable Issues Required**: All repair issues must be actionable for end users
- **Issue Content Requirements**:
  - Clearly explain what is happening
  - Provide specific steps users need to take to resolve the issue
  - Use friendly, helpful language
  - Include relevant context (device names, error details, etc.)
- **Implementation**:
  ```python
  ir.async_create_issue(
      hass,
      DOMAIN,
      "outdated_version",
      is_fixable=False,
      issue_domain=DOMAIN,
      severity=ir.IssueSeverity.ERROR,
      translation_key="outdated_version",
  )
  ```
- **Translation Strings Requirements**: Must contain user-actionable text in `strings.json`:
  ```json
  {
    "issues": {
      "outdated_version": {
        "title": "Device firmware is outdated",
        "description": "Your device firmware version {current_version} is below the minimum required version {min_version}. To fix this issue: 1) Open the manufacturer's mobile app, 2) Navigate to device settings, 3) Select 'Update Firmware', 4) Wait for the update to complete, then 5) Restart Home Assistant."
      }
    }
  }
  ```
- **String Content Must Include**:
  - What the problem is
  - Why it matters
  - Exact steps to resolve (numbered list when multiple steps)
  - What to expect after following the steps
- **Avoid Vague Instructions**: Don't just say "update firmware" - provide specific steps
- **Severity Guidelines**:
  - `CRITICAL`: Reserved for extreme scenarios only
  - `ERROR`: Requires immediate user attention  
  - `WARNING`: Indicates future potential breakage
- **Additional Attributes**:
  ```python
  ir.async_create_issue(
      hass, DOMAIN, "issue_id",
      breaks_in_ha_version="2024.1.0",
      is_fixable=True,
      is_persistent=True,
      severity=ir.IssueSeverity.ERROR,
      translation_key="issue_description",
  )
  ```
- Only create issues for problems users can potentially resolve

### Entity Categories
- **Required**: Assign appropriate category to entities
- **Implementation**: Set `_attr_entity_category`
  ```python
  class MySensor(SensorEntity):
      _attr_entity_category = EntityCategory.DIAGNOSTIC
  ```
- Categories include: `DIAGNOSTIC` for system/technical information

### Device Classes
- **Use When Available**: Set appropriate device class for entity type
  ```python
  class MyTemperatureSensor(SensorEntity):
      _attr_device_class = SensorDeviceClass.TEMPERATURE
  ```
- Provides context for: unit conversion, voice control, UI representation

### Disabled by Default
- **Disable Noisy/Less Popular Entities**: Reduce resource usage
  ```python
  class MySignalStrengthSensor(SensorEntity):
      _attr_entity_registry_enabled_default = False
  ```
- Target: frequently changing states, technical diagnostics

### Entity Translations
- **Required with has_entity_name**: Support international users
- **Implementation**:
  ```python
  class MySensor(SensorEntity):
      _attr_has_entity_name = True
      _attr_translation_key = "phase_voltage"
  ```
- Create `strings.json` with translations:
  ```json
  {
    "entity": {
      "sensor": {
        "phase_voltage": {
          "name": "Phase voltage"
        }
      }
    }
  }
  ```

### Exception Translations (Gold)
- **Translatable Errors**: Use translation keys for user-facing exceptions
- **Implementation**:
  ```python
  raise ServiceValidationError(
      translation_domain=DOMAIN,
      translation_key="end_date_before_start_date",
  )
  ```
- Add to `strings.json`:
  ```json
  {
    "exceptions": {
      "end_date_before_start_date": {
        "message": "The end date cannot be before the start date."
      }
    }
  }
  ```

### Icon Translations (Gold)
- **Dynamic Icons**: Support state and range-based icon selection
- **State-based Icons**:
  ```json
  {
    "entity": {
      "sensor": {
        "tree_pollen": {
          "default": "mdi:tree",
          "state": {
            "high": "mdi:tree-outline"
          }
        }
      }
    }
  }
  ```
- **Range-based Icons** (for numeric values):
  ```json
  {
    "entity": {
      "sensor": {
        "battery_level": {
          "default": "mdi:battery-unknown",
          "range": {
            "0": "mdi:battery-outline",
            "90": "mdi:battery-90",
            "100": "mdi:battery"
          }
        }
      }
    }
  }
  ```

## Testing Requirements

- **Location**: `tests/components/{domain}/`
- **Coverage Requirement**: Above 95% test coverage for all modules
- **Best Practices**:
  - Use pytest fixtures from `tests.common`
  - Mock all external dependencies
  - Use snapshots for complex data structures
  - Follow existing test patterns

### Config Flow Testing
- **100% Coverage Required**: All config flow paths must be tested
- **Test Scenarios**:
  - All flow initiation methods (user, discovery, import)
  - Successful configuration paths
  - Error recovery scenarios
  - Prevention of duplicate entries
  - Flow completion after errors

## Development Commands

### Code Quality & Linting
- **Run all linters on all files**: `pre-commit run --all-files`
- **Run linters on staged files only**: `pre-commit run`
- **PyLint on everything** (slow): `pylint homeassistant`
- **PyLint on specific folder**: `pylint homeassistant/components/my_integration`
- **MyPy type checking (whole project)**: `mypy homeassistant/`
- **MyPy on specific integration**: `mypy homeassistant/components/my_integration`

### Testing
- **Integration-specific tests** (recommended):
  ```bash
  pytest ./tests/components/<integration_domain> \
    --cov=homeassistant.components.<integration_domain> \
    --cov-report term-missing \
    --durations-min=1 \
    --durations=0 \
    --numprocesses=auto
  ```
- **Quick test of changed files**: `pytest --timeout=10 --picked`
- **Update test snapshots**: Add `--snapshot-update` to pytest command
  - ⚠️ Omit test results after using `--snapshot-update`
  - Always run tests again without the flag to verify snapshots
- **Full test suite** (AVOID - very slow): `pytest ./tests`

### Dependencies & Requirements
- **Update generated files after dependency changes**: `python -m script.gen_requirements_all`
- **Install all Python requirements**: 
  ```bash
  uv pip install -r requirements_all.txt -r requirements.txt -r requirements_test.txt
  ```
- **Install test requirements only**: 
  ```bash
  uv pip install -r requirements_test_all.txt -r requirements.txt
  ```

### Translations
- **Update translations after strings.json changes**: 
  ```bash
  python -m script.translations develop --all
  ```

### Project Validation
- **Run hassfest** (checks project structure and updates generated files): 
  ```bash
  python -m script.hassfest
  ```

### File Locations
- **Integration code**: `./homeassistant/components/<integration_domain>/`
- **Integration tests**: `./tests/components/<integration_domain>/`

## Integration Templates

### Standard Integration Structure
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

### Quality Scale Progression
- **Bronze → Silver**: Add entity unavailability, parallel updates, auth flows
- **Silver → Gold**: Add device management, diagnostics, translations  
- **Gold → Platinum**: Add strict typing, async dependencies, websession injection

### Minimal Integration Checklist
- [ ] `manifest.json` with required fields (domain, name, codeowners, etc.)
- [ ] `__init__.py` with `async_setup_entry` and `async_unload_entry`
- [ ] `config_flow.py` with UI configuration support
- [ ] `const.py` with `DOMAIN` constant
- [ ] `strings.json` with at least config flow text
- [ ] Platform files (`sensor.py`, etc.) as needed
- [ ] `quality_scale.yaml` with rule status tracking

## Common Anti-Patterns & Best Practices

### ❌ **Avoid These Patterns**
```python
# Blocking operations in event loop
data = requests.get(url)  # ❌ Blocks event loop
time.sleep(5)  # ❌ Blocks event loop

# Reusing BleakClient instances
self.client = BleakClient(address)
await self.client.connect()
# Later...
await self.client.connect()  # ❌ Don't reuse

# Hardcoded strings in code
self._attr_name = "Temperature Sensor"  # ❌ Not translatable

# Missing error handling
data = await self.api.get_data()  # ❌ No exception handling

# Storing sensitive data in diagnostics
return {"api_key": entry.data[CONF_API_KEY]}  # ❌ Exposes secrets

# Accessing hass.data directly in tests
coordinator = hass.data[DOMAIN][entry.entry_id]  # ❌ Don't access hass.data

# User-configurable polling intervals
# In config flow
vol.Optional("scan_interval", default=60): cv.positive_int  # ❌ Not allowed
# In coordinator
update_interval = timedelta(minutes=entry.data.get("scan_interval", 1))  # ❌ Not allowed

# User-configurable config entry names (non-helper integrations)
vol.Optional("name", default="My Device"): cv.string  # ❌ Not allowed in regular integrations

# Too much code in try block
try:
    response = await client.get_data()  # Can throw
    # ❌ Data processing should be outside try block
    temperature = response["temperature"] / 10
    humidity = response["humidity"] 
    self._attr_native_value = temperature
except ClientError:
    _LOGGER.error("Failed to fetch data")

# Bare exceptions in regular code
try:
    value = await sensor.read_value()
except Exception:  # ❌ Too broad - catch specific exceptions
    _LOGGER.error("Failed to read sensor")
```

### ✅ **Use These Patterns Instead**
```python
# Async operations with executor
data = await hass.async_add_executor_job(requests.get, url)
await asyncio.sleep(5)  # ✅ Non-blocking

# Fresh BleakClient instances
client = BleakClient(address)  # ✅ New instance each time
await client.connect()

# Translatable entity names
_attr_translation_key = "temperature_sensor"  # ✅ Translatable

# Proper error handling
try:
    data = await self.api.get_data()
except ApiException as err:
    raise UpdateFailed(f"API error: {err}") from err

# Redacted diagnostics data
return async_redact_data(data, {"api_key", "password"})  # ✅ Safe

# Test through proper integration setup and fixtures
@pytest.fixture
async def init_integration(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)  # ✅ Proper setup

# Integration-determined polling intervals (not user-configurable)
SCAN_INTERVAL = timedelta(minutes=5)  # ✅ Common pattern: constant in const.py

class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        # ✅ Integration determines interval based on device capabilities, connection type, etc.
        interval = timedelta(minutes=1) if client.is_local else SCAN_INTERVAL
        super().__init__(
            hass, 
            logger=LOGGER, 
            name=DOMAIN, 
            update_interval=interval,
            config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
        )
```

### Entity Performance Optimization
```python
# Use __slots__ for memory efficiency
class MySensor(SensorEntity):
    __slots__ = ("_attr_native_value", "_attr_available")
    
    @property 
    def should_poll(self) -> bool:
        """Disable polling when using coordinator."""
        return False  # ✅ Let coordinator handle updates
```

## Testing Patterns

### Testing Best Practices
- **Never access `hass.data` directly** - Use fixtures and proper integration setup instead
- **Use snapshot testing** - For verifying entity states and attributes
- **Test through integration setup** - Don't test entities in isolation
- **Mock external APIs** - Use fixtures with realistic JSON data
- **Verify registries** - Ensure entities are properly registered with devices

### Config Flow Testing Template
```python
async def test_user_flow_success(hass, mock_api):
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test form submission
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Device"
    assert result["data"] == TEST_USER_INPUT

async def test_flow_connection_error(hass, mock_api_error):
    """Test connection error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
```

### Entity Testing Patterns
```python
@pytest.fixture 
def platforms() -> list[Platform]: 
    """Overridden fixture to specify platforms to test.""" 
    return [Platform.SENSOR]  # Or another specific platform as needed.

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entities are correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_unique_id")}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
```

### Mock Patterns
```python
# Modern integration fixture setup
@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Integration",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_API_KEY: "test_key"},
        unique_id="device_unique_id",
    )

@pytest.fixture
def mock_device_api() -> Generator[MagicMock]:
    """Return a mocked device API."""
    with patch("homeassistant.components.my_integration.MyDeviceAPI", autospec=True) as api_mock:
        api = api_mock.return_value
        api.get_data.return_value = MyDeviceData.from_json(
            load_fixture("device_data.json", DOMAIN)
        )
        yield api

@pytest.fixture 
def platforms() -> list[Platform]: 
    """Fixture to specify platforms to test.""" 
    return PLATFORMS

@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.my_integration.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
```

## Debugging & Troubleshooting

### Common Issues & Solutions
- **Integration won't load**: Check `manifest.json` syntax and required fields
- **Entities not appearing**: Verify `unique_id` and `has_entity_name` implementation  
- **Config flow errors**: Check `strings.json` entries and error handling
- **Discovery not working**: Verify manifest discovery configuration and callbacks
- **Tests failing**: Check mock setup and async context

### Debug Logging Setup
```python
# Enable debug logging in tests
caplog.set_level(logging.DEBUG, logger="my_integration")

# In integration code - use proper logging
_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Processing data: %s", data)  # Use lazy logging
```

### Validation Commands
```bash
# Check specific integration
python -m script.hassfest --integration-path homeassistant/components/my_integration

# Validate quality scale
# Check quality_scale.yaml against current rules

# Run integration tests with coverage
pytest ./tests/components/my_integration \
  --cov=homeassistant.components.my_integration \
  --cov-report term-missing
```