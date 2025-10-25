# ZeroGrid Integration

## Overview

ZeroGrid is a Home Assistant integration that intelligently manages controllable loads in your home to maximize the use of available power from solar generation and/or grid supply while preventing circuit overload. It dynamically allocates power to multiple loads based on priority, available capacity, and actual consumption patterns.

## Key Concepts

### Priority-Based Load Management
ZeroGrid manages multiple controllable loads (e.g., EV chargers, hot water heaters, pool pumps) by assigning each a priority level. Higher priority loads (lower numbers) get power first, with remaining capacity allocated to lower priority loads.

### Dynamic Power Allocation
The system continuously monitors:
- **House consumption** - Total power being used by the household
- **Solar generation** - Available solar power (optional)
- **Grid import limits** - Maximum allowable draw from the grid
- **Load consumption** - Actual power usage of each controllable load

### Reactive Reallocation
A key feature that makes ZeroGrid highly efficient is **reactive power reallocation**. When a load doesn't draw its expected power (e.g., hot water heater reaches temperature, EV battery is full), that unused power is immediately detected and reallocated to other loads rather than being wasted.

## How It Works

### 1. Configuration Phase
At startup, ZeroGrid reads your configuration including:
- Maximum house load limits (prevents tripping circuit breakers)
- List of controllable loads with their priorities and power requirements
- Power monitoring entity IDs (consumption, voltage, solar generation)
- Reactive reallocation settings

### 2. State Initialization
The system initializes by reading current states from Home Assistant:
- Current house consumption in amps
- Mains voltage
- Solar generation (if configured)
- Whether grid import is allowed
- Current state of all controllable loads (on/off, current draw)

### 3. Continuous Monitoring
ZeroGrid subscribes to state changes for all monitored entities:
- **House consumption changes** - Triggers recalculation of available power
- **Solar generation changes** - Updates available power budget
- **Load consumption changes** - Monitors actual vs expected usage
- **Switch state changes** - Tracks when loads are manually controlled
- **Time-based events** - Periodic recalculation (every 10 seconds by default)

### 4. Power Calculation Algorithm

#### Available Power Calculation
```python
# Base calculation
grid_available = max_house_load - house_consumption

# Solar power calculation
if allow_grid_import:
    # Solar adds on top of grid headroom (up to absolute max)
    solar_amps = (solar_generation_kw * 1000) / voltage
    base_available = min(grid_available + solar_amps, max_house_load)
else:
    # Solar-only mode: only use solar that exceeds consumption
    solar_amps = (solar_generation_kw * 1000) / voltage
    solar_net = solar_amps - house_consumption
    base_available = min(solar_net, grid_available)

# Apply safety margin
base_available -= hysteresis_amps

# Calculate reactive power from underperforming loads
reactive_available = sum(expected_consumption - actual_consumption)
                     for loads where variance > threshold

# For planning: base + reactive (capped to physical grid limit)
planning_available = min(base_available + reactive_available,
                        grid_available - hysteresis_amps)

# For display: base only (reactive is internal reallocation)
display_available = base_available
```

**Key improvements:**
- Solar power correctly adds on top of grid capacity when grid import is enabled
- Multiple safety caps prevent exceeding physical limits
- Separate display vs planning values for better user visibility
- Reactive power used internally but not shown as "available" to users

#### Load Planning Algorithm
For each load in priority order:

1. **Credit back current consumption** - If the load is currently on, add its power back to the available budget
2. **Cap after crediting** - Ensure credited power doesn't exceed physical grid limits
3. **Calculate minimum requirements** - Determine minimum power needed for all lower-priority loads
4. **Check throttling opportunities** - Can we throttle lower-priority loads to make room for this one?
5. **Determine allocation** - Calculate how much power this load should get
6. **Apply rate limiting** - Respect minimum toggle/throttle intervals to prevent rapid switching
7. **Handle overload** - Immediately shed loads if the circuit is overloaded
8. **Update power budget** - Subtract allocated power from available budget
9. **Validate plan** - Check for over-allocation and trigger emergency load shedding if needed

**Safety features:**
- Multiple caps throughout to prevent exceeding grid capacity
- Over-allocation detection with emergency load shedding
- Credit-back capping prevents inflated available power
- Conservative safety margins prevent tripping breakers

#### Smart Priority Allocation
- Higher priority loads can throttle down lower priority loads to get the power they need
- Lower priority loads can use unused power from higher priority loads (reactive reallocation)
- Throttleable loads can be dynamically adjusted between min and max values
- Non-throttleable loads are binary (on/off only)

### 5. Reactive Variance Detection

The system continuously monitors each load's actual vs expected consumption:

```python
variance = expected_consumption - actual_consumption

if variance >= threshold and time_since_update >= delay:
    # This load is using less power than planned
    # Make that power available for other loads
    trigger_reallocation()
```

**Benefits:**
- **Hot water heater** reaches temperature → Unused power freed for other loads
- **EV charger** battery approaches full → Gradually freed power redistributed
- **Pool heater** cycles off → Power immediately available for backup loads
- **Multiple loads** underperforming → Total unused power reallocated efficiently

### 6. Plan Execution

Once the optimal allocation is calculated, ZeroGrid executes the plan:

1. **Switch Control** - Turn loads on or off as needed
2. **Throttle Control** - Adjust throttleable loads to target values (respecting hysteresis)
3. **State Tracking** - Update expected consumption for variance monitoring
4. **Rate Limiting** - Record last toggle/throttle times to prevent rapid changes

### 7. Safety Features

- **Emergency Abort** - Cuts all loads if critical sensors become unavailable
- **Overload Protection** - Immediately sheds loads if consumption exceeds safe limits
- **Safety Margins** - Hysteresis prevents oscillation and provides buffer
- **Validation** - Detects and corrects power over-allocation scenarios
- **Entity Validation** - Checks entity existence before service calls

## Configuration

### Basic Setup

```yaml
zero_grid:
  max_house_load_amps: 32              # Maximum safe load for your main circuit
  hysteresis_amps: 2                   # Safety margin to prevent oscillation
  recalculate_interval_seconds: 10     # How often to recalculate (in addition to state changes)
  house_consumption_amps_entity: "sensor.house_consumption"
  mains_voltage_entity: "sensor.mains_voltage"

  controllable_loads:
    - name: "hot_water_heater"
      priority: 0                       # Highest priority (0 = first)
      max_controllable_load_amps: 10
      min_controllable_load_amps: 10
      min_toggle_interval_seconds: 300  # 5 minutes between on/off
      load_amps_entity: "sensor.hot_water_current"
      switch_entity: "switch.hot_water_heater"
```

### Optional Features

#### Solar Generation
```yaml
zero_grid:
  solar_generation_kw_entity: "sensor.solar_generation"
  # System will prioritize using solar power over grid import
```

#### Grid Import Control
```yaml
zero_grid:
  allow_grid_import_entity: "input_boolean.allow_grid_import"
  # Enable/disable ability to draw from grid (useful for battery systems)
```

#### Reactive Reallocation (Recommended)
```yaml
zero_grid:
  enable_reactive_reallocation: true    # Default: true
  variance_detection_threshold: 1.0     # Minimum amps variance to trigger (default: 1.0)
  variance_detection_delay_seconds: 30  # Stability period before reallocation (default: 30)
```

#### Throttleable Loads
```yaml
controllable_loads:
  - name: "ev_charger"
    priority: 1
    max_controllable_load_amps: 16
    min_controllable_load_amps: 6       # Can throttle between 6-16A
    min_toggle_interval_seconds: 60
    min_throttle_interval_seconds: 30   # Minimum time between throttle adjustments
    load_amps_entity: "sensor.ev_charger_current"
    switch_entity: "switch.ev_charger"
    throttle_amps_entity: "number.ev_charger_max_current"  # Must be a number entity
```

## State Management

### State Objects

**State** - Current system state:
- `house_consumption_amps` - Total household power draw
- `load_control_consumption_amps` - Power used by controllable loads
- `mains_voltage` - Current voltage
- `solar_generation_kw` - Solar power available
- `allow_grid_import` - Whether grid import is enabled
- `controllable_loads[]` - State of each load:
  - `is_on` - Actual switch state
  - `current_load_amps` - Actual power consumption
  - `expected_load_amps` - What we planned for it to use
  - `consumption_variance` - Difference between expected and actual
  - `last_toggled` - When it was last switched
  - `last_throttled` - When it was last throttled
  - `last_expected_update` - When expectation was last set

**PlanState** - Calculated load control plan:
- `available_amps` - Total power budget
- `used_amps` - Total planned consumption
- `controllable_loads[]` - Plan for each load:
  - `is_on` - Should it be on?
  - `expected_load_amps` - How much should it consume?
  - `throttle_amps` - Throttle setting (if applicable)

## Entities Created

ZeroGrid creates the following entities:

### Sensors
- **`sensor.zero_grid_available_load`** - Grid headroom available for new loads (in amps)
  - Shows base available power only (excludes reactive reallocation)
  - Updates immediately when house consumption or solar generation changes
  - Represents how much new load capacity exists

- **`sensor.zero_grid_controlled_load`** - Actual planned consumption of controlled loads (in amps)
  - Shows the sum of all loads planned to be on
  - Updates when loads are turned on/off or throttled
  - Represents actual power being used by ZeroGrid-controlled loads
  - Will be less than "Available load" when loads don't need all available power

### Switches
- **`switch.zero_grid_enable_load_control`** - Master enable/disable for load control
- **`switch.zero_grid_allow_grid_import`** - Enable/disable grid import (useful for battery systems)

**Note:** Available load and Controlled load will only match when your loads are using all available power. This is normal and indicates efficient power utilization.

## Load Behavior Scenarios

### Scenario 1: Abundant Solar Power
- All high-priority loads turn on first
- Lower priority loads turn on as power becomes available
- Throttleable loads run at maximum within available power
- Reactive reallocation handles loads that don't draw full power

### Scenario 2: Limited Power Available
- Only highest priority loads operate
- Lower priority loads wait for more power
- Throttleable loads may run at reduced capacity
- System continuously checks for freed power to enable more loads

### Scenario 3: Cloud Passes Over Solar Panels
- Available power drops suddenly
- Lower priority loads turn off immediately
- Throttleable loads reduce consumption
- Highest priority loads remain on
- System recovers automatically when sun returns

### Scenario 4: Hot Water Heater Reaches Temperature
- Hot water heater allocated 10A, drawing 10A
- Thermostat satisfied, consumption drops to 1A
- After 30 seconds (variance_detection_delay), 9A variance detected
- 9A freed for lower-priority loads (e.g., pool heater can now turn on)
- System immediately recalculates and enables additional loads

### Scenario 5: EV Charging Completion
- EV charger allocated 16A at priority 1
- As battery approaches full, charging current drops to 4A
- 12A variance detected and freed for reallocation
- Pool heater (priority 2) can now turn on or increase throttle
- Backup loads (priority 3) may also become available

### Scenario 6: Multiple Loads Underperforming
- Hot water heater: 10A allocated, 2A actual → 8A freed
- EV charger: 16A allocated, 6A actual → 10A freed
- Pool heater: 8A allocated, 8A actual → 0A freed
- Total: 18A reactive power available
- Backup loads and other low-priority loads can now operate

## Advantages Over Static Systems

Traditional load management systems suffer from:
- **Wasted allocation** - Power allocated to loads that aren't using it
- **Slow response** - Only reallocate when loads are manually turned off
- **Poor efficiency** - Lower priority loads stay off even when power is available

ZeroGrid with reactive reallocation provides:
- **Real-time efficiency** - Unused power detected and redistributed within seconds
- **Dynamic response** - Handles thermostatic controls, charge completion, cycling loads
- **Better utilization** - More loads can operate by using underutilized allocations
- **Reduced waste** - No power allocation goes unused
- **Automatic optimization** - No manual intervention needed

## Performance Considerations

- **Lightweight monitoring** - Only calculates variances when states change
- **Selective recalculation** - Only triggers when significant changes occur
- **Hysteresis protection** - Prevents rapid switching and oscillation
- **Rate limiting** - Respects device-specific toggle and throttle constraints
- **Efficient execution** - Uses existing Home Assistant service infrastructure

## Safety and Reliability

- **Fail-safe design** - Critical sensor failures trigger emergency load shedding
- **Over-allocation protection** - Validates plans and turns off lowest priority loads if needed
- **Conservative margins** - Hysteresis ensures system stays within safe limits
- **Multiple safety caps** - Power calculations capped at every stage to prevent exceeding physical limits
- **Credit-back capping** - Load crediting cannot inflate available power beyond grid capacity
- **Solar calculation safety** - Solar power correctly bounded to prevent exceeding main fuse rating
- **Rate limiting** - Prevents damage from excessive switching
- **Backward compatible** - Reactive features can be disabled if needed
- **Emergency detection** - Logs critical warnings when over-allocation detected

## Debugging and Logging

ZeroGrid provides extensive debug logging:

```python
_LOGGER.debug("Available amps: %f", available_amps)
_LOGGER.info("Turning on %s due to available load", switch_entity)
_LOGGER.warning("Unable to change load %s due to rate limit", load_name)
_LOGGER.error("Switch entity %s does not exist, skipping control", switch_entity)
```

Enable debug logging in Home Assistant:
```yaml
logger:
  default: info
  logs:
    homeassistant.components.zero_grid: debug
```

## Future Enhancement Possibilities

1. **Learning Algorithm** - Track historical patterns to predict load behavior
2. **Weather Integration** - Use weather forecasts to predict solar availability
3. **Advanced Scheduling** - Coordinate load timing based on expected patterns
4. **Battery Integration** - Incorporate battery state of charge in decisions
5. **Cost Optimization** - Consider time-of-use rates in priority calculations
6. **Performance Metrics** - Track efficiency gains and power utilization statistics

## Technical Implementation Notes

- **Language**: Python 3.13+ with modern features (pattern matching, type hints, f-strings)
- **Integration Type**: Helper integration (calculated values, no external API)
- **Update Method**: Event-driven (state changes) + periodic (time interval)
- **State Persistence**: Uses Home Assistant state machine
- **Service Calls**: Domain-specific (switch.turn_on, number.set_value, etc.)
- **Thread Safety**: Uses Home Assistant's async/await patterns

### Recent Bug Fixes (2025-10)

**Issue: Solar power incorrectly calculated**
- **Problem**: When grid import was enabled, solar power was ignored entirely, or when calculated, it was incorrectly subtracting house consumption (which was already accounted for)
- **Fix**: Solar generation now correctly adds on top of grid headroom when grid import is enabled, with proper capping to prevent exceeding main fuse rating

**Issue: Available and Controlled load sensors always matching**
- **Problem**: Both sensors showed the same value because they were both capped to the same formula
- **Fix**: Separated display available (base power only) from planning available (base + reactive). "Controlled load" now shows actual planned consumption without artificial capping

**Issue: Reactive power exceeding safe limits**
- **Problem**: Reactive reallocation could push total available power beyond physical grid capacity
- **Fix**: Added cap to total available power after reactive calculation to never exceed grid limits

**Issue: Load crediting inflating available power**
- **Problem**: When loads were credited back during planning, available power could exceed physical limits
- **Fix**: Added safety cap after every credit operation to ensure available power never exceeds grid capacity

These fixes ensure that:
- With 0 solar and 30A consumption at 63A max: Available shows ~31A (not 93A)
- Solar power properly contributes when available
- Sensors show different values when loads use less than available
- System never exceeds physical grid limits regardless of reactive reallocation

## Related Documentation

- See `REACTIVE_REALLOCATION.md` for detailed technical documentation of the reactive power features
- See `example_reactive_config.yaml` for a complete configuration example with annotations

## Credits

- **Author**: @mike-debney
- **Integration Domain**: zero_grid
- **Quality Scale**: Bronze
