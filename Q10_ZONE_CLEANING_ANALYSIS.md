# Q10 Zone/Room Cleaning API Analysis

## Résumé des Résultats

Voici comment implémenter le nettoyage de zones (pièces) pour le Roborock Q10 S5+.

## 1. DP Codes Disponibles pour le Nettoyage de Zones

Le Q10 utilise les DP (Data Points) codes suivants pour gérer le nettoyage de zones:

```python
from roborock.data.b01_q10 import B01_Q10_DP

# Zone-related DP codes:
B01_Q10_DP.START_CLEAN           # dpStartClean (code: 201)
B01_Q10_DP.ZONED                 # dpZoned (code: 58)  - Define zones to clean
B01_Q10_DP.ZONED_UP              # dpZonedUp (code: 59) - Update zones
B01_Q10_DP.REMOVE_ZONED          # dpRemoveZoned (code: 70)
B01_Q10_DP.REMOVE_ZONED_UP       # dpRemoveZonedUp (code: 71)
B01_Q10_DP.ADD_CLEAN_AREA        # dpAddCleanArea - Add area
B01_Q10_DP.ADD_CLEAN_STATE       # dpAddCleanState - State for area cleaning
B01_Q10_DP.CLEAN_MODE            # dpCleanMode - Set cleaning mode (sweep/mop/sweep+mop)
B01_Q10_DP.AREA_UNIT             # dpAreaUnit - Unit for area (m²/sqft)
B01_Q10_DP.CLEAN_AREA            # dpCleanArea - Current cleaning area
```

## 2. API Structure

The Q10 uses `CommandTrait.send()` to send commands:

```python
from roborock.devices.traits.b01.q10 import CommandTrait

# Method signature:
async def send(self, command: B01_Q10_DP, params: list | dict | int | None = None) -> Any
```

### Example Usage

```python
# Access the command trait via coordinator
command_trait = coordinator.api.command

# Send a zone cleaning command
await command_trait.send(
    command=B01_Q10_DP.ZONED,
    params=[room_id]  # room_id can be 1, 2, 3, etc.
)

# Or with coordinates (x1, y1, x2, y2):
await command_trait.send(
    command=B01_Q10_DP.ZONED,
    params=[[x1, y1, x2, y2]]
)
```

## 3. MQTT Communication Flow

From the logs, we can see the flow:

1. **Device sends status update via MQTT** (every coordinator refresh):
   ```
   Received Q10 status update: {<B01_Q10_DP.STATUS: 'dpStatus'>: 2, ...}
   ```

2. **Coordinator updates data every 5 seconds**:
   ```
   Finished fetching roborock data in 1.014 seconds (success: True)
   ```

3. **Entity reads from coordinator.data**:
   ```python
   @property
   def activity(self) -> VacuumActivity | None:
       status = _get_q10_status(self.coordinator.data)
       return Q7_STATE_CODE_TO_STATE.get(status)
   ```

## 4. Status Code Mapping

The Q10 status codes (YXDeviceState) and their meanings:

```python
from roborock.data.b01_q10.b01_q10_code_mappings import YXDeviceState

# Status codes:
YXDeviceState.STANDBY_STATE      # code: 3  -> VacuumActivity.IDLE
YXDeviceState.CLEANING_STATE     # code: 5  -> VacuumActivity.CLEANING
YXDeviceState.TO_CHARGE_STATE    # code: 6  -> VacuumActivity.RETURNING
YXDeviceState.CHARGING_STATE     # code: 8  -> VacuumActivity.DOCKED
YXDeviceState.PAUSE_STATE        # code: 10 -> VacuumActivity.PAUSED

# Mapping (already fixed in vacuum.py):
status_map = {
    1: WorkStatusMapping.SWEEP_MOPING,        # ROBOT_SWEEPING
    2: WorkStatusMapping.SWEEP_MOPING,        # ROBOT_MOPING
    3: WorkStatusMapping.WAITING_FOR_ORDERS,  # STANDBY_STATE (idle)
    4: WorkStatusMapping.SWEEP_MOPING,        # ROBOT_SWEEP_AND_MOPING
    5: WorkStatusMapping.SWEEP_MOPING,        # CLEANING_STATE
    6: WorkStatusMapping.DOCKING,             # TO_CHARGE_STATE (returning)
    8: WorkStatusMapping.CHARGING,            # CHARGING_STATE
    10: WorkStatusMapping.PAUSED,             # PAUSE_STATE
}
```

## 5. How to Implement Zone Cleaning

### Option A: Simple Room Cleaning (by room ID)

```python
async def async_clean_spot(self, **kwargs: Any) -> None:
    """Clean specific room/zone by ID."""
    try:
        # Get room ID from Home Assistant service params
        room_id = kwargs.get("room_id", 1)  # Default to room 1
        
        # Set zone to clean
        await self.coordinator.api.command.send(
            command=B01_Q10_DP.ZONED,
            params=[room_id]
        )
        
        # Start cleaning
        await self.coordinator.api.vacuum.start_clean()
    except RoborockException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"command": "clean_zone"},
        ) from err
    
    await self.coordinator.async_refresh()
```

### Option B: Coordinate-based Zone Cleaning

```python
async def async_clean_zone(self, x1: int, y1: int, x2: int, y2: int) -> None:
    """Clean a zone by coordinates."""
    try:
        # Set coordinates for zone
        await self.coordinator.api.command.send(
            command=B01_Q10_DP.ZONED,
            params=[[x1, y1, x2, y2]]
        )
        
        # Start cleaning
        await self.coordinator.api.vacuum.start_clean()
    except RoborockException as err:
        raise HomeAssistantError(...) from err
    
    await self.coordinator.async_refresh()
```

## 6. Integration with Home Assistant

To add zone cleaning to Home Assistant:

1. **Create a new service in `__init__.py`**:
   ```yaml
   homeassistant/components/roborock/services.yaml:
   
   vacuum_clean_zone:
     target:
       entity:
         integration: roborock
         domain: vacuum
     fields:
       room_id:
         example: 1
         required: true
         selector:
           text:
             type: number
   ```

2. **Register the service handler**:
   ```python
   platform.async_register_entity_service(
       "clean_zone",
       {
           vol.Required("room_id"): cv.positive_int,
       },
       "async_clean_zone",
   )
   ```

3. **Implement in `RoborockQ10Vacuum`**:
   ```python
   async def async_clean_zone(self, room_id: int) -> None:
       """Clean specific zone/room."""
       try:
           await self.coordinator.api.command.send(
               command=B01_Q10_DP.ZONED,
               params=[room_id]
           )
           await self.coordinator.api.vacuum.start_clean()
       except RoborockException as err:
           raise HomeAssistantError(...) from err
       
       await self.coordinator.async_refresh()
   ```

## 7. Testing / Reproduction Steps

To test zone cleaning:

1. **Option 1: Via Python script**:
   ```python
   import asyncio
   from roborock.devices.traits.b01.q10 import Q10PropertiesApi
   from roborock.data.b01_q10 import B01_Q10_DP
   
   async def test_zone_clean():
       # Assuming you have api instance
       # 1. Set zone
       await api.command.send(B01_Q10_DP.ZONED, params=[1])  # Room 1
       # 2. Start cleaning
       await api.vacuum.start_clean()
   ```

2. **Option 2: Via Home Assistant UI** (after implementation):
   - Go to Developer Tools > Services
   - Call `roborock.vacuum.clean_zone` service
   - Pass `room_id: 1`
   - Vacuum will clean that zone

## 8. Key Findings from Logs

From the captured MQTT logs:

1. **Commands are sent via MQTT** to topic `rr/m/i/{device-id}`
2. **Device responds with status** on topic `rr/m/o/{device-id}`
3. **Status updates include all DP codes** in the response
4. **Command execution is asynchronous** - device may take few seconds
5. **After command, coordinator.async_refresh()** should be called to fetch latest state

## 9. Areas for Future Enhancement

- [ ] Support for multiple zones in single command
- [ ] Zone name/label support (integrate with map data)
- [ ] Persistent zone definitions (save often-used zones)
- [ ] Zone presence detection integration
- [ ] Coordinate visualization in UI

