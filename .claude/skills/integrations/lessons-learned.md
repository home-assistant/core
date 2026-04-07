---
name: lessons-learned
description: Lessons learned from building and reviewing Home Assistant integrations. Consult this when writing new integrations or reviewing PRs to avoid repeating known mistakes.
---

# Lessons Learned - Duco PR Review

Insights gathered during the review process of PR #167220 (Duco integration).

---

## Integration structure

### DeviceInfo belongs in the base entity class
Build DeviceInfo in the base class (DucoEntity.__init__), not in each subclass separately. This keeps device metadata consistent and reduces duplication.

### board_info fetch belongs in coordinator._async_setup
Initial data fetches that can fail (and should trigger ConfigEntryNotReady) belong in _async_setup of the coordinator, not in async_setup_entry. UpdateFailed raised from _async_setup is automatically converted to ConfigEntryNotReady by async_config_entry_first_refresh.

### Separate exception handling for connection vs API errors
Catch connection errors and general API errors separately, including in _async_setup. Reporting "Cannot connect" for an API error is misleading.

### ConfigEntryError vs UpdateFailed in _async_setup
Don't raise `UpdateFailed` for all errors in `_async_setup`. `UpdateFailed` leads to `SETUP_RETRY` (HA will retry indefinitely). Use `ConfigEntryError` for non-transient errors that the user must resolve:

```python
except DucoConnectionError as err:
    raise UpdateFailed(f"Cannot connect: {err}") from err  # transient, retry
except DucoError as err:
    raise ConfigEntryError(f"API error: {err}") from err  # non-transient, SETUP_ERROR
```

Rule of thumb: if retrying won't help (e.g. wrong firmware, unexpected API response), it's `ConfigEntryError`. If the device might just be temporarily unreachable, it's `UpdateFailed`.

---

## Entity availability

### Keep _node non-nullable; use _node_id in coordinator.data for availability
Don't use `Optional[Node]` and scatter `if node is None` checks across properties. Instead, keep `_node` non-nullable and guard with `_node_id in coordinator.data` in the `available` property:

```python
@property
def available(self) -> bool:
    return super().available and self._node_id in self.coordinator.data

@property
def _node(self) -> Node:
    return self.coordinator.data[self._node_id]
```

This is cleaner: `_node` only gets called when `available` is True, and every property stays free of None checks.

### Always override available when doing a node lookup
If an entity looks up a node from coordinator data, always add an available property so the entity becomes unavailable when the node disappears:

    @property
    def available(self) -> bool:
        return super().available and self._node is not None

Without this, the entity stays available while self._node returns None.

---

## Device registry

### Use ATTR_VIA_DEVICE constant, not a string literal
Import `ATTR_VIA_DEVICE` from `homeassistant.const` and use it as a dict key:

```python
device_info[ATTR_VIA_DEVICE] = (DOMAIN, f"{mac}_1")
```

Don't use `"via_device"` as a string or try `DeviceInfo(via_device=...)` in a ternary — `via_device` is typed as `tuple[str, str]`, not `tuple[str, str] | None`.

### Use CONNECTION_NETWORK_MAC for MAC address connections
Import from `homeassistant.helpers.device_registry`:

```python
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
```

### assert mac is not None after reading config_entry.unique_id
`config_entry.unique_id` is typed as `str | None`. Add a guard before using it as a MAC:

```python
mac = coordinator.config_entry.unique_id
assert mac is not None
```

---

## strings.json

### Use common::state keys for standard values
Before writing a custom translation, check if a common key exists. For fan preset modes, prefer:

```json
"auto":   "[%key:common::state::auto%]",
"low":    "[%key:common::state::low%]",
"medium": "[%key:common::state::medium%]",
"high":   "[%key:common::state::high%]"
```

Custom strings like `away`, `low_forced`, `medium_forced`, `high_forced` stay as-is — no common key exists for those.

---

## Link child devices to the main device using via_device
When a coordinator manages multiple physical devices (e.g. a hub + connected modules), set `via_device` in `DeviceInfo` for non-primary devices so they appear as children of the main device in the device registry:

```python
device_info = DeviceInfo(
    identifiers={(DOMAIN, f"{mac}_{node.node_id}")},
    ...
)
if node.general.node_type != "BOX":
    device_info["via_device"] = (DOMAIN, f"{mac}_1")
self._attr_device_info = device_info
```

**Mypy gotcha**: `via_device` is typed as `tuple[str, str]`, not `tuple[str, str] | None`. Don't use a ternary `... if condition else None` — set it conditionally instead.

---

## Fan platform

### Always read the base class before writing an override
Before overriding a property or method (e.g. `is_on`, `percentage`, `state`), read the default implementation in the HA base entity class. The default often already handles the case correctly — for example, `FanEntity.is_on` returns `True` when `preset_mode is not None`, which means an entity in AUTO preset mode is already considered on without any override.

### Use _valid_preset_mode_or_raise() from FanEntity
FanEntity has a built-in _valid_preset_mode_or_raise(preset_mode) method that raises NotValidPresetModeError(ServiceValidationError) with the correct translation keys. Use it instead of a manual check.

### Only add TURN_ON/TURN_OFF if the device can actually stop
If the physical device is always running (e.g. a ventilation unit that you can't actually turn off), don't add `FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF` to `_attr_supported_features`. Keep only `FanEntityFeature.PRESET_MODE`. Adding turn_on/turn_off for a device that's always on is misleading to users.

### Filter platform entities on node type, not on optional data presence
When a coordinator fetches multiple device types, filter in platform setup with an explicit type check rather than checking if optional data is present:

```python
# Good
entities = [DucoFanEntity(coordinator, node) for node in coordinator.data.values() if node.general.node_type == "BOX"]

# Bad - fragile, breaks if the field is present on other node types too
entities = [DucoFanEntity(coordinator, node) for node in coordinator.data.values() if node.ventilation is not None]
```

### Don't update state optimistically and revert on error
Don't assign `_attr_preset_mode` (or similar) immediately on a service call and then revert if the API call fails. Let the coordinator's next refresh update the state. Optimistic updates add complexity and can leave the UI in an inconsistent state if the revert logic is missed.

### ServiceValidationError vs HomeAssistantError
- Invalid input (e.g. invalid preset_mode): ServiceValidationError
- Network/API failure: HomeAssistantError

This is explicit in the action-exceptions quality scale rule:
https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/

### PARALLEL_UPDATES
- Write platforms (fan): PARALLEL_UPDATES = 1
- Read-only platforms (sensor): PARALLEL_UPDATES = 0

---

## Config flow

### _validate_input helper pattern
Extract connection validation into a separate method. Let exceptions propagate - the caller (async_step_user) catches them and maps them to error keys. This makes reuse in reconfigure/reauth steps straightforward.

### VERSION and MINOR_VERSION
Explicitly present in gold/platinum integrations - makes the migration schema visible without having to know the defaults. Can be omitted in new integrations, but keeping them is not wrong either.

---

## Testing

### Use snapshot_platform instead of manual state assertions
Don't assert individual state values and unique_ids manually. Use `snapshot_platform` from `tests.common` — it captures all entities registered for a config entry and compares against a stored snapshot:

```python
from tests.common import snapshot_platform

async def test_fan_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
```

Generate initial snapshots with `pytest --snapshot-update`. Commit the `.ambr` file.

### autospec=True in fixtures makes spec= on individual mocks redundant
If a fixture creates a mock with `autospec=True`, don't also pass `spec=SomeClass` when configuring return values. The spec is already applied.

### With autospec=True, use .return_value = directly — don't reassign with AsyncMock
When patching with `autospec=True`, coroutine methods on the mock are already `AsyncMock` instances. Reassigning them with `AsyncMock(return_value=...)` throws away the autospec and replaces the method with an unspecced mock:

```python
# Wrong — discards autospec on the method:
client.async_get_board_info = AsyncMock(return_value=mock_board_info)

# Correct — keep the autospec, just set the return value:
client.async_get_board_info.return_value = mock_board_info
```

### Use add_to_hass in duplicate-entry detection tests
For tests that verify the "already_configured" abort, seed the registry with `mock_config_entry.add_to_hass(hass)` directly instead of running a full config flow first. The test is about duplicate detection, not about the create-entry flow:

```python
async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)  # seed existing entry
    result = await hass.config_entries.flow.async_init(...)
    result = await hass.config_entries.flow.async_configure(...)
    assert result["reason"] == "already_configured"
```

### Add match= to pytest.raises for exception message coverage
Include `match=` in `pytest.raises` calls to verify the error message, not just the type:

```python
with pytest.raises(HomeAssistantError, match="Failed to set ventilation state"):
    ...
```

**Exception**: `match=` does NOT work for translated exceptions (`ConfigEntryAuthFailed`, `ConfigEntryNotReady`, `HomeAssistantError` raised with `translation_domain` + `translation_key`) when the test runs outside a hass context. Calling `str()` on these exceptions triggers `async_get_hass()` which raises `HomeAssistantError: async_get_hass called from the wrong thread`. In that case, just check the type.

### Use init_integration fixture in test_init.py
Don't manually call `add_to_hass` + `async_setup` in setup/unload tests. Use the `init_integration` fixture so setup tests stay focused on the assertion, not the setup itself.

### Patch both integration and config_flow import paths in one fixture
When a client class is imported in two places (e.g. `homeassistant.components.duco` and `homeassistant.components.duco.config_flow`), patch both in a single fixture using `new=mock_class`:

```python
mock_class = AsyncMock(spec=DucoClient)
mock_class.return_value = mock  # the instance

with (
    patch("homeassistant.components.duco.DucoClient", new=mock_class),
    patch("homeassistant.components.duco.config_flow.DucoClient", new=mock_class),
):
    yield mock
```

This avoids having to patch in every individual test and ensures both paths use the same mock instance.

### Prefer end-to-end setup with freezer for unavailability tests
Core members prefer simulating a real polling cycle over calling `async_refresh()` directly. Use `freezer.tick()` + `async_fire_time_changed` + `async_block_till_done(wait_background_tasks=True)`:

```python
freezer.tick(SCAN_INTERVAL)
async_fire_time_changed(hass)
await hass.async_block_till_done(wait_background_tasks=True)
```

This tests the full polling path including the scheduler, instead of bypassing it with a direct `async_refresh()` call. The `freezer` fixture is provided by `pytest-freezegun`, which HA already includes.

Do NOT use `hass.config_entries.async_reload()` — a failed reload removes entities instead of marking them unavailable.

### Parametrize tests that differ only in input/exception
When multiple tests share the same structure and differ only in a value (exception type, preset mode, expected result), combine them with `@pytest.mark.parametrize`. This reduces duplication, makes the test suite easier to extend, and keeps test names descriptive (e.g. `test_fan_set_preset_mode[high-MAN3]`).

Examples of good candidates:
- Error path tests that cover multiple exception types (DucoConnectionError, DucoError)
- Preset mapping tests where each case is `(preset_mode, expected_duco_state)`

Pattern:
```python
@pytest.mark.parametrize(
    ("preset_mode", "expected_duco_state"),
    [
        ("high", "MAN3"),
        ("away", "EMPT"),
    ],
)
async def test_fan_set_preset_mode(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    preset_mode: str,
    expected_duco_state: str,
) -> None:
    ...
```

---

## PR review process

### Reviewer authority
- CHANGES_REQUESTED from a CONTRIBUTOR does NOT block merge - only reviews from MEMBER or OWNER are enforced by branch protection.
- Still respond respectfully and with substance, but you do not have to accept every suggestion.

### Outdated inline comments are not gone
After pushing new commits, GitHub marks inline review comments as "outdated" — they don't disappear. To find them:
- **Files changed tab**: look for the grey "N outdated" badge on each file and click it
- **Conversation tab**: all comments appear in chronological order, including outdated ones (without code context)

After addressing all comments, post individual replies per thread (not a single summary comment), then click **Re-request review** on the reviewer in the PR sidebar.

### Single platform rule for new integrations
HA requires new integrations to be limited to a single platform in the first PR. Small exceptions (e.g. a trivial 50-line read-only sensor reusing the same coordinator) are debatable, but the rule is strictly meant to reduce review burden.

### Do not export __all__
In an integration's __init__.py, __all__ is not needed - nothing outside the integration imports from it directly.

---

# Lessons Learned - EVE Online PR Review

Insights gathered during the review process of PR #166674 (EVE Online integration, reviewer: joostlek).

---

## Scope - first PR

### Keep the first PR minimal
Start small: get the core flow working (config flow, coordinator, one or two platforms). Diagnostics, reauth, and reconfigure belong in follow-up PRs. Start with fewer entities too.

### Diagnostics and reauth → separate PRs
joostlek explicitly: "Please make sure you get rid of diagnostics and reauth flow, that can happen in a later PR."

---

## Sensors

### SensorStateClass: TOTAL is only for monotonically increasing values
`SensorStateClass.TOTAL` (and `TOTAL_INCREASING`) is reserved for values that can never decrease (e.g. odometer, energy counters). If a value can go down (skill points, wallet balance), use `SensorStateClass.MEASUREMENT`.

### Use typed unit constants where available
Prefer typed unit constants over plain strings where a constant exists:
- `UnitOfTime.SECONDS` not `"s"`
- `UnitOfInformation.MEGABYTES` not `"MB"`

**Note**: `UnitOfCurrency` does NOT exist in HA. For currency units like ISK, EUR, USD, use the plain string. For common currencies, `CURRENCY_EURO`, `CURRENCY_DOLLAR`, `CURRENCY_CENT` constants exist in `homeassistant.const`; for others (like ISK), use plain strings: `native_unit_of_measurement="ISK"`.

**Conflict**: If a sensor's `unit_of_measurement` is defined in `strings.json` entity translations, do NOT also set `native_unit_of_measurement` in the Python entity description. HA raises `ValueError: has a translation key for unit_of_measurement '...', but also has a native_unit_of_measurement '...'`. Use one or the other — translation key for user-facing units, `native_unit_of_measurement` for programmatic units.

---

## Config flow

### Use pyjwt for JWT decoding
Use `jwt.decode(token, options={"verify_signature": False})` instead of manual base64 parsing. Always wrap in try/except for `ValueError | KeyError`. Other integrations (e.g. aladdin_connect) do it this way.

### CONF_ constants for custom keys
Don't use string literals for config entry data keys. Define `CONF_CHARACTER_ID`, `CONF_CHARACTER_NAME`, etc. in `const.py` and import them.

---

## Entities

### No DOMAIN prefix in unique_id
The config entry already provides namespace isolation. `f"{entry.entry_id}_{character_id}"` is sufficient; no need to add `DOMAIN` prefix.

### Shared entities across config entries cause unique_id collisions
If server/hub entities are created per config entry, adding a second character entry will try to register the same unique_id twice. Simplest fix: don't create shared entities at all. If you need them, use a dedicated "server" config entry type or a separate coordinator shared across entries.

### integration_type for OAuth2 per-character integrations
Use `integration_type: service` (not `hub`) when each config entry represents an individual account/character in a broader service.

---

## Error handling

### Map authentication errors to ConfigEntryAuthFailed
When an API call fails due to expired/invalid tokens, catch the integration-specific auth error and raise `ConfigEntryAuthFailed`. This triggers HA's built-in reauth flow. Don't re-raise the library error directly.

### Translation placeholders must match the translation string
If a translation string contains `{error}`, always pass `translation_placeholders={"error": str(err)}`. Without it, the literal `{error}` appears in the UI.

---

## Python style

### Generator expression for conditional count
Prefer `sum(1 for x in items if condition)` over `len([x for x in items if condition])`. The former avoids building an intermediate list.

---

## quality_scale.yaml

### Must be complete and in sync
Add all rules and mark each one with its correct status. An incomplete quality_scale.yaml is a review blocker.
