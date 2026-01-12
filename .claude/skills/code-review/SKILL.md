---
name: code-review
description: Review Home Assistant integration code for quality, best practices, and standards compliance. Use when reviewing pull requests, identifying anti-patterns, checking security vulnerabilities (OWASP), verifying async patterns, ensuring quality scale compliance, or providing comprehensive code feedback.
---

# Code Review Skill for Home Assistant Integrations

You are an expert Home Assistant code reviewer with deep knowledge of Python, async programming, Home Assistant architecture, and integration best practices.

## Review Guidelines

### What to Review
✅ **DO review and comment on:**
- Architecture and design patterns
- Async programming correctness
- Error handling and edge cases
- Security vulnerabilities (XSS, SQL injection, command injection, etc.)
- Performance issues (blocking operations, inefficient loops)
- Code organization and clarity
- Compliance with Home Assistant patterns
- Quality scale requirements
- Missing functionality or incomplete implementations

❌ **DO NOT comment on:**
- Missing imports (static analysis catches this)
- Code formatting (Ruff handles this)
- Minor style issues that linters catch

### Git Practices During Review
⚠️ **CRITICAL**: After review has started:
- **DO NOT amend commits**
- **DO NOT squash commits**
- **DO NOT rebase commits**
- Reviewers need to see what changed since their last review

## Key Review Areas

### 1. Async Programming Patterns

#### ✅ Good Async Patterns
```python
# Proper async I/O
data = await client.get_data()

# Using asyncio.sleep instead of time.sleep
await asyncio.sleep(5)

# Executor for blocking operations
result = await hass.async_add_executor_job(blocking_function, args)

# Gathering async operations
results = await asyncio.gather(
    client.get_temp(),
    client.get_humidity(),
)

# @callback for event loop safe functions
@callback
def async_update_callback(self, event):
    self.async_write_ha_state()
```

#### ❌ Bad Async Patterns
```python
# Blocking operations in event loop
data = requests.get(url)  # ❌ Blocks event loop
time.sleep(5)  # ❌ Blocks event loop

# Awaiting in loops (use gather instead)
for device in devices:
    data = await device.get_data()  # ❌ Sequential, slow

# Reusing BleakClient instances
await self.client.connect()  # ❌ Don't reuse BleakClient
```

### 2. Error Handling

#### ✅ Good Error Handling
```python
# Minimal try blocks, process outside
try:
    data = await device.get_data()
except DeviceError as err:
    _LOGGER.error("Failed to get data: %s", err)
    return

# Process data outside try block
processed = data.get("value", 0) * 100
self._attr_native_value = processed

# Proper exception types
try:
    await client.connect()
except asyncio.TimeoutError as ex:
    raise ConfigEntryNotReady(f"Timeout connecting to {host}") from ex
except AuthError as ex:
    raise ConfigEntryAuthFailed("Invalid credentials") from ex
```

#### ❌ Bad Error Handling
```python
# Too much code in try block
try:
    data = await device.get_data()
    processed = data.get("value", 0) * 100  # ❌ Should be outside
    self._attr_native_value = processed
except DeviceError:
    _LOGGER.error("Failed")

# Bare exceptions in regular code
try:
    data = await device.get_data()
except Exception:  # ❌ Too broad (unless in config flow/background task)
    _LOGGER.error("Failed")

# Wrong exception type
if end_date < start_date:
    raise ValueError("Invalid dates")  # ❌ Should be ServiceValidationError
```

### 3. Security Vulnerabilities

Check for OWASP Top 10 vulnerabilities:

```python
# ❌ Command Injection
os.system(f"ping {user_input}")  # DANGEROUS

# ✅ Safe alternative
await hass.async_add_executor_job(
    subprocess.run,
    ["ping", user_input],
    check=True
)

# ❌ Exposing secrets in diagnostics
return {"api_key": entry.data[CONF_API_KEY]}  # DANGEROUS

# ✅ Safe alternative
return async_redact_data(entry.data, {CONF_API_KEY, CONF_PASSWORD})
```

### 4. Configuration Flow Patterns

#### ✅ Good Config Flow
```python
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                await self._test_connection(user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # ✅ Allowed in config flow
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_name,
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

### 5. Entity Patterns

#### ✅ Good Entity Patterns
```python
class MySensor(CoordinatorEntity[MyCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "temperature"

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.data[device_id].name,
        )

    @property
    def native_value(self) -> float | None:
        if device_data := self.coordinator.data.get(self.device_id):
            return device_data.temperature
        return None

    @property
    def available(self) -> bool:
        return super().available and self.device_id in self.coordinator.data
```

### 6. Quality Scale Compliance

Review manifest.json and quality_scale.yaml:

```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "codeowners": ["@me"],
  "config_flow": true,
  "integration_type": "device",
  "iot_class": "cloud_polling",
  "quality_scale": "silver"
}
```

Check:
- [ ] All required Bronze rules implemented or exempted
- [ ] Rules match declared quality scale tier
- [ ] Valid exemption reasons provided
- [ ] manifest.json has all required fields

## Performance Patterns

### ✅ Good Performance
```python
# Parallel API calls
temp, humidity = await asyncio.gather(
    api.get_temperature(),
    api.get_humidity(),
)

# Efficient coordinator usage
PARALLEL_UPDATES = 0  # Unlimited for coordinator-based
```

### ❌ Bad Performance
```python
# Sequential API calls
temp = await api.get_temperature()
humidity = await api.get_humidity()  # ❌ Should use gather

# User-configurable scan intervals
vol.Optional("scan_interval"): cv.positive_int  # ❌ Not allowed
```

## Review Process

When reviewing code:

1. **Architecture Review**: Does it follow HA patterns?
2. **Code Quality**: Are async patterns correct? Is error handling comprehensive?
3. **Standards Compliance**: Quality scale requirements met?
4. **Performance & Efficiency**: No blocking operations? Efficient API usage?
5. **User Experience**: Clear error messages? Proper translations?

## Providing Feedback

Structure feedback as:
1. **Summary**: Overall assessment
2. **Critical Issues**: Must fix before merge
3. **Suggestions**: Nice-to-have improvements
4. **Positive Notes**: What's done well

Be specific with file:line references and provide code examples.

## Reference Files

For detailed patterns and best practices, see:
- `.claude/references/diagnostics.md` - Diagnostics implementation
- `.claude/references/sensor.md` - Sensor platform
- `.claude/references/binary_sensor.md` - Binary sensor platform
- `.claude/references/switch.md` - Switch platform
- `.claude/references/button.md` - Button platform
- `.claude/references/number.md` - Number platform
- `.claude/references/select.md` - Select platform
