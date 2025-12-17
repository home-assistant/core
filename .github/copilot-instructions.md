# Home Assistant Development Instructions

Python 3.13+ home automation core. Use modern features: pattern matching, type hints, f-strings, dataclasses, walrus operator.

## Code Review Guidelines

**Do NOT comment on:**
- Missing imports (static analysis catches these)
- Code formatting (Ruff handles this)

## Code Quality Standards

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Testing**: pytest with plain functions and fixtures
- **Language**: American English, sentence case
- **Suppressions**: Fix underlying issues before using `# type: ignore` or `noqa`

### Writing Style
- Friendly, informative tone; use "you" and "your"
- Write for non-native English speakers
- Use backticks for: file paths, filenames, variable names, field entries
- Sentence case for titles/messages; avoid abbreviations

## Quality Scale

Check `manifest.json` for `"quality_scale"` and `quality_scale.yaml` for rule status (`done`/`exempt`/`todo`).

- **Bronze**: Always required
- **Silver**: Entity unavailability, parallel updates, auth flows
- **Gold**: Device management, diagnostics, translations
- **Platinum**: Strict typing, async dependencies, websession injection

## Code Organization

### Core Locations
- Shared constants: `homeassistant/const.py`
- Integration: `homeassistant/components/{domain}/`
  - `const.py`, `models.py`, `coordinator.py`, `config_flow.py`, `{platform}.py`

### Manifest Requirements
- **Required**: `domain`, `name`, `codeowners`, `integration_type`, `documentation`, `requirements`
- **Types**: `device`, `hub`, `service`, `system`, `helper`
- **IoT Class**: `cloud_polling`, `local_polling`, `local_push`, etc.
- **Discovery**: `zeroconf`, `dhcp`, `bluetooth`, `ssdp`, `usb` when applicable

### Documentation
```python
"""Integration for Peblar EV chargers."""

async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Set up Peblar from a config entry."""
```

## Async Programming

- All external I/O must be async
- Use `gather()` instead of awaiting in loops
- Use `asyncio.sleep()` not `time.sleep()`
- Group executor jobs when possible

### Blocking Operations
```python
result = await hass.async_add_executor_job(blocking_function, args)
```

### Thread Safety
```python
@callback
def async_update_callback(self, event):
    """Safe to run in event loop."""
    self.async_write_ha_state()
```

### WebSession Injection (Platinum)
```python
client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
# For cookies: async_create_clientsession (aiohttp) or create_async_httpx_client (httpx)
```

### Data Update Coordinator
```python
type MyConfigEntry = ConfigEntry[MyCoordinator]

class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass, logger=LOGGER, name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # Always pass config_entry
        )
        self.client = client

    async def _async_update_data(self) -> MyData:
        try:
            return await self.client.fetch_data()
        except ApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except AuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
```

## Integration Guidelines

### Configuration Flow
- Set `"config_flow": true` in manifest
- Store connection-critical config in `ConfigEntry.data`, settings in `ConfigEntry.options`
- ❌ No user-configurable entry names (except helpers)
- ❌ No user-configurable polling intervals

```python
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                await self._test_connection(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # Allowed in config flow
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Device", data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
```

### Reauthentication
```python
async def async_step_reauth(self, entry_data):
    """Handle reauth."""
    return await self.async_step_reauth_confirm()

async def async_step_reauth_confirm(self, user_input=None):
    if user_input:
        await self.async_set_unique_id(self._get_reauth_entry().unique_id)
        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
        )
```

### Reconfiguration
- Add `async_step_reconfigure` method
- Use `_abort_if_unique_id_mismatch` to prevent account changes

### Device Discovery
```python
# In manifest.json
{"zeroconf": ["_mydevice._tcp.local."]}

# In config_flow.py
async def async_step_zeroconf(self, discovery_info):
    await self.async_set_unique_id(discovery_info.properties["serialno"])
    self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
```

### Bluetooth
- Add `bluetooth_adapters` to manifest dependencies
- Never reuse `BleakClient` instances; use 10+ second timeouts

### Setup & Unload
```python
async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up from config entry."""
    try:
        client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
        await client.connect()
    except TimeoutError as ex:
        raise ConfigEntryNotReady(f"Timeout: {ex}") from ex
    except AuthError as ex:
        raise ConfigEntryAuthFailed(f"Auth failed: {ex}") from ex

    coordinator = MyCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### Services
- Register in `async_setup`, NOT `async_setup_entry`
- Create `services.yaml` with descriptions

```python
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def service_action(call: ServiceCall) -> ServiceResponse:
        if not (entry := hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])):
            raise ServiceValidationError("Entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Entry not loaded")
```

### Polling
- Use coordinator pattern
- **Minimum intervals**: Local 5s, Cloud 60s
- Set `PARALLEL_UPDATES = 1` to serialize, `0` for unlimited

### Error Handling
- `ConfigEntryNotReady`: Device offline (temporary)
- `ConfigEntryAuthFailed`: Auth issues
- `ConfigEntryError`: Permanent setup issues
- `UpdateFailed`: API errors in coordinator
- `ServiceValidationError`: Invalid service input
- `HomeAssistantError`: Device communication failures

**Keep try blocks minimal:**
```python
try:
    data = await device.get_data()
except DeviceError:
    _LOGGER.error("Failed to get data")
    return

# Process data outside try block
self._attr_native_value = data.get("value", 0) * 100
```

**Bare exceptions only allowed in:**
- Config flows (for robustness)
- Background tasks

### Logging
- No periods at end, no domain names, no sensitive data
- Use lazy logging: `_LOGGER.debug("Message: %s", var)`
- Log unavailability once, log recovery

## Entity Development

### Unique IDs
**Acceptable**: Serial numbers, MAC addresses (`format_mac`), physical identifiers, config entry ID (last resort)

**Never use**: IP addresses, hostnames, URLs, device names, emails

```python
class MySensor(SensorEntity):
    _attr_unique_id = f"{device_id}_temperature"
```

### Entity Naming & Translations
```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "phase_voltage"  # For specific sensors
    # _attr_name = None  # For main device entity

    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        name=device.name,
        manufacturer="Company",
        model="Model",
        sw_version=device.version,
    )
```

In `strings.json`:
```json
{"entity": {"sensor": {"phase_voltage": {"name": "Phase voltage"}}}}
```

### Entity Descriptions
```python
SensorEntityDescription(
    key="temperature",
    value_fn=lambda data: (  # Wrap long lambdas in parentheses
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```

### Lifecycle & Availability
```python
async def async_added_to_hass(self) -> None:
    """Subscribe to events."""
    self.async_on_remove(
        self.client.events.subscribe("my_event", self._handle_event)
    )

@property
def available(self) -> bool:
    return super().available and self.identifier in self.coordinator.data
```

- Use `None` for unknown values (not "unknown" string)
- Override `available` property (don't use "unavailable" state)

### Entity Attributes
- `_attr_device_class`: Use when available (enables unit conversion, voice control)
- `_attr_entity_category`: `EntityCategory.DIAGNOSTIC` for technical info
- `_attr_entity_registry_enabled_default = False`: For noisy/less popular entities

## Device Management

### Device Registry
```python
_attr_device_info = DeviceInfo(
    connections={(CONNECTION_NETWORK_MAC, device.mac)},
    identifiers={(DOMAIN, device.id)},
    name=device.name,
    manufacturer="Company",
    model="Model",
    sw_version=device.version,
)
# For services: entry_type=DeviceEntryType.SERVICE
```

### Dynamic Devices
```python
def _check_device() -> None:
    new_devices = set(coordinator.data) - known_devices
    if new_devices:
        known_devices.update(new_devices)
        async_add_entities([MySensor(coordinator, d) for d in new_devices])

entry.async_on_unload(coordinator.async_add_listener(_check_device))
```

### Stale Device Removal
```python
device_registry.async_update_device(
    device_id=device.id,
    remove_config_entry_id=self.config_entry.entry_id,
)
```

## Diagnostics & Repairs

### Diagnostics
```python
TO_REDACT = [CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE]

async def async_get_config_entry_diagnostics(hass, entry):
    return {"entry_data": async_redact_data(entry.data, TO_REDACT)}
```

### Repair Issues
Must be **actionable** with specific steps:
```python
ir.async_create_issue(
    hass, DOMAIN, "outdated_version",
    is_fixable=False,
    severity=ir.IssueSeverity.ERROR,
    translation_key="outdated_version",
)
```

In `strings.json`, include: what's wrong, why it matters, exact steps to fix:
```json
{"issues": {"outdated_version": {
    "title": "Device firmware is outdated",
    "description": "Your firmware {current_version} is below {min_version}. Steps: 1) Open app, 2) Go to settings, 3) Update firmware, 4) Restart Home Assistant."
}}}
```

### Exception Translations (Gold)
```python
raise ServiceValidationError(
    translation_domain=DOMAIN,
    translation_key="end_date_before_start_date",
)
```

### Icon Translations (Gold)
```json
{"entity": {"sensor": {"battery": {
    "default": "mdi:battery-unknown",
    "range": {"0": "mdi:battery-outline", "90": "mdi:battery-90", "100": "mdi:battery"}
}}}}
```

## Testing

### Commands
```bash
# Integration tests (recommended)
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --numprocesses=auto

# Linting
pre-commit run --all-files

# Type checking
mypy homeassistant/components/<domain>

# After manifest/strings changes
python -m script.hassfest
python -m script.translations develop --all

# Snapshot updates
pytest ... --snapshot-update  # Then re-run without flag to verify
```

### Requirements
- **95%+ coverage** for all modules
- **100% config flow coverage**
- Never access `hass.data` directly in tests

### Test Patterns
```python
@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        title="My Integration", domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"}, unique_id="device_id",
    )

@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    with patch("homeassistant.components.my_integration.MyAPI", autospec=True) as mock:
        mock.return_value.get_data.return_value = load_fixture("data.json", DOMAIN)
        yield mock

@pytest.fixture
async def init_integration(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(hass, snapshot, entity_registry, mock_config_entry):
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
```

## Common Anti-Patterns

### ❌ Avoid
```python
data = requests.get(url)  # Blocks event loop
time.sleep(5)  # Blocks event loop
await self.client.connect()  # Don't reuse BleakClient
self._attr_name = "Temperature"  # Not translatable
return {"api_key": entry.data[CONF_API_KEY]}  # Exposes secrets
coordinator = hass.data[DOMAIN][entry.entry_id]  # Don't access in tests
vol.Optional("scan_interval"): cv.positive_int  # User polling not allowed
vol.Optional("name"): cv.string  # User naming not allowed (except helpers)
except Exception:  # Too broad in regular code
```

### ✅ Use Instead
```python
data = await hass.async_add_executor_job(requests.get, url)
await asyncio.sleep(5)
client = BleakClient(address)  # Fresh instance each time
_attr_translation_key = "temperature"
return async_redact_data(data, {"api_key"})
# Use fixtures and proper setup in tests
SCAN_INTERVAL = timedelta(minutes=5)  # Integration determines interval
```

## Debugging

- **Integration won't load**: Check `manifest.json` syntax
- **Entities missing**: Verify `unique_id` and `has_entity_name`
- **Config flow errors**: Check `strings.json` error keys
- **Discovery failing**: Check manifest discovery config

```python
caplog.set_level(logging.DEBUG, logger="my_integration")
```
