# Vizio Integration: Coordinator Migration and Remote Entity

## Overview

Add a remote entity platform for the vizio integration and migrate the media player to use a coordinator for all device polling.

**Two PRs:**
1. **PR 1:** Migrate all API calls to coordinator pattern
2. **PR 2:** Add remote entity platform

## PR 1: Coordinator Migration

### Design Principle

Move **all** device API calls from the media player's `async_update()` to the coordinator. The coordinator fetches raw data from the device and stores it in a dataclass. The media player then applies business logic to transform this data into entity state.

**Separation of concerns:**
- **Coordinator:** Fetches and caches raw API responses
- **Media Player:** Interprets data and manages entity state

### New: VizioDeviceData

**File:** `homeassistant/components/vizio/coordinator.py`

```python
@dataclass
class VizioDeviceData:
    """Raw data fetched from Vizio device."""

    # Power state (None = unavailable)
    is_on: bool | None

    # Audio settings from get_all_settings("audio")
    audio_settings: dict[str, Any] | None

    # Sound mode options from get_setting_options("audio", "eq")
    sound_mode_list: list[str] | None

    # Current input from get_current_input()
    current_input: str | None

    # Available inputs from get_inputs_list()
    input_list: list[str] | None

    # Current app config from get_current_app_config() (TVs only)
    current_app_config: AppConfig | None

    # Device info (fetched once)
    model: str | None
    version: str | None
```

### New: VizioDeviceCoordinator

**File:** `homeassistant/components/vizio/coordinator.py`

```python
class VizioDeviceCoordinator(DataUpdateCoordinator[VizioDeviceData]):
    """Coordinator for Vizio device data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: VizioAsync,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.device = device
        self._device_info_fetched = False

    async def _async_update_data(self) -> VizioDeviceData:
        """Fetch all device data."""
        # Always try power state first
        is_on = await self.device.get_power_state(log_api_exception=False)

        # Handle unavailable
        if is_on is None:
            return VizioDeviceData(
                is_on=None,
                audio_settings=None,
                sound_mode_list=None,
                current_input=None,
                input_list=None,
                current_app_config=None,
                model=None,
                version=None,
            )

        # Handle device off - return minimal data
        if not is_on:
            return VizioDeviceData(
                is_on=False,
                audio_settings=None,
                sound_mode_list=None,
                current_input=None,
                input_list=None,
                current_app_config=None,
                model=self.data.model if self.data else None,
                version=self.data.version if self.data else None,
            )

        # Device is on - fetch all data
        audio_settings = await self.device.get_all_settings(
            "audio", log_api_exception=False
        )

        sound_mode_list = None
        if audio_settings and "eq" in audio_settings:
            sound_mode_list = await self.device.get_setting_options(
                "audio", "eq", log_api_exception=False
            )

        current_input = await self.device.get_current_input(log_api_exception=False)
        input_list_raw = await self.device.get_inputs_list(log_api_exception=False)
        input_list = [i.name for i in input_list_raw] if input_list_raw else None

        current_app_config = await self.device.get_current_app_config(
            log_api_exception=False
        )

        # Device info - fetch once
        model = None
        version = None
        if not self._device_info_fetched:
            model = await self.device.get_model_name(log_api_exception=False)
            version = await self.device.get_version(log_api_exception=False)
            self._device_info_fetched = True
        elif self.data:
            model = self.data.model
            version = self.data.version

        return VizioDeviceData(
            is_on=True,
            audio_settings=audio_settings,
            sound_mode_list=sound_mode_list,
            current_input=current_input,
            input_list=input_list,
            current_app_config=current_app_config,
            model=model,
            version=version,
        )
```

### New: VizioRuntimeData

**File:** `homeassistant/components/vizio/__init__.py`

```python
@dataclass
class VizioRuntimeData:
    """Runtime data for Vizio integration."""

    device: VizioAsync
    device_coordinator: VizioDeviceCoordinator
    apps_coordinator: VizioAppsDataUpdateCoordinator | None  # None for speakers

type VizioConfigEntry = ConfigEntry[VizioRuntimeData]
```

Replaces current `hass.data[DOMAIN]` pattern for device storage with typed `ConfigEntry.runtime_data`.

### Media Player Changes

**File:** `homeassistant/components/vizio/media_player.py`

1. Inherit from `CoordinatorEntity[VizioDeviceCoordinator]` and `MediaPlayerEntity`
2. Remove `async_update()` method entirely
3. Override `_handle_coordinator_update()` to apply business logic:

```python
@callback
def _handle_coordinator_update(self) -> None:
    """Handle updated data from the coordinator."""
    data = self.coordinator.data

    # Update device registry info (once)
    if data.model and data.version and not self._received_device_info:
        self._update_device_registry(data.model, data.version)
        self._received_device_info = True

    # Handle unavailable - just write state
    if data.is_on is None:
        self.async_write_ha_state()
        return

    # Handle device off
    if not data.is_on:
        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = None
        self._attr_is_volume_muted = None
        self._current_input = None
        self._attr_app_name = None
        self._current_app_config = None
        self._attr_sound_mode = None
        self.async_write_ha_state()
        return

    # Device is on - apply business logic to coordinator data
    self._attr_state = MediaPlayerState.ON

    # Audio settings
    if data.audio_settings:
        self._attr_volume_level = (
            float(data.audio_settings.get("volume", 0)) / self._max_volume
        )
        if "mute" in data.audio_settings:
            self._attr_is_volume_muted = (
                data.audio_settings["mute"].lower() == "on"
            )
        if "eq" in data.audio_settings:
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.SELECT_SOUND_MODE
            )
            self._attr_sound_mode = data.audio_settings["eq"]
            self._attr_sound_mode_list = data.sound_mode_list or []
        else:
            self._attr_supported_features &= (
                ~MediaPlayerEntityFeature.SELECT_SOUND_MODE
            )

    # Input state
    if data.current_input:
        self._current_input = data.current_input
    if data.input_list:
        self._available_inputs = data.input_list

    # App state (TV only)
    if (
        self._attr_device_class != MediaPlayerDeviceClass.SPEAKER
        and data.input_list
        and any(app in data.input_list for app in INPUT_APPS)
    ):
        self._available_apps = self._apps_list(
            [app["name"] for app in self._all_apps or ()]
        )
        self._current_app_config = data.current_app_config
        self._attr_app_name = find_app_name(
            self._current_app_config,
            [APP_HOME, *(self._all_apps or ()), *self._additional_app_configs],
        )
        if self._attr_app_name == NO_APP_RUNNING:
            self._attr_app_name = None

    self.async_write_ha_state()
```

4. Availability based on coordinator data:
```python
@property
def available(self) -> bool:
    return self.coordinator.data is not None and self.coordinator.data.is_on is not None
```

### Init Changes

**File:** `homeassistant/components/vizio/__init__.py`

- Create `VizioAsync` device in `async_setup_entry`
- Create `VizioDeviceCoordinator` with the device
- Call `await coordinator.async_config_entry_first_refresh()`
- Store in `entry.runtime_data = VizioRuntimeData(...)`
- Keep `VizioAppsDataUpdateCoordinator` shared via `hass.data[DOMAIN][CONF_APPS]` for TVs

### Testing (PR 1)

**Update fixtures in `conftest.py`:**
- Mock `VizioDeviceCoordinator._async_update_data` to return `VizioDeviceData`
- Keep existing device method mocks for service call tests

**Existing tests should pass** with fixture updates since:
- Same state values exposed through entity
- Same service call behavior (device methods still mocked)

**New coordinator tests:**
- Test unavailable state when `get_power_state` returns `None`
- Test off state data
- Test on state with full data fetch
- Test device info fetched only once

---

## PR 2: Remote Entity

### New: Remote Platform

**File:** `homeassistant/components/vizio/remote.py`

**Entity setup:**
- Created for all device classes (TV and Speaker)
- Inherits from `CoordinatorEntity[VizioDeviceCoordinator]` and `RemoteEntity`
- Uses same coordinator as media player (from `entry.runtime_data`)

**Properties:**
```python
@property
def is_on(self) -> bool | None:
    return self.coordinator.data.is_on if self.coordinator.data else None
```

**Commands:**
- `async_turn_on()` → calls `device.pow_on()`
- `async_turn_off()` → calls `device.pow_off()`
- `async_send_command(command, **kwargs)` → sends remote key commands

**Command handling:**
```python
async def async_send_command(self, command: Iterable[str], **kwargs) -> None:
    # Get device-specific key mapping from pyvizio
    key_mapping = PYVIZIO_KEY_MAPPING[self._device_class]

    # Convert all commands to uppercase
    keys = [cmd.upper() for cmd in command]

    # Validate ALL commands first before sending any
    invalid_keys = [k for k in keys if k not in key_mapping]
    if invalid_keys:
        raise ServiceValidationError(
            f"Unknown command(s): {', '.join(invalid_keys)}",
            translation_key="unknown_command",
        )

    # All valid - now send them
    for key in keys:
        await self._device.remote(key)
```

- Pre-validation: checks all commands before sending any
- Device-specific mapping: uses correct key mapping for TV vs Speaker
- Case-insensitive: converts input to uppercase for lookup

### Platform Registration

**File:** `homeassistant/components/vizio/__init__.py`

```python
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]
```

### Testing (PR 2)

**New file:** `tests/components/vizio/test_remote.py`

- Test entity creation for TV and Speaker
- Test `is_on` state from coordinator
- Test `turn_on` / `turn_off` commands
- Test `send_command` with valid commands
- Test `send_command` validation fails for invalid commands (before any sent)
- Test case-insensitive command handling
- Test device-specific key mappings (TV vs Speaker)

---

## Implementation Order

1. **PR 1:** Coordinator migration (prerequisite for PR 2)
   - Create `VizioDeviceData` dataclass
   - Create `VizioDeviceCoordinator` with full data fetching
   - Create `VizioRuntimeData`
   - Update `__init__.py` setup
   - Update `media_player.py` to use coordinator data with business logic
   - Update test fixtures
   - Add coordinator tests

2. **PR 2:** Remote entity (depends on PR 1)
   - Add `remote.py`
   - Update `PLATFORMS` list
   - Add translation keys for errors
   - Add remote entity tests
