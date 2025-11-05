# WebAssembly Sandboxing for Home Assistant Integrations
## Comprehensive Feasibility and Implementation Analysis

**Document Version:** 1.0
**Date:** November 5, 2025
**Status:** Proposal / Analysis Phase

---

## Executive Summary

This document analyzes the feasibility of using WebAssembly (WASM) to provide security sandboxing for Home Assistant integrations. The goal is to isolate third-party integrations in sandboxed environments while maintaining compatibility with existing Python-based integrations.

### Key Findings

✅ **Technically Feasible** - WASM/WASI provides capability-based security suitable for sandboxing
⚠️ **Significant Effort Required** - Estimated 6-12 months for foundation with 2-3 senior engineers
✅ **CPython WASI Support** - Official tier-2 support in CPython 3.11+
⚠️ **Performance Trade-offs** - 20-50% overhead expected for WASM execution
✅ **Gradual Migration** - Can coexist with current Python integrations

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [WASM/WASI Capabilities](#wasmwasi-capabilities)
3. [Proposed Architecture](#proposed-architecture)
4. [Security Model](#security-model)
5. [Versioned API Design](#versioned-api-design)
6. [Implementation Phases](#implementation-phases)
7. [Effort Estimation](#effort-estimation)
8. [Migration Strategy](#migration-strategy)
9. [Boilerplate Code Examples](#boilerplate-code-examples)
10. [Challenges and Mitigations](#challenges-and-mitigations)
11. [Recommendations](#recommendations)

---

## 1. Current Architecture Analysis

### Integration Loading Mechanism

Home Assistant currently loads integrations using Python's native import system:

```python
# From homeassistant/loader.py
def _get_component(self) -> ComponentProtocol:
    """Import integration directly in Python."""
    cache[domain] = importlib.import_module(self.pkg_path)
    return cache[domain]
```

### Key Integration Touchpoints

**Core APIs integrations interact with:**

1. **HomeAssistant Core** (`hass` object)
   - Event bus (`hass.bus`)
   - Service registry (`hass.services`)
   - State machine (`hass.states`)
   - Data storage (`hass.data`)
   - Configuration (`hass.config`)

2. **Entity Management**
   - Entity platform setup
   - Entity registry
   - Device registry
   - State updates

3. **Config Entries**
   - Setup/unload lifecycle
   - Options flow
   - Reauth flow

4. **External Resources**
   - Network I/O (HTTP clients, sockets)
   - File system access
   - External libraries (pip packages)
   - Async executor jobs

### Current Security Model

**Current state: Trust-based**
- All integrations run in the same Python process
- Full access to Home Assistant internals
- No resource limits
- No capability restrictions
- Custom integrations can break core functionality

---

## 2. WASM/WASI Capabilities

### What is WASM/WASI?

**WebAssembly (WASM):** Portable binary instruction format with security sandboxing
**WASI (WebAssembly System Interface):** System interface for WASM outside browsers

### Security Features

#### Capability-Based Security
```
WASI code only has access to explicitly granted capabilities:
- File descriptors (specific directories only)
- Network sockets (if granted)
- Environment variables (explicit allow-list)
- Process spawning (disabled by default)
```

#### Resource Metering
- CPU cycle counting
- Memory allocation tracking
- Stack depth limits
- Deterministic execution

#### Process Isolation
- Separate memory space
- No shared global state
- Controlled inter-process communication

### Python WASM Status (2025)

**CPython WASI Support:**
- ✅ Tier-2 support in CPython 3.11+
- ✅ Official WASI SDK available
- ✅ Standard library largely functional
- ⚠️ Some C extensions require porting
- ⚠️ Asyncio support limited but improving

**Available Runtimes:**
- **Wasmtime** (Bytecode Alliance) - Production-ready, security-focused
- **Wasmer** - Fast, multiple language support
- **wazero** (Go) - Embedded WASM runtime

---

## 3. Proposed Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Home Assistant Core                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Integration Loader & Router                   │   │
│  │  - Detects integration type (native/WASM)            │   │
│  │  - Routes to appropriate runtime                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────┐      ┌──────────────────────────┐  │
│  │  Native Python      │      │  WASM Runtime Manager     │  │
│  │  Integrations       │      │  ┌──────────────────────┐ │  │
│  │  (Current)          │      │  │ Versioned API Bridge │ │  │
│  │                     │      │  │ - v1: Basic entities │ │  │
│  │  - Full access      │      │  │ - v2: Advanced       │ │  │
│  │  - Trusted code     │      │  │ - v3: Future...      │ │  │
│  └─────────────────────┘      │  └──────────────────────┘ │  │
│                                │  ┌──────────────────────┐ │  │
│                                │  │  Wasmtime Instance   │ │  │
│                                │  │  ┌────────────────┐  │ │  │
│                                │  │  │ Integration A  │  │ │  │
│                                │  │  │ (Sandboxed)    │  │ │  │
│                                │  │  └────────────────┘  │ │  │
│                                │  │  ┌────────────────┐  │ │  │
│                                │  │  │ Integration B  │  │ │  │
│                                │  │  │ (Sandboxed)    │  │ │  │
│                                │  │  └────────────────┘  │ │  │
│                                │  └──────────────────────┘ │  │
│                                └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. Integration Loader Extensions

**Location:** `homeassistant/loader.py`

Add detection for WASM-based integrations:

```python
class Integration:
    @cached_property
    def execution_mode(self) -> Literal["native", "wasm"]:
        """Determine execution mode from manifest."""
        return self.manifest.get("execution_mode", "native")

    @cached_property
    def wasm_module_path(self) -> str | None:
        """Path to compiled WASM module."""
        if self.execution_mode == "wasm":
            return self.manifest.get("wasm_module")
        return None
```

#### 2. WASM Runtime Manager

**New module:** `homeassistant/wasm_runtime.py`

```python
"""WASM runtime manager for sandboxed integrations."""

from wasmtime import Engine, Store, Module, Linker
import asyncio
from typing import Any

class WasmRuntimeManager:
    """Manage WASM integration execution."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.engine = Engine()
        self.instances: dict[str, WasmIntegrationInstance] = {}

    async def load_integration(
        self,
        domain: str,
        wasm_path: Path,
        api_version: int
    ) -> WasmIntegrationInstance:
        """Load and instantiate a WASM integration."""
        module = Module.from_file(self.engine, str(wasm_path))

        # Create capability-restricted store
        store = Store(self.engine)
        store.set_fuel(1_000_000_000)  # CPU limit
        store.set_memory_limit(100 * 1024 * 1024)  # 100MB memory

        # Link versioned API
        linker = self._create_api_linker(api_version)

        instance = WasmIntegrationInstance(
            domain=domain,
            store=store,
            instance=linker.instantiate(store, module),
            api_version=api_version
        )

        self.instances[domain] = instance
        return instance
```

#### 3. Versioned API Bridge

**New module:** `homeassistant/wasm_api/`

```
homeassistant/wasm_api/
├── __init__.py
├── base.py              # Base API interface
├── v1/
│   ├── __init__.py
│   ├── entities.py      # Entity API v1
│   ├── services.py      # Service API v1
│   └── state.py         # State API v1
├── v2/
│   ├── __init__.py
│   └── ...              # Enhanced APIs
└── bridge.py            # API bridge implementation
```

---

## 4. Security Model

### Capability Model

**Granted Capabilities (Configurable per integration):**

```yaml
# manifest.json
{
  "domain": "example",
  "execution_mode": "wasm",
  "wasm_module": "integration.wasm",
  "api_version": 1,
  "capabilities": {
    "network": {
      "allowed_hosts": ["api.example.com"],
      "allowed_ports": [443],
      "protocols": ["https"]
    },
    "filesystem": {
      "read": ["/config/example"],
      "write": ["/config/example/cache"]
    },
    "resources": {
      "max_memory_mb": 100,
      "max_cpu_time_ms": 5000,
      "max_concurrent_requests": 10
    },
    "home_assistant": {
      "can_fire_events": true,
      "can_call_services": true,
      "can_register_services": true,
      "can_access_states": true,
      "entity_domains": ["sensor", "binary_sensor"]
    }
  }
}
```

### Isolation Boundaries

```
┌─────────────────────────────────────────┐
│  WASM Integration (Untrusted)           │
│                                          │
│  ✅ Can: Access versioned API            │
│  ✅ Can: Read/write own data             │
│  ✅ Can: Make HTTP to allowed hosts      │
│  ✅ Can: Create entities (approved types)│
│  ❌ Cannot: Access other integrations    │
│  ❌ Cannot: Modify HA internals          │
│  ❌ Cannot: Execute arbitrary code       │
│  ❌ Cannot: Access full filesystem       │
│                                          │
└─────────────────────────────────────────┘
            ↕ (API Bridge)
┌─────────────────────────────────────────┐
│  Home Assistant Core (Trusted)          │
└─────────────────────────────────────────┘
```

### Resource Limits

**Per-Integration Limits:**
- Memory: 50-200MB (configurable)
- CPU time: Metered via fuel API
- Network connections: Rate-limited
- Disk I/O: Quota-based
- Event firing: Rate-limited

---

## 5. Versioned API Design

### API Versioning Strategy

**Semantic Versioning for APIs:**
- **v1.x**: Core functionality (entities, basic services)
- **v2.x**: Advanced features (coordinators, complex flows)
- **v3.x**: Future extensions

**Version Compatibility:**
```python
# Integration declares supported API versions
{
  "api_version": 1,
  "api_version_min": 1,
  "api_version_max": 2
}
```

### API v1 Interface (Foundation)

```python
# homeassistant/wasm_api/v1/interface.py

"""WASM Integration API v1."""

class WasmApiV1:
    """API v1 for WASM integrations."""

    # Entity Management
    async def register_entity(
        self,
        entity_id: str,
        platform: str,
        device_class: str | None,
        config: dict[str, Any]
    ) -> EntityHandle

    async def update_entity_state(
        self,
        handle: EntityHandle,
        state: str,
        attributes: dict[str, Any]
    ) -> None

    async def set_entity_available(
        self,
        handle: EntityHandle,
        available: bool
    ) -> None

    # State Access
    async def get_state(self, entity_id: str) -> State | None

    async def get_states(self, domain: str | None = None) -> list[State]

    # Service Calls
    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any]
    ) -> None

    async def register_service(
        self,
        service: str,
        schema: dict[str, Any],
        handler_id: int  # Maps to WASM function
    ) -> None

    # Events
    async def fire_event(
        self,
        event_type: str,
        data: dict[str, Any]
    ) -> None

    async def listen_event(
        self,
        event_type: str,
        handler_id: int
    ) -> ListenerHandle

    # Configuration
    def get_config_entry_data(self) -> dict[str, Any]

    def get_config_entry_options(self) -> dict[str, Any]

    async def update_config_entry(
        self,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None
    ) -> None

    # HTTP Client (Restricted)
    async def http_get(
        self,
        url: str,
        headers: dict[str, str] | None = None
    ) -> HttpResponse

    async def http_post(
        self,
        url: str,
        data: bytes | dict[str, Any],
        headers: dict[str, str] | None = None
    ) -> HttpResponse

    # Logging
    def log_debug(self, message: str) -> None
    def log_info(self, message: str) -> None
    def log_warning(self, message: str) -> None
    def log_error(self, message: str) -> None
```

### API Serialization Format

**Use JSON for all API calls:**
```
WASM Integration → JSON-RPC over WASM memory → Core
Core → JSON response in WASM memory → WASM Integration
```

**Example Call:**
```json
{
  "jsonrpc": "2.0",
  "method": "register_entity",
  "params": {
    "entity_id": "sensor.example_temperature",
    "platform": "sensor",
    "device_class": "temperature",
    "config": {
      "name": "Example Temperature",
      "unit_of_measurement": "°C"
    }
  },
  "id": 1
}
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Months 1-3)

**Goals:**
- WASM runtime infrastructure
- Basic API v1 implementation
- One proof-of-concept integration

**Deliverables:**
1. `homeassistant/wasm_runtime.py` - Runtime manager
2. `homeassistant/wasm_api/v1/` - API v1 interface
3. Integration loader WASM support
4. Wasmtime dependency integration
5. Simple WASM example integration (e.g., sensor)

**Key Files to Modify:**
- `homeassistant/loader.py` - Add WASM detection
- `homeassistant/setup.py` - Add WASM setup path
- `homeassistant/core.py` - Add WASM runtime to hass object
- `manifest.json` schema - Add WASM fields

### Phase 2: API Expansion (Months 4-6)

**Goals:**
- Complete API v1 coverage
- Entity platform support
- Config flow integration
- Developer documentation

**Deliverables:**
1. Full entity platforms (sensor, binary_sensor, switch, etc.)
2. Config flow support for WASM
3. Developer tools for WASM integrations
4. Python→WASM compiler toolchain
5. Testing framework

### Phase 3: Advanced Features (Months 7-9)

**Goals:**
- API v2 with advanced features
- Performance optimization
- Migration tools

**Deliverables:**
1. Coordinator pattern support
2. Device management APIs
3. Diagnostics APIs
4. Migration toolkit (Python → WASM)
5. Performance benchmarks

### Phase 4: Production Readiness (Months 10-12)

**Goals:**
- Security audits
- Production hardening
- Community adoption

**Deliverables:**
1. Security audit report
2. Production deployment docs
3. CI/CD integration testing
4. 5-10 migrated popular integrations
5. Quality scale requirements

---

## 7. Effort Estimation

### Team Requirements

**Core Team:**
- 2-3 Senior Python/Systems Engineers (full-time)
- 1 Security Engineer (50% time)
- 1 Developer Advocate (25% time)

**Community:**
- Beta testers
- Integration developers
- Security reviewers

### Time Breakdown

| Phase | Duration | Engineer-Months | Key Risks |
|-------|----------|-----------------|-----------|
| Phase 1: Foundation | 3 months | 6-9 | WASM runtime integration complexity |
| Phase 2: API Expansion | 3 months | 6-9 | API completeness, edge cases |
| Phase 3: Advanced Features | 3 months | 6-9 | Performance optimization |
| Phase 4: Production | 3 months | 3-6 | Community adoption, migration |
| **Total** | **12 months** | **21-33** | Scope creep, compatibility issues |

### Cost Estimate (Rough)

**Engineering:**
- 2.5 engineers × 12 months × $15k/month = $450k

**Infrastructure:**
- WASM runtime licenses: $0 (open source)
- Testing infrastructure: $5-10k
- Security audit: $20-30k

**Total: ~$480-500k**

---

## 8. Migration Strategy

### Coexistence Model

```python
# Both types of integrations can coexist
INTEGRATION_TYPES = {
    "native": ["hue", "zwave_js", "esphome"],  # Trusted
    "wasm": ["custom_sensor", "new_integration"]  # Sandboxed
}
```

### Migration Path

**Option 1: Dual-Mode Integrations**
```json
{
  "domain": "example",
  "execution_mode": "hybrid",
  "native_module": "__init__.py",
  "wasm_module": "integration.wasm",
  "prefer_wasm": true
}
```

**Option 2: Gradual Migration**
1. Start with new custom integrations → WASM only
2. Migrate popular custom integrations
3. Eventually require WASM for all custom integrations
4. Core integrations can remain native (trusted)

### Developer Experience

**Build Process:**
```bash
# Developer writes Python as usual
# homeassistant/components/my_integration/__init__.py

# Build to WASM
$ ha-wasm build my_integration
→ Compiles Python to WASM using CPython WASI
→ Generates manifest with WASM fields
→ Validates API compatibility
→ Creates my_integration.wasm

# Test locally
$ ha-wasm test my_integration
```

---

## 9. Boilerplate Code Examples

### 9.1 WASM Integration Manifest

```json
{
  "domain": "example_wasm",
  "name": "Example WASM Integration",
  "codeowners": ["@example"],
  "config_flow": true,
  "documentation": "https://www.example.com/integration",
  "integration_type": "device",
  "iot_class": "cloud_polling",
  "requirements": [],

  "execution_mode": "wasm",
  "wasm_module": "example_wasm.wasm",
  "api_version": 1,
  "api_version_min": 1,
  "api_version_max": 1,

  "capabilities": {
    "network": {
      "allowed_hosts": ["api.example.com"],
      "protocols": ["https"]
    },
    "resources": {
      "max_memory_mb": 50,
      "max_cpu_time_ms": 2000
    },
    "home_assistant": {
      "entity_domains": ["sensor"],
      "can_fire_events": true,
      "can_call_services": false
    }
  }
}
```

### 9.2 WASM Integration Python Code

```python
"""Example WASM integration - Python source."""

from __future__ import annotations
from typing import Any

# WASM API imports (provided by runtime)
from homeassistant.wasm_api import (
    WasmIntegration,
    ConfigEntry,
    EntityHandle,
    async_api_call,
)

class ExampleWasmIntegration(WasmIntegration):
    """Example integration running in WASM sandbox."""

    def __init__(self):
        """Initialize the integration."""
        super().__init__()
        self.entities: dict[str, EntityHandle] = {}

    async def async_setup_entry(self, entry: ConfigEntry) -> bool:
        """Set up from a config entry."""
        # Get config data
        config_data = await self.api.get_config_entry_data()
        host = config_data["host"]
        api_key = config_data["api_key"]

        # Make HTTP request (capability-checked)
        response = await self.api.http_get(
            f"https://api.example.com/devices",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        if response.status != 200:
            self.api.log_error(f"Failed to connect: {response.status}")
            return False

        devices = response.json()

        # Register entities
        for device in devices:
            entity_id = f"sensor.example_{device['id']}"
            handle = await self.api.register_entity(
                entity_id=entity_id,
                platform="sensor",
                device_class="temperature",
                config={
                    "name": device["name"],
                    "unit_of_measurement": "°C",
                    "device_info": {
                        "identifiers": {("example_wasm", device["id"])},
                        "name": device["name"],
                        "manufacturer": "Example Corp",
                    }
                }
            )
            self.entities[device["id"]] = handle

        # Start update loop
        await self.async_update()
        return True

    async def async_update(self) -> None:
        """Update entity states."""
        config_data = await self.api.get_config_entry_data()

        response = await self.api.http_get(
            "https://api.example.com/states",
            headers={"Authorization": f"Bearer {config_data['api_key']}"}
        )

        if response.status == 200:
            states = response.json()
            for device_id, handle in self.entities.items():
                if device_id in states:
                    await self.api.update_entity_state(
                        handle=handle,
                        state=str(states[device_id]["temperature"]),
                        attributes={
                            "last_updated": states[device_id]["timestamp"]
                        }
                    )

        # Schedule next update (API handles the actual scheduling)
        await self.api.schedule_update(delay_seconds=60)

    async def async_unload_entry(self, entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        # Cleanup handled automatically by runtime
        return True


# Entry point (called by WASM runtime)
async def async_setup_entry(config_entry_json: str) -> bool:
    """Setup entry point called by WASM runtime."""
    integration = ExampleWasmIntegration()
    entry = ConfigEntry.from_json(config_entry_json)
    return await integration.async_setup_entry(entry)
```

### 9.3 Core WASM Runtime Implementation

```python
"""homeassistant/wasm_runtime.py - WASM Runtime Manager."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from wasmtime import Config, Engine, Store, Module, Linker, WasiConfig
import wasmtime

from .core import HomeAssistant, callback
from .exceptions import HomeAssistantError
from .wasm_api import create_api_bridge

_LOGGER = logging.getLogger(__name__)


class WasmIntegrationInstance:
    """Represents a running WASM integration instance."""

    def __init__(
        self,
        domain: str,
        store: Store,
        instance: wasmtime.Instance,
        api_version: int,
        capabilities: dict[str, Any]
    ):
        """Initialize WASM instance."""
        self.domain = domain
        self.store = store
        self.instance = instance
        self.api_version = api_version
        self.capabilities = capabilities
        self.memory = instance.exports(store)["memory"]

    async def call_function(
        self,
        func_name: str,
        *args: Any
    ) -> Any:
        """Call a WASM function."""
        try:
            func = self.instance.exports(self.store).get(func_name)
            if func is None:
                raise HomeAssistantError(
                    f"Function {func_name} not found in WASM module"
                )

            result = func(self.store, *args)
            return result
        except wasmtime.Trap as err:
            _LOGGER.error(
                "WASM trap in %s.%s: %s",
                self.domain,
                func_name,
                err
            )
            raise HomeAssistantError(f"WASM execution error: {err}")


class WasmRuntimeManager:
    """Manage WASM integration instances."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the WASM runtime manager."""
        self.hass = hass

        # Configure Wasmtime engine
        config = Config()
        config.cache = True
        config.consume_fuel = True  # Enable CPU metering
        config.strategy = "cranelift"  # JIT compilation

        self.engine = Engine(config)
        self.instances: dict[str, WasmIntegrationInstance] = {}

    async def load_integration(
        self,
        domain: str,
        wasm_path: Path,
        manifest: dict[str, Any]
    ) -> WasmIntegrationInstance:
        """Load and instantiate a WASM integration."""
        _LOGGER.info("Loading WASM integration: %s", domain)

        # Load and compile WASM module
        module = Module.from_file(self.engine, str(wasm_path))

        # Create isolated store with resource limits
        store = Store(self.engine)
        capabilities = manifest.get("capabilities", {})
        resources = capabilities.get("resources", {})

        # Set fuel (CPU cycles) limit
        max_cpu_time_ms = resources.get("max_cpu_time_ms", 5000)
        fuel_amount = max_cpu_time_ms * 1_000_000  # Rough estimate
        store.add_fuel(fuel_amount)

        # Configure WASI with restricted capabilities
        wasi = WasiConfig()
        wasi.inherit_env()

        # Grant filesystem access if specified
        if fs_caps := capabilities.get("filesystem"):
            for read_path in fs_caps.get("read", []):
                wasi.preopen_dir(
                    read_path,
                    "/",
                    readonly=True
                )
            for write_path in fs_caps.get("write", []):
                wasi.preopen_dir(
                    write_path,
                    "/",
                    readonly=False
                )

        store.set_wasi(wasi)

        # Create API bridge with versioned interface
        api_version = manifest.get("api_version", 1)
        api_bridge = create_api_bridge(
            self.hass,
            domain,
            api_version,
            capabilities
        )

        # Create linker and link API functions
        linker = Linker(self.engine)
        linker.define_wasi()

        # Link Home Assistant API functions
        self._link_api_functions(linker, api_bridge)

        # Instantiate the WASM module
        try:
            instance = linker.instantiate(store, module)
        except wasmtime.Trap as err:
            raise HomeAssistantError(
                f"Failed to instantiate WASM module for {domain}: {err}"
            )

        wasm_instance = WasmIntegrationInstance(
            domain=domain,
            store=store,
            instance=instance,
            api_version=api_version,
            capabilities=capabilities
        )

        self.instances[domain] = wasm_instance
        _LOGGER.info("WASM integration %s loaded successfully", domain)

        return wasm_instance

    def _link_api_functions(
        self,
        linker: Linker,
        api_bridge: Any
    ) -> None:
        """Link Home Assistant API functions to WASM module."""
        # These functions are callable from WASM

        def ha_register_entity(
            caller: wasmtime.Caller,
            data_ptr: int,
            data_len: int
        ) -> int:
            """Register an entity from WASM."""
            # Read JSON from WASM memory
            memory = caller["memory"]
            data_bytes = memory.read(caller, data_ptr, data_len)
            data = json.loads(data_bytes.decode("utf-8"))

            # Call API bridge
            handle = asyncio.run_coroutine_threadsafe(
                api_bridge.register_entity(**data),
                self.hass.loop
            ).result()

            return handle

        # Link functions to "homeassistant" namespace
        linker.define_func(
            "homeassistant",
            "register_entity",
            ha_register_entity
        )

        # Add more API functions...
        # (Similar pattern for all API v1 functions)

    async def setup_integration(
        self,
        domain: str,
        config_entry_data: dict[str, Any]
    ) -> bool:
        """Call async_setup_entry in WASM integration."""
        if domain not in self.instances:
            raise HomeAssistantError(f"WASM integration {domain} not loaded")

        instance = self.instances[domain]

        # Serialize config entry to JSON
        config_json = json.dumps(config_entry_data)

        # Write to WASM memory and call setup
        # (Simplified - actual implementation more complex)
        result = await instance.call_function(
            "async_setup_entry",
            config_json
        )

        return bool(result)

    async def unload_integration(self, domain: str) -> bool:
        """Unload a WASM integration."""
        if domain not in self.instances:
            return True

        instance = self.instances[domain]

        # Call unload if it exists
        try:
            await instance.call_function("async_unload_entry", "{}")
        except HomeAssistantError:
            pass  # Unload function optional

        # Cleanup
        del self.instances[domain]
        _LOGGER.info("WASM integration %s unloaded", domain)

        return True


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the WASM runtime."""
    hass.data["wasm_runtime"] = WasmRuntimeManager(hass)


def get_wasm_runtime(hass: HomeAssistant) -> WasmRuntimeManager:
    """Get the WASM runtime manager."""
    return hass.data["wasm_runtime"]
```

### 9.4 API Bridge Implementation

```python
"""homeassistant/wasm_api/bridge.py - API Bridge."""

from __future__ import annotations

from typing import Any
import logging

from ..core import HomeAssistant
from ..helpers.entity import Entity
from ..helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


class WasmApiBridge:
    """Bridge between WASM integration and Home Assistant core."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        api_version: int,
        capabilities: dict[str, Any]
    ):
        """Initialize the API bridge."""
        self.hass = hass
        self.domain = domain
        self.api_version = api_version
        self.capabilities = capabilities
        self.entities: dict[int, Entity] = {}
        self._next_handle = 1

    async def register_entity(
        self,
        entity_id: str,
        platform: str,
        device_class: str | None,
        config: dict[str, Any]
    ) -> int:
        """Register an entity from WASM integration."""
        # Validate capability
        if not self._check_capability("home_assistant", "entity_domains"):
            raise PermissionError(
                f"Integration {self.domain} not allowed to create "
                f"{platform} entities"
            )

        allowed_domains = (
            self.capabilities
            .get("home_assistant", {})
            .get("entity_domains", [])
        )
        if platform not in allowed_domains:
            raise PermissionError(
                f"Integration {self.domain} not allowed to create "
                f"{platform} entities"
            )

        # Create entity
        entity = WasmEntity(
            entity_id=entity_id,
            platform=platform,
            device_class=device_class,
            **config
        )

        handle = self._next_handle
        self._next_handle += 1
        self.entities[handle] = entity

        _LOGGER.debug(
            "WASM integration %s registered entity %s (handle: %d)",
            self.domain,
            entity_id,
            handle
        )

        return handle

    async def update_entity_state(
        self,
        handle: int,
        state: str,
        attributes: dict[str, Any]
    ) -> None:
        """Update entity state."""
        if handle not in self.entities:
            raise ValueError(f"Invalid entity handle: {handle}")

        entity = self.entities[handle]
        entity.update_state(state, attributes)

    def _check_capability(self, category: str, capability: str) -> bool:
        """Check if integration has a specific capability."""
        return capability in self.capabilities.get(category, {})


class WasmEntity(Entity):
    """Entity managed by WASM integration."""

    def __init__(
        self,
        entity_id: str,
        platform: str,
        device_class: str | None,
        name: str,
        **kwargs
    ):
        """Initialize the entity."""
        self._attr_unique_id = entity_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_value = None
        self._attributes = {}

    def update_state(
        self,
        state: str,
        attributes: dict[str, Any]
    ) -> None:
        """Update state from WASM."""
        self._attr_native_value = state
        self._attributes.update(attributes)
        self.async_write_ha_state()


def create_api_bridge(
    hass: HomeAssistant,
    domain: str,
    api_version: int,
    capabilities: dict[str, Any]
) -> WasmApiBridge:
    """Create API bridge for specific version."""
    return WasmApiBridge(hass, domain, api_version, capabilities)
```

---

## 10. Challenges and Mitigations

### Challenge 1: Async/Await in WASM

**Problem:** Python's asyncio doesn't directly map to WASM
**Mitigation:**
- Use synchronous API in WASM, handle async in bridge
- Implement callback-based API for async operations
- Use WASI async proposals when mature

### Challenge 2: Performance Overhead

**Problem:** 20-50% performance penalty expected
**Mitigation:**
- JIT compilation via Wasmtime
- Ahead-of-time compilation for production
- Profile and optimize hot paths
- Use native integrations for performance-critical code

### Challenge 3: Python Package Ecosystem

**Problem:** Many Python packages use C extensions
**Mitigation:**
- Maintain allow-list of WASM-compatible packages
- Provide WASM-compiled common dependencies
- Encourage pure-Python implementations
- Build integration-specific WASM modules

### Challenge 4: Debugging Experience

**Problem:** Debugging WASM is harder than Python
**Mitigation:**
- Enhanced logging from WASM
- Detailed error messages
- WASM debugger integration (dwarf debugging symbols)
- Development mode with verbose tracing

### Challenge 5: Binary Size

**Problem:** WASM modules can be large (CPython + code)
**Mitigation:**
- Strip unnecessary CPython features
- Compress WASM modules
- Lazy loading of integrations
- Shared CPython runtime module

### Challenge 6: Community Adoption

**Problem:** Developers need to learn new workflow
**Mitigation:**
- Excellent documentation
- Smooth tooling (ha-wasm CLI)
- Write Python, compile to WASM automatically
- Provide many examples
- Migration assistance

---

## 11. Recommendations

### Immediate Actions (Next 3 Months)

1. **Prototype Development**
   - Build minimal WASM runtime proof-of-concept
   - Single sensor integration example
   - Measure performance overhead
   - Validate security model

2. **Architecture Review**
   - Present to core team
   - Gather feedback from security experts
   - Refine API design
   - Create RFC (Request for Comments)

3. **Community Engagement**
   - Blog post on architecture
   - Developer survey
   - Gauge interest and concerns

### Go/No-Go Decision Criteria

**Proceed if:**
- ✅ Performance overhead < 50%
- ✅ Security model validated by experts
- ✅ Positive community feedback
- ✅ CPython WASI support remains stable
- ✅ Core team buy-in

**Reconsider if:**
- ❌ Performance overhead > 100%
- ❌ Critical security gaps found
- ❌ CPython WASI support deteriorates
- ❌ Implementation complexity too high

### Long-Term Vision

**Year 1-2:**
- WASM support optional
- Focus on new custom integrations
- Build ecosystem and tooling

**Year 3+:**
- WASM recommended for custom integrations
- Quality scale includes WASM option
- Large library of WASM integrations

**Year 5+:**
- Possible requirement for all custom integrations
- Native integrations remain for trusted/core code
- Mature, stable WASM ecosystem

---

## Conclusion

WebAssembly sandboxing for Home Assistant integrations is **technically feasible** with current technology. The security benefits are significant:

- ✅ Capability-based security model
- ✅ Resource limits and metering
- ✅ Process isolation
- ✅ Reduced attack surface

However, this is a **major undertaking** requiring:

- 12+ months of development
- 2-3 senior engineers
- $500k+ investment
- Community buy-in and migration effort

**Recommendation:**
Proceed with **Phase 0 (Prototype)** to validate assumptions, then make go/no-go decision based on results.

The foundation work will enable Home Assistant to:
1. Safely run untrusted custom integrations
2. Provide resource limits and isolation
3. Create a stable, versioned API for integrations
4. Improve overall system security and reliability

This positions Home Assistant as a leader in smart home security while maintaining its vibrant custom integration ecosystem.

---

## Appendix: Alternative Approaches Considered

### Alternative 1: Python Sandboxing (RestrictedPython)

**Pros:** Stays in Python, easier migration
**Cons:** Not true isolation, can be bypassed, no resource limits
**Decision:** Rejected - insufficient security

### Alternative 2: Process Isolation (multiprocessing)

**Pros:** True process isolation, use existing Python
**Cons:** High overhead, complex IPC, no resource metering
**Decision:** Partial - could complement WASM

### Alternative 3: Docker/Containers per Integration

**Pros:** Strong isolation, mature tooling
**Cons:** Very high overhead, complex deployment, resource intensive
**Decision:** Rejected - too heavy for typical HA deployments

### Alternative 4: Status Quo with Review Process

**Pros:** No development needed
**Cons:** Doesn't scale, trust-based, reactive not proactive
**Decision:** Insufficient for long-term security

---

**Document End**
