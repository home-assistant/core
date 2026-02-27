# Dashboard Creation Guide

This guide provides best practices for building effective Home Assistant dashboards.

## Basic Structure of a Dashboard

A dashboard is a collection of views, and each view contains sections with cards. The basic structure looks like this:

```yaml
views:
- title: Living Room
  path: living-room
  icon: mdi:sofa
  badges:
    - type: entity
      entity: sensor.living_room_temperature
    - type: entity
      entity: sensor.living_room_humidity
  sections:
    - type: grid
      title: Lights
      cards:
        - type: tile
          entity: light.living_room_ceiling
          features:
            - type: light-brightness
        - type: tile
          entity: light.floor_lamp
        - type: tile
          entity: light.reading_lamp
    - type: grid
      title: Climate
      cards:
        - type: thermostat
          entity: climate.living_room
        - type: tile
          entity: sensor.living_room_temperature
        - type: tile
          entity: sensor.living_room_humidity
```

## Registry Listing Strategy

Use the list tools first to discover available data before building cards:

- `area_list`: list areas and filter with `area-id` and `floor`
- `device_list`: list devices and filter with `device-id`, `area`, and `floor`
- `entity_list`: list entities and filter with `entity-id`, `domain`, `area`, `floor`, `label`, `device`, and `device-class`

When needed, use `count`, `brief`, and `limit` flags to narrow output and then run a second call with the exact IDs you want to include in the dashboard.

## Task-Focused Dashboards

When creating a dashboard focused on a specific task that involves a few devices (e.g., "Home Office", "Coffee Station", "Media Center"), include a **Maintenance section** alongside the primary controls. This section should contain:

- Battery levels for wireless devices
- Signal strength indicators
- Firmware update status
- Device connectivity states
- Any diagnostic entities relevant to the devices

This approach keeps users informed about the health of the devices supporting their task without cluttering the main interface. When something stops working, the maintenance section provides immediate visibility into potential issues.

## Respect Entity Categories

Entities have categories that indicate their intended purpose:

- **No category (primary)**: Main controls and states meant for regular user interaction
- **Diagnostic**: Entities for maintenance and troubleshooting (e.g., signal strength, battery level, firmware version)
- **Config**: Configuration entities for device settings (e.g., sensitivity levels, LED brightness)

When building dashboards:
- Group primary entities together for the main user interface
- Place diagnostic entities in a separate "Maintenance" or "Diagnostics" section
- Config entities typically belong in a dedicated settings area, not the main dashboard

This separation keeps dashboards clean and prevents users from accidentally changing configuration settings.

## Tile Card Features for Enhanced Control

Tile cards support features that provide additional control directly on the card. Consider using tile card features for:

- **Primary controls**: Light brightness slider, cover position, fan speed
- **Frequently used actions**: Toggle switches, quick actions

Avoid adding features to:
- Diagnostic entities
- Configuration entities
- Entities where simple state display is sufficient

Tile card features make important controls more accessible and visually prominent.

```yaml
type: tile
entity: light.ceiling_lights
features:
  - type: light-brightness
```

Available features: `cover-open-close`, `cover-position`, `cover-tilt`, `cover-tilt-position`, `light-brightness`, `light-color-temp`, `lock-commands`, `lock-open-door`, `media-player-playback`, `media-player-volume-slider`, `media-player-volume-buttons`, `fan-direction`, `fan-oscillate`, `fan-preset-modes`, `fan-speed`, `alarm-modes`, `climate-fan-modes`, `climate-swing-modes`, `climate-swing-horizontal-modes`, `climate-hvac-modes`, `climate-preset-modes`, `counter-actions`, `date-set`, `select-options`, `numeric-input`, `target-humidity`, `target-temperature`, `toggle`, `water-heater-operation-modes`, `humidifier-modes`, `humidifier-toggle`, `vacuum-commands`, `valve-open-close`, `valve-position`, `lawn-mower-commands`, `update-actions`, `trend-graph`, `area-controls`, `bar-gauge`,

## Specialized Cards for Specific Domains

### Climate Entities
Use the **thermostat card** for climate entities. It provides:
- Current and target temperature display
- HVAC mode selection
- Temperature adjustment controls
- A visual representation that users intuitively understand

```yaml
type: thermostat
entity: climate.heatpump
```

### Camera and Image Entities
Use **picture-entity cards** for camera and image entities:
- Hide the state (the image itself is the state)
- Hide the name unless the image context is ambiguous (most cameras and images are self-explanatory when viewed)
- Let the visual content speak for itself

```yaml
type: picture-entity
entity: camera.demo_camera
show_state: false
show_name: false
camera_view: auto
fit_mode: cover
```

### Graph Cards

Sometimes you want to show historical data for an entity. The choice of graph card depends on the type of entity:

#### Statistics Graph (for sensor entities)
Use **statistics-graph** cards when displaying sensor data over time:
- Automatically calculates and displays statistics (mean, min, max)
- Optimized for numerical sensor data
- Better performance for long time ranges

#### History Graph (for other entity types)
Use **history-graph** cards for:
- Climate entity history (showing temperature changes alongside HVAC states)
- Binary sensor timelines
- State-based entities where you want to see state changes over time
- Any non-sensor entity where historical data is valuable

The history graph shows actual state changes as they occurred, which is more appropriate for non-numerical entities.

## Using Badges for Global Information

Badges are ideal for displaying global data points that apply to an entire dashboard view. Good candidates include:

- Area temperature and humidity
- Security system status
- Weather conditions
- Presence/occupancy indicators
- General alerts or warnings

If the information is more specific to a subset of the dashboard, consider adding it to a section header instead of a badge. Badges work best for truly dashboard-wide context.

```yaml
type: entity
entity: sensor.temperature
```
