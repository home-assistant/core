# Home Assistant Core - Developer Documentation

> **Complete documentation library for Home Assistant Core development**
> 
> 📚 **81+ documentation files** organized into **10 thematic sections**

## 📖 Table of Contents

- [Getting Started](#-getting-started) (7 files)
- [Architecture](#-architecture) (7 files + subsections)
- [Building Integrations](#-building-integrations) (17 files + subsections)
- [Entities](#-entities) (13 files)
- [Registries](#-registries) (5 files)
- [Authentication](#-authentication) (5 files)
- [Core Features & APIs](#-core-features--apis) (5 files + subsections)
- [External APIs](#-external-apis) (2 files)
- [Quality & Best Practices](#-quality--best-practices) (3 files)
- [Advanced Topics](#-advanced-topics) (11 files)

---

## 🚀 Getting Started

**Location**: `01_getting_started/`

Start here if you're new to Home Assistant development.

- [**Introduction**](01_getting_started/introduction.md) - Overview of Home Assistant Core development
- [**Development Environment**](01_getting_started/development_environment.md) - Setup your dev environment (VS Code + devcontainer or manual)
- [**Submitting Work**](01_getting_started/submitting_work.md) - How to submit PRs and contributions
- [**Style Guidelines**](01_getting_started/style_guidelines.md) - Coding standards and conventions
- [**Testing**](01_getting_started/testing.md) - How to test your code
- [**Catching Up**](01_getting_started/catching_up.md) - Staying updated with the codebase
- [**Tips and Tricks**](01_getting_started/tips_and_tricks.md) - Useful development tips

---

## 🏗️ Architecture

**Location**: `02_architecture/`

Understand the core architecture of Home Assistant.

- [**Overview**](02_architecture/overview.md) - High-level architecture overview
- [**Integrations**](02_architecture/integrations.md) - How integrations work
- [**Devices and Services**](02_architecture/devices_and_services.md) - Device and service architecture

### The `hass` Object
**Location**: `02_architecture/hass_object/`

- [Introduction](02_architecture/hass_object/introduction.md) - The central `hass` object
- [Events](02_architecture/hass_object/events.md) - Event bus system
- [States](02_architecture/hass_object/states.md) - State machine
- [Config](02_architecture/hass_object/config.md) - Configuration handling

---

## 🔌 Building Integrations

**Location**: `03_integrations/`

Complete guide to building Home Assistant integrations.

### Core Integration Concepts
- [**Creating Your First Integration**](03_integrations/creating_first_integration.md) - Step-by-step guide
- [**File Structure**](03_integrations/file_structure.md) - How to organize integration files
- [**Tests File Structure**](03_integrations/tests_file_structure.md) - Organizing test files
- [**Manifest**](03_integrations/manifest.md) - Creating manifest.json
- [**Config Flow**](03_integrations/config_flow.md) - User configuration UI
- [**Options Flow**](03_integrations/options_flow.md) - Options and reconfiguration
- [**YAML Configuration**](03_integrations/yaml_configuration.md) - YAML-based config (legacy)

### Integration Features
- [**Custom Actions**](03_integrations/custom_actions.md) - Creating service actions
- [**Platforms**](03_integrations/platforms.md) - Entity platforms
- [**Multiple Platforms**](03_integrations/multiple_platforms.md) - Supporting multiple platforms
- [**Fetching Data**](03_integrations/fetching_data.md) - Data update coordinators
- [**Setup Failures**](03_integrations/setup_failures.md) - Handling setup errors
- [**Firing Events**](03_integrations/firing_events.md) - Event dispatching
- [**Listening to Events**](03_integrations/listening_events.md) - Event subscribers
- [**Networking & Discovery**](03_integrations/networking_discovery.md) - Network and device discovery

### Bluetooth
**Location**: `03_integrations/bluetooth/`

- [Building Integration](03_integrations/bluetooth/building_integration.md)
- [Fetching Data](03_integrations/bluetooth/fetching_data.md)
- [API Reference](03_integrations/bluetooth/api.md)

---

## 🎛️ Entities

**Location**: `04_entities/`

Documentation for all entity types.

- [**Entity Base**](04_entities/entity_base.md) - Base entity class and concepts
- [Sensor](04_entities/sensor.md) - Sensor entities
- [Binary Sensor](04_entities/binary_sensor.md) - Binary (on/off) sensors
- [Switch](04_entities/switch.md) - Switch entities
- [Light](04_entities/light.md) - Light entities
- [Climate](04_entities/climate.md) - Climate/thermostat entities
- [Cover](04_entities/cover.md) - Cover/blind entities
- [Fan](04_entities/fan.md) - Fan entities
- [Lock](04_entities/lock.md) - Lock entities
- [Alarm Control Panel](04_entities/alarm_control_panel.md) - Alarm systems
- [Vacuum](04_entities/vacuum.md) - Vacuum cleaners
- [Camera](04_entities/camera.md) - Camera entities
- [Media Player](04_entities/media_player.md) - Media player entities

---

## 📋 Registries

**Location**: `05_registries/`

Entity, device, area, and config entry registries.

- [**Entity Registry**](05_registries/entity_registry.md) - Entity registry system
- [**Entity Disabled By**](05_registries/entity_registry_disabled_by.md) - Entity disable management
- [**Device Registry**](05_registries/device_registry.md) - Device registry system
- [**Area Registry**](05_registries/area_registry.md) - Area/room management
- [**Config Entries**](05_registries/config_entries.md) - Configuration entries lifecycle

---

## 🔐 Authentication

**Location**: `06_authentication/`

Authentication and authorization system.

- [**Introduction**](06_authentication/introduction.md) - Auth system overview
- [**Permissions**](06_authentication/permissions.md) - Permission system
- [**API**](06_authentication/api.md) - Authentication API
- [**Auth Provider**](06_authentication/auth_provider.md) - Creating auth providers
- [**MFA Module**](06_authentication/auth_module.md) - Multi-factor authentication

---

## ⚙️ Core Features & APIs

**Location**: `07_core_features/`

### Core Systems
- [**Data Entry Flow**](07_core_features/data_entry_flow.md) - User input flows
- [**Automations**](07_core_features/automations.md) - Automation system

### Device Automations
**Location**: `07_core_features/device_automations/`

- [Triggers](07_core_features/device_automations/triggers.md)
- [Conditions](07_core_features/device_automations/conditions.md)
- [Actions](07_core_features/device_automations/actions.md)

### Intents
**Location**: `07_core_features/intents/`

- [Firing](07_core_features/intents/firing.md)
- [Handling](07_core_features/intents/handling.md)
- [Built-in](07_core_features/intents/builtin.md)

### AI & Voice
**Location**: `07_core_features/ai_voice/`

- [Conversation API](07_core_features/ai_voice/conversation_api.md)

---

## 🌐 External APIs

**Location**: `08_apis/`

APIs for external integrations and frontends.

- [**WebSocket API**](08_apis/websocket_api.md) - Real-time WebSocket API
- [**REST API**](08_apis/rest_api.md) - RESTful HTTP API

---

## ✅ Quality & Best Practices

**Location**: `09_quality_and_best_practices/`

Code quality, testing, and review guidelines.

- [**Development Checklist**](09_quality_and_best_practices/development_checklist.md) - General checklist
- [**Component Checklist**](09_quality_and_best_practices/component_checklist.md) - Component review checklist
- [**Platform Checklist**](09_quality_and_best_practices/platform_checklist.md) - Platform review checklist

---

## 🎓 Advanced Topics

**Location**: `10_advanced/`

Advanced development topics and specialized features.

- [**Asyncio Best Practices**](10_advanced/asyncio_best_practices.md) - Async programming patterns
- [**Validation**](10_advanced/validation.md) - Input validation
- [**Type Hints**](10_advanced/typing.md) - Type hinting guidelines
- [**Brands**](10_advanced/brands.md) - Brand integration
- [**Instance URL**](10_advanced/instance_url.md) - Instance URL handling
- [**Application Credentials**](10_advanced/application_credentials.md) - OAuth credentials
- [**Backup**](10_advanced/backup.md) - Backup platform
- [**Repairs**](10_advanced/repairs.md) - Repair platform
- [**Reproduce State**](10_advanced/reproduce_state.md) - State reproduction
- [**Significant Change**](10_advanced/significant_change.md) - Significant change detection

---

## 🔗 Official Resources

### Documentation & Community
- 🌐 [Official Developer Docs](https://developers.home-assistant.io/)
- 💬 [Discord Developer Channel](https://www.home-assistant.io/join-chat/) - `#developers`
- 💻 [Home Assistant Core Repository](https://github.com/home-assistant/core)
- 📖 [Developer Documentation Repository](https://github.com/home-assistant/developers.home-assistant)

### Quick Links
- [Architecture Documentation](https://developers.home-assistant.io/docs/architecture_index)
- [Integration Development](https://developers.home-assistant.io/docs/development_index)
- [Community Forum](https://community.home-assistant.io/)
- [Reddit r/homeassistant](https://reddit.com/r/homeassistant)

---

## 📊 Documentation Statistics

- **Total Files**: 81+ markdown files
- **Categories**: 10 main sections
- **Subsections**: Bluetooth, hass_object, device_automations, intents, ai_voice
- **Last Updated**: January 2026
- **Source**: Home Assistant developers.home-assistant repository

---

## 🎯 Quick Start Path

If you're new to Home Assistant development, follow this path:

1. **Read**: [Getting Started Introduction](01_getting_started/introduction.md)
2. **Setup**: [Development Environment](01_getting_started/development_environment.md)
3. **Understand**: [Architecture Overview](02_architecture/overview.md)
4. **Learn**: [Creating Your First Integration](03_integrations/creating_first_integration.md)
5. **Build**: [Entity Base](04_entities/entity_base.md) → Choose your entity type
6. **Test**: [Testing Guide](01_getting_started/testing.md)
7. **Submit**: [Submitting Work](01_getting_started/submitting_work.md)

---

## 📝 Archive

Previous flat-structure files are preserved in the `archive/` folder for reference.
