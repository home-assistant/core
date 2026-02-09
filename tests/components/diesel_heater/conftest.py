"""Shared test fixtures for Diesel Heater tests.

For pure-Python tests (protocol, helpers) we stub out the homeassistant
package so that ``custom_components.diesel_heater`` can be imported without
having Home Assistant installed.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


class _HAStubFinder:
    """Meta-path finder that intercepts homeassistant.* and bleak* imports.

    Returns a fresh MagicMock-based module for any submodule, so that
    ``from homeassistant.components.recorder import get_instance`` works
    without the real HA package installed.
    """

    _PREFIXES = ("homeassistant", "bleak", "bleak_retry_connector")

    def find_module(self, fullname, path=None):
        for prefix in self._PREFIXES:
            if fullname == prefix or fullname.startswith(prefix + "."):
                return self
        return None

    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]
        mod = types.ModuleType(fullname)
        mod.__path__ = []          # make it a package
        mod.__loader__ = self
        mod.__spec__ = None
        # Attribute access returns MagicMock so `from x import y` works
        mod.__getattr__ = lambda name: MagicMock()
        sys.modules[fullname] = mod
        return mod


# Install the finder BEFORE any test import
sys.meta_path.insert(0, _HAStubFinder())

# Ensure custom_components is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Config flow stubs
# ---------------------------------------------------------------------------
# Provide real base classes so that
#   class Foo(config_entries.ConfigFlow, domain=DOMAIN): ...
# produces a proper class (not a MagicMock).

class _AbortFlow(Exception):
    """Stub for homeassistant.data_entry_flow.AbortFlow."""

    def __init__(self, reason="", description_placeholders=None):
        self.reason = reason
        self.description_placeholders = description_placeholders or {}
        super().__init__(reason)


class _StubConfigFlow:
    """Stub for homeassistant.config_entries.ConfigFlow.

    Tests can set ``_existing_unique_ids`` (set) to make
    ``_abort_if_unique_id_configured()`` raise AbortFlow.
    Tests can set ``_current_ids`` (set) to control ``_async_current_ids()``.
    """

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if domain:
            cls.domain = domain

    async def async_set_unique_id(self, unique_id: str):
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        existing = getattr(self, "_existing_unique_ids", set())
        if getattr(self, "_unique_id", None) in existing:
            raise _AbortFlow("already_configured")

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(
        self, *, step_id, data_schema=None, errors=None, description_placeholders=None
    ):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {},
        }

    def async_abort(self, *, reason, description_placeholders=None):
        return {"type": "abort", "reason": reason}

    def _set_confirm_only(self):
        pass

    def _async_current_ids(self):
        return getattr(self, "_current_ids", set())

    @property
    def hass(self):
        # Lazy init: subclass __init__ may not call super().__init__()
        if not hasattr(self, "_hass"):
            self._hass = MagicMock()
        return self._hass

    @hass.setter
    def hass(self, value):
        self._hass = value


class _StubOptionsFlow:
    """Stub for homeassistant.config_entries.OptionsFlow."""

    def __init__(self):
        self._hass = MagicMock()
        self._config_entry = None

    @property
    def config_entry(self):
        return self._config_entry

    @config_entry.setter
    def config_entry(self, value):
        self._config_entry = value

    @property
    def hass(self):
        return self._hass

    @hass.setter
    def hass(self, value):
        self._hass = value

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(
        self, *, step_id, data_schema=None, errors=None, description_placeholders=None
    ):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {},
        }


class _StubConfigEntry:
    """Stub for homeassistant.config_entries.ConfigEntry."""

    def __init__(self, *, domain="", data=None, options=None, unique_id=None, entry_id="test"):
        self.domain = domain
        self.data = data or {}
        self.options = options or {}
        self.unique_id = unique_id
        self.entry_id = entry_id
        self.runtime_data = None

    def __class_getitem__(cls, item):
        """Support ConfigEntry[T] syntax for type aliases."""
        return cls


# ---------------------------------------------------------------------------
# Inject stubs into the HA stub modules
# ---------------------------------------------------------------------------
# Force-create the modules via our finder, then override specific attributes
# with real classes.  This must happen BEFORE any test imports config_flow.py.

import homeassistant.config_entries  # noqa: E402
import homeassistant.data_entry_flow  # noqa: E402
import homeassistant.const  # noqa: E402

sys.modules["homeassistant.config_entries"].ConfigFlow = _StubConfigFlow
sys.modules["homeassistant.config_entries"].OptionsFlow = _StubOptionsFlow
sys.modules["homeassistant.config_entries"].ConfigEntry = _StubConfigEntry

sys.modules["homeassistant.data_entry_flow"].AbortFlow = _AbortFlow
sys.modules["homeassistant.data_entry_flow"].FlowResult = dict

sys.modules["homeassistant.const"].CONF_ADDRESS = "address"


# ---------------------------------------------------------------------------
# Coordinator stubs
# ---------------------------------------------------------------------------

class _StubDataUpdateCoordinator:
    """Stub for homeassistant.helpers.update_coordinator.DataUpdateCoordinator."""

    def __init__(self, *args, **kwargs):
        self.hass = kwargs.get("hass")
        self.name = kwargs.get("name", "test")
        self.data = {}
        self._listeners = {}

    async def async_config_entry_first_refresh(self):
        pass

    async def async_refresh(self):
        pass

    async def async_request_refresh(self):
        pass

    def async_add_listener(self, callback):
        pass


class _StubUpdateFailed(Exception):
    """Stub for homeassistant.helpers.update_coordinator.UpdateFailed."""
    pass


# Inject coordinator stubs
import homeassistant.helpers.update_coordinator  # noqa: E402

sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = _StubDataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = _StubUpdateFailed


# ---------------------------------------------------------------------------
# Entity stubs
# ---------------------------------------------------------------------------

class _StubEntity:
    """Stub for homeassistant.helpers.entity.Entity."""
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_device_info = None
    _attr_available = True

    @property
    def available(self):
        return getattr(self, "_attr_available", True)

    @property
    def unique_id(self):
        return getattr(self, "_attr_unique_id", None)


class _StubCoordinatorEntity(_StubEntity):
    """Stub for homeassistant.helpers.update_coordinator.CoordinatorEntity."""

    def __init__(self, coordinator, context=None):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        """Support CoordinatorEntity[T] syntax."""
        return cls

    @property
    def available(self):
        # Default: available if connected
        if hasattr(self, "coordinator") and self.coordinator:
            return self.coordinator.data.get("connected", True)
        return True


class _StubSensorEntity(_StubEntity):
    """Stub for homeassistant.components.sensor.SensorEntity."""
    _attr_native_value = None
    _attr_native_unit_of_measurement = None
    _attr_device_class = None
    _attr_state_class = None

    @property
    def native_value(self):
        return getattr(self, "_attr_native_value", None)

    @property
    def device_class(self):
        return getattr(self, "_attr_device_class", None)


class _StubBinarySensorEntity(_StubEntity):
    """Stub for homeassistant.components.binary_sensor.BinarySensorEntity."""
    _attr_is_on = None

    @property
    def is_on(self):
        return getattr(self, "_attr_is_on", None)


class _StubClimateEntity(_StubEntity):
    """Stub for homeassistant.components.climate.ClimateEntity."""
    _attr_hvac_mode = None
    _attr_hvac_modes = []
    _attr_current_temperature = None
    _attr_target_temperature = None


class _StubFanEntity(_StubEntity):
    """Stub for homeassistant.components.fan.FanEntity."""
    _attr_is_on = None
    _attr_percentage = None


class _StubSwitchEntity(_StubEntity):
    """Stub for homeassistant.components.switch.SwitchEntity."""
    _attr_is_on = None

    @property
    def is_on(self):
        return getattr(self, "_attr_is_on", None)


class _StubSelectEntity(_StubEntity):
    """Stub for homeassistant.components.select.SelectEntity."""
    _attr_current_option = None
    _attr_options = []


class _StubNumberEntity(_StubEntity):
    """Stub for homeassistant.components.number.NumberEntity."""
    _attr_native_value = None
    _attr_native_min_value = 0
    _attr_native_max_value = 100


class _StubButtonEntity(_StubEntity):
    """Stub for homeassistant.components.button.ButtonEntity."""
    pass


# Inject entity stubs - import modules first to create them via our finder
import homeassistant.helpers.entity  # noqa: E402
import homeassistant.components.sensor  # noqa: E402
import homeassistant.components.binary_sensor  # noqa: E402
import homeassistant.components.climate  # noqa: E402
import homeassistant.components.fan  # noqa: E402
import homeassistant.components.switch  # noqa: E402
import homeassistant.components.select  # noqa: E402
import homeassistant.components.number  # noqa: E402
import homeassistant.components.button  # noqa: E402

sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = _StubCoordinatorEntity
sys.modules["homeassistant.helpers.entity"].Entity = _StubEntity

sys.modules["homeassistant.components.sensor"].SensorEntity = _StubSensorEntity
sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = _StubBinarySensorEntity
sys.modules["homeassistant.components.climate"].ClimateEntity = _StubClimateEntity
sys.modules["homeassistant.components.fan"].FanEntity = _StubFanEntity
sys.modules["homeassistant.components.switch"].SwitchEntity = _StubSwitchEntity
sys.modules["homeassistant.components.select"].SelectEntity = _StubSelectEntity
sys.modules["homeassistant.components.number"].NumberEntity = _StubNumberEntity
sys.modules["homeassistant.components.button"].ButtonEntity = _StubButtonEntity


# ---------------------------------------------------------------------------
# Core callback decorator stub
# ---------------------------------------------------------------------------
# The @callback decorator in HA is an identity decorator that marks functions
# as callbacks but doesn't change their behavior. We need a real function
# instead of MagicMock to preserve method bodies.

def _stub_callback(func):
    """Stub for homeassistant.core.callback decorator (identity function)."""
    return func

# Ensure homeassistant.core module exists before setting callback
if "homeassistant.core" not in sys.modules:
    _ha_core = types.ModuleType("homeassistant.core")
    _ha_core.__path__ = []
    _ha_core.__loader__ = _HAStubFinder()
    _ha_core.__spec__ = None
    _ha_core.__getattr__ = lambda name: MagicMock()
    sys.modules["homeassistant.core"] = _ha_core
sys.modules["homeassistant.core"].callback = _stub_callback


# ---------------------------------------------------------------------------
# Real HA constants (not MagicMocks)
# ---------------------------------------------------------------------------
# Some constants need to be real values for tests to work properly.

# Ensure homeassistant.const module exists
if "homeassistant.const" not in sys.modules:
    _ha_const = types.ModuleType("homeassistant.const")
    _ha_const.__path__ = []
    _ha_const.__loader__ = _HAStubFinder()
    _ha_const.__spec__ = None
    _ha_const.__getattr__ = lambda name: MagicMock()
    sys.modules["homeassistant.const"] = _ha_const

# Set real string values for constants used as dict keys
sys.modules["homeassistant.const"].ATTR_TEMPERATURE = "temperature"
sys.modules["homeassistant.const"].CONF_ADDRESS = "address"


# ---------------------------------------------------------------------------
# Exception stubs
# ---------------------------------------------------------------------------
# HA exceptions need to be real exception classes, not MagicMocks

class _ConfigEntryNotReady(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryNotReady."""
    pass


class _HomeAssistantError(Exception):
    """Stub for homeassistant.exceptions.HomeAssistantError."""

    def __init__(
        self,
        message: str = "",
        *args,
        translation_domain: str | None = None,
        translation_key: str | None = None,
        translation_placeholders: dict | None = None,
        **kwargs,
    ):
        super().__init__(message, *args)
        self.translation_domain = translation_domain
        self.translation_key = translation_key
        self.translation_placeholders = translation_placeholders or {}


class _ServiceValidationError(_HomeAssistantError):
    """Stub for homeassistant.exceptions.ServiceValidationError."""
    pass


# Ensure homeassistant.exceptions module exists
if "homeassistant.exceptions" not in sys.modules:
    _ha_exceptions = types.ModuleType("homeassistant.exceptions")
    _ha_exceptions.__path__ = []
    _ha_exceptions.__loader__ = _HAStubFinder()
    _ha_exceptions.__spec__ = None
    _ha_exceptions.__getattr__ = lambda name: MagicMock()
    sys.modules["homeassistant.exceptions"] = _ha_exceptions

sys.modules["homeassistant.exceptions"].ConfigEntryNotReady = _ConfigEntryNotReady
sys.modules["homeassistant.exceptions"].HomeAssistantError = _HomeAssistantError
sys.modules["homeassistant.exceptions"].ServiceValidationError = _ServiceValidationError


# ---------------------------------------------------------------------------
# Bleak stubs
# ---------------------------------------------------------------------------
# bleak.exc.BleakError needs to be a real exception class, not a MagicMock

class _BleakError(Exception):
    """Stub for bleak.exc.BleakError."""
    pass


# Ensure bleak.exc module exists
if "bleak.exc" not in sys.modules:
    _bleak_exc = types.ModuleType("bleak.exc")
    _bleak_exc.__path__ = []
    _bleak_exc.__loader__ = _HAStubFinder()
    _bleak_exc.__spec__ = None
    _bleak_exc.__getattr__ = lambda name: MagicMock()
    sys.modules["bleak.exc"] = _bleak_exc

sys.modules["bleak.exc"].BleakError = _BleakError
