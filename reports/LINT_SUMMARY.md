# Lint Summary Report: openh264customh264Integration

**Date:** 2025-10-22  
**Integration Path:** `homeassistant/components/openh264customh264/`  
**Python Version:** 3.13.9  
**Tools:** Ruff 0.13.0, Pylint 4.0.1

---

## Executive Summary

✅ **Formatting:** All files properly formatted  
✅ **JSON/YAML:** All configuration files valid  
⚠️  **Ruff Issues:** 30 errors found (mostly fixable)  
⚠️  **Pylint Issues:** ~40+ Home Assistant-specific warnings  

---

## Detailed Results

### 1. Code Formatting (Ruff Format)
**Status:** ✅ PASS  
**Result:** 7 files already formatted  
**Action:** None required

### 2. JSON/YAML Validation
**Status:** ✅ PASS  
**Files Checked:**
- `manifest.json` - ✓ Valid
- `strings.json` - ✓ Valid
- `translations/en.json` - ✓ Valid

### 3. Ruff Linting  
**Status:** ⚠️ 30 ISSUES FOUND

#### Issue Breakdown by Category:

**Exception Handling (15 issues):**
- `BLE001`: Do not catch blind exception `Exception` (11 occurrences)
  - Files: `__init__.py`, `camera.py`, `encoder.py`, `lib.py`
  - Fix: Catch specific exceptions like `OSError`, `ValueError`, etc.
  
- `B904`: Missing `raise ... from err` (7 occurrences)
  - Files: `__init__.py`
  - Fix: Use `raise ... from err` or `raise ... from None`

**Code Quality (8 issues):**
- `C901`: Function too complex (1)
  - `_async_register_services` is too complex (63 > 25)
  - Fix: Refactor into smaller functions

- `TRY300`: Consider moving statement to `else` block (2)
  - Fix: Move success path to else block after except

- `TRY301`: Abstract `raise` to inner function (5)
  - Fix: Move raise statements to helper functions

**Async Best Practices (1 issue):**
- `ASYNC230`: Async functions should not use blocking `open()` (1)
  - Line 390 in `__init__.py`
  - Fix: Use `aiofiles` or move file operations to executor

**Other (6 issues):**
- `RUF059`: Unpacked variable never used (2)
  - Variables: `stdout` (lines 288, 488)
  - Fix: Use `_` for unused variables

- `PLC0415`: Import not at top level (1)
  - `encoder.py` line 107
  - Fix: Move import to top or guard with TYPE_CHECKING

### 4. Pylint (Home Assistant Specific)
**Status:** ⚠️ ~40+ WARNINGS

#### Issue Breakdown:

**Logger Formatting (16 warnings):**
- `W7401 (hass-logger-period)`: Logger messages must not end with period (2)
- `W7402 (hass-logger-capital)`: Logger messages must start with capital (14)
  - Affects: `__init__.py` lines 106, 160, 180, 191, 243, 247, 257, 261, 505, 570

**Type Hints (16 warnings):**
- `W7432 (hass-return-type)`: Incorrect return type annotations (10)
  - Files: `diagnostics.py`, `encoder.py`, `camera.py`, `config_flow.py`
  - Missing proper type hints for:
    - `__init__` methods → should be `None`
    - Config flow methods → should be `ConfigFlowResult`
    - Device info → should be `DeviceInfo | None`
    
- `W7431 (hass-argument-type)`: Incorrect argument type annotations (6)
  - Files: `camera.py`, `config_flow.py`, `__init__.py`
  - Need to use proper HA types like `AddConfigEntryEntitiesCallback`

**Code Structure (3 warnings):**
- `W7471 (hass-async-callback-decorator)`: Coroutine should not use `@callback` (1)
  - Line 87: `_async_update_listener` - remove `@callback` or make it sync
  
- `R6102 (consider-using-tuple)`: Use tuple instead of list (1)
  - `diagnostics.py` line 17

---

## Priority Fixes

### 🔴 HIGH PRIORITY

1. **Fix `@callback` decorator issue** (Line 87)
   ```python
   # Remove @callback decorator from coroutine
   # @callback  ← Remove this
   async def _async_update_listener(...):
   ```

2. **Add proper type hints** (16 locations)
   ```python
   # Example fixes:
   def __init__(...) -> None:
   async def async_step_user(...) -> ConfigFlowResult:
   def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
   ```

3. **Fix exception handling** (15 locations)
   ```python
   # Instead of:
   except Exception as e:
       raise HomeAssistantError(...)
   
   # Use:
   except (OSError, ValueError) as err:
       raise HomeAssistantError(...) from err
   ```

### 🟡 MEDIUM PRIORITY

4. **Refactor complex function** (`_async_register_services`)
   - Split into smaller helper functions
   - Complexity: 63 → target < 25

5. **Fix logger message formatting**
   - Capitalize first letter of user-facing messages
   - Remove trailing periods

6. **Fix async file operations** (Line 390)
   ```python
   # Use aiofiles or run_in_executor
   async with aiofiles.open(h264_temp_path, "wb") as h264_file:
   ```

### 🟢 LOW PRIORITY

7. **Use `_` for unused variables**
   ```python
   _, stderr = await process.communicate()  # Instead of: stdout, stderr
   ```

8. **Move imports to top level**
   - `encoder.py` line 107

---

## Auto-Fixable Issues

Ruff can auto-fix some issues safely:

```bash
cd /Users/martinpark/Projects/Python/homeassistant-core
./.venv/bin/ruff check --fix homeassistant/components/openh264customh264/
```

**Auto-fixable:**
- `RUF059`: Unused unpacked variables → rename to `_`
- Some `B904`: Add `from err` to raise statements (with --unsafe-fixes)

**Manual fixes required:**
- Exception type specificity (`BLE001`)
- Type hints (`W7432`, `W7431`)
- Logger formatting (`W7401`, `W7402`)
- Function complexity (`C901`)
- Async file operations (`ASYNC230`)

---

## Files Requiring Attention

### Critical Files:
1. **`__init__.py`** - 24 issues (most complex, needs refactoring)
2. **`config_flow.py`** - 8 type hint warnings
3. **`camera.py`** - 5 issues (exception handling + types)
4. **`encoder.py`** - 4 issues
5. **`diagnostics.py`** - 2 issues
6. **`lib.py`** - 1 issue

---

## Next Steps

### Immediate Actions:
1. ✅ **Run auto-fixes**
   ```bash
   ./.venv/bin/ruff check --fix homeassistant/components/openh264customh264/
   ```

2. ✅ **Fix type hints** - Add proper return types and argument types

3. ✅ **Fix logger messages** - Capitalize and remove periods

4. ✅ **Fix exception handling** - Be specific with exception types

5. ✅ **Refactor complex function** - Break down `_async_register_services`

### Validation:
After fixes, re-run linters:
```bash
./.venv/bin/ruff check homeassistant/components/openh264customh264/
./.venv/bin/pylint homeassistant/components/openh264customh264/
```

---

## References

- **Ruff Rules:** https://docs.astral.sh/ruff/rules/
- **Home Assistant Type Hints:** https://developers.home-assistant.io/docs/development_typing
- **Home Assistant Code Style:** https://developers.home-assistant.io/docs/development_guidelines

---

## Report Files

All detailed reports available in `reports/`:
- `ruff_format.txt` - Formatting check results
- `ruff.txt` - Ruff linting detailed output
- `pylint.txt` - Pylint detailed output
- `json_validation.txt` - JSON/YAML validation results
