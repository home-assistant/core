# Home Assistant Development Instructions

Python 3.13+ home automation core. Use modern features: pattern matching, type hints, f-strings, dataclasses.

## Code Quality

- **Tools**: Ruff (format/lint), PyLint, MyPy (types), pytest
- **Language**: American English, sentence case
- **Don't comment on**: Missing imports, formatting (tooling catches these)
- **Suppressions**: Fix underlying issues before using `# type: ignore` or `noqa`

## Quality Scale

Check `manifest.json` for `"quality_scale"` and `quality_scale.yaml` for rule status (`done`/`exempt`/`todo`).
- **Bronze**: Always required
- **Silver/Gold/Platinum**: Apply if targeting that tier

## Integration Structure

```
homeassistant/components/{domain}/
├── __init__.py       # async_setup_entry, async_unload_entry
├── manifest.json     # domain, name, codeowners, integration_type, documentation, requirements
├── const.py          # DOMAIN constant
├── config_flow.py    # VERSION = 1, MINOR_VERSION = 1
├── coordinator.py    # DataUpdateCoordinator subclass
├── strings.json      # Translations
└── {platform}.py     # sensor.py, switch.py, etc.
```

## Key Patterns

### Config Entry & Coordinator
```python
type MyConfigEntry = ConfigEntry[MyCoordinator]

class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(hass, logger=LOGGER, name=DOMAIN,
                         update_interval=timedelta(minutes=5), config_entry=config_entry)
        self.client = client

    async def _async_update_data(self) -> MyData:
        try:
            return await self.client.fetch_data()
        except ApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up from config entry."""
    client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
    coordinator = MyCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

### Entity
```python
class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_temperature"
        self._attr_translation_key = "temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.data.name,
            manufacturer="Company",
        )
```

### Config Flow
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

## Critical Rules

### Async
- All I/O must be async; use `await hass.async_add_executor_job()` for blocking calls
- Use `asyncio.sleep()` not `time.sleep()`
- Use `gather()` instead of awaiting in loops

### Entities
- **Unique IDs**: Use serial numbers, MAC addresses, or physical identifiers (never IPs/hostnames/names)
- **Availability**: Override `available` property; use `None` for unknown values
- **Subscriptions**: Subscribe in `async_added_to_hass` with `self.async_on_remove()`

### Config Flow
- ❌ No user-configurable polling intervals
- ❌ No user-configurable entry names (except helpers)
- Implement `async_step_reauth` and `async_step_reconfigure`

### Error Handling
- `ConfigEntryNotReady`: Device offline
- `ConfigEntryAuthFailed`: Auth issues
- `UpdateFailed`: API errors in coordinator
- `ServiceValidationError`: Invalid service input
- Keep try blocks minimal; process data outside

### Logging
- No periods, no domain names, no sensitive data
- Use lazy logging: `_LOGGER.debug("Message: %s", var)`

### Services
- Register in `async_setup`, not `async_setup_entry`
- Create `services.yaml` with descriptions

### Diagnostics
- Redact sensitive data: `async_redact_data(data, TO_REDACT)`

## Testing

```bash
# Run integration tests
pytest ./tests/components/<domain> --cov=homeassistant.components.<domain> --cov-report term-missing --numprocesses=auto

# Linting
pre-commit run --all-files

# Type checking
mypy homeassistant/components/<domain>

# Update after manifest/strings changes
python -m script.hassfest
python -m script.translations develop --all
```

- **95%+ coverage required**
- Use `snapshot_platform()` for entity state testing
- Mock external APIs with fixtures
- Never access `hass.data` directly in tests
