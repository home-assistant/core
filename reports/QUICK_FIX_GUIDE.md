# Quick Fix Guide - openh264customh264

This guide provides copy-paste fixes for the most common issues found in linting.

## 1. Run Auto-Fixes First ⚡

```bash
cd /Users/martinpark/Projects/Python/homeassistant-core

# Auto-fix what Ruff can handle safely
./.venv/bin/ruff check --fix homeassistant/components/openh264customh264/

# Format code
./.venv/bin/ruff format homeassistant/components/openh264customh264/
```

## 2. Fix Type Hints (Required for all files)

### `__init__.py`

**Line 265:** Add type hint to `_encode_with_shim`
```python
async def _encode_with_shim(
    hass: HomeAssistant,  # Change from: hass
    input_path: str,
    output_path: str,
    bitrate: str,
    fps: int,
    gop: int,
) -> None:
```

**Line 87:** Remove `@callback` decorator (coroutines can't use it)
```python
# Remove this line:
# @callback
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
```

### `config_flow.py`

Add imports at top:
```python
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
```

**Line 57:** Fix async_step_user return type
```python
async def async_step_user(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:  # Add this return type
```

**Line 92:** Fix async_get_options_flow
```python
@staticmethod
@callback
def async_get_options_flow(
    config_entry: ConfigEntry,  # Change type
) -> OptionsFlow:  # Add return type
    """Get the options flow for this handler."""
    return OpenH264CustomH264OptionsFlow(config_entry)
```

**Line 100 & 104:** Fix OptionsFlow init and step
```python
def __init__(self, config_entry: ConfigEntry) -> None:  # Add return type
    """Initialize OpenH264 options flow."""
    self.config_entry = config_entry

async def async_step_init(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:  # Add return type
```

### `camera.py`

Add import at top:
```python
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
```

**Line 31:** Fix async_setup_entry
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,  # Fix type
) -> None:
```

**Line 54:** Fix __init__
```python
def __init__(
    self,
    hass: HomeAssistant,
    name: str,
    mode: str,
    entity_id: str | None,
    stream_url: str | None,
    snapshot_url: str | None,
    entry_id: str,
) -> None:  # Add return type
```

**Line 127:** Fix device_info
```python
@property
def device_info(self) -> DeviceInfo | None:  # Add return type
```

### `encoder.py`

**Line 53:** Fix __init__
```python
def __init__(
    self,
    width: int,
    height: int,
    fps: int,
    bitrate: int,
    keyint: int = 60,
    threads: int = 1,
    lib_path: str | None = None,
) -> None:  # Add return type
```

### `diagnostics.py`

Add import at top:
```python
from collections.abc import Mapping
```

**Line 11:** Fix return type
```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> Mapping[str, Any]:  # Change from dict
```

**Line 17:** Change list to tuple
```python
"lib_search_paths": (  # Change from [
    "/usr/lib",
    "/usr/local/lib",
    "/opt/homebrew/lib",
),  # Change from ]
```

## 3. Fix Exception Handling

### Pattern to Replace:

```python
# BAD - Don't do this
except Exception as e:
    LOGGER.error("Failed: %s", e)
    raise HomeAssistantError(f"Failed: {e}")

# GOOD - Do this instead
except (OSError, ValueError, subprocess.SubprocessError) as err:
    LOGGER.error("Failed: %s", err)
    raise HomeAssistantError(f"Failed: {err}") from err
```

### Specific Locations in `__init__.py`:

**Line 46, 144, 168, 260, 436, 558, 657:**
```python
# Replace:
except Exception as e:
# With:
except (OSError, subprocess.SubprocessError, ValueError) as err:

# And replace:
raise HomeAssistantError(...)
# With:
raise HomeAssistantError(...) from err
```

### In `camera.py` (Lines 105, 121):

```python
# Replace:
except Exception as err:
    LOGGER.warning("Failed to ...: %s", err)
# With:
except (aiohttp.ClientError, asyncio.TimeoutError) as err:
    LOGGER.warning("Failed to ...: %s", err)
```

### In `encoder.py` (Line 224):

```python
# Replace:
except Exception as e:
# With:
except (OSError, ctypes.ArgumentError) as err:
```

### In `lib.py` (Line 41):

```python
# Replace:
except Exception:
# With:
except (OSError, FileNotFoundError):
```

## 4. Fix Logger Messages

### Capitalize and remove periods:

```python
# BAD
LOGGER.info("encode_file service called: %s -> %s", ...)
LOGGER.warning("ffmpeg not found in PATH")
LOGGER.info("OpenH264 encoder initialized successfully: %s", ...)

# GOOD
LOGGER.debug("Encode_file service called: %s -> %s", ...)  # Lowercase = use debug
LOGGER.warning("Ffmpeg not found in PATH")  # Or capitalize first letter
LOGGER.info("OpenH264 encoder initialized successfully: %s", ...)  # Remove period
```

### Specific Changes in `__init__.py`:

- Line 47: Remove period from "OpenH264 encoder initialized successfully: %s."
- Line 106, 160, 180, 191, 243, 247, 257, 261, 505, 570: Capitalize first letter or downgrade to `LOGGER.debug()`

## 5. Fix Unused Variables

```python
# Line 288 and 488:
# Replace:
stdout, stderr = await result.communicate()
# With:
_, stderr = await result.communicate()
```

## 6. Fix Async File Operations (Line 390)

**Option A: Use aiofiles (recommended)**

Add to requirements:
```python
import aiofiles

# Replace:
with open(h264_temp_path, "wb") as h264_file:
    # ... frame processing
# With:
async with aiofiles.open(h264_temp_path, "wb") as h264_file:
    # ... frame processing (use await for writes)
    await h264_file.write(encoded_data)
```

**Option B: Use executor**
```python
def write_frames_sync(h264_temp_path, frames):
    with open(h264_temp_path, "wb") as h264_file:
        for frame in frames:
            h264_file.write(frame)

# Then call:
await hass.async_add_executor_job(write_frames_sync, h264_temp_path, frames)
```

## 7. Move Import to Top (encoder.py Line 107)

```python
# At top of file, add:
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ctypes

# Or simply move the import to the top if it's always needed
```

## 8. Validation Commands

After making changes:

```bash
# Check formatting
./.venv/bin/ruff format --check homeassistant/components/openh264customh264/

# Check linting
./.venv/bin/ruff check homeassistant/components/openh264customh264/

# Check with Pylint
./.venv/bin/pylint homeassistant/components/openh264customh264/

# Run all checks
./.venv/bin/ruff check homeassistant/components/openh264customh264/ && \
./.venv/bin/pylint homeassistant/components/openh264customh264/ && \
echo "✅ All checks passed!"
```

## 9. Complexity Reduction (Future Work)

The `_async_register_services` function (line 93) is too complex. Consider:

1. **Extract service handlers to separate module:**
```python
# Create: homeassistant/components/openh264customh264/services.py

async def handle_encode_file(hass, call):
    """Handle encode_file service call."""
    # ... move implementation here

async def handle_capture_snapshot(hass, call):
    """Handle capture_snapshot service call."""
    # ... move implementation here

async def handle_record_clip(hass, call):
    """Handle record_clip service call."""
    # ... move implementation here
```

2. **Extract helper functions:**
```python
async def _encode_with_ffmpeg_openh264(...): # Keep separate
async def _encode_with_shim(...): # Keep separate
async def _wrap_h264_in_mp4(...): # Keep separate
def _parse_video_info(...): # Keep separate
```

---

## Summary Checklist

- [ ] Run `ruff check --fix` and `ruff format`
- [ ] Add all missing type hints (16 locations)
- [ ] Fix exception handling (15 locations)
- [ ] Fix logger message formatting (16 locations)
- [ ] Replace unused `stdout` with `_` (2 locations)
- [ ] Remove `@callback` from coroutine (1 location)
- [ ] Fix async file operations (1 location)
- [ ] Move import to top (1 location)
- [ ] Run validation commands
- [ ] Consider refactoring complex function (future)

After completing these fixes, you should have < 5 lint issues remaining!
