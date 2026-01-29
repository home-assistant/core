# Webex CE Integration - Massive Feature Addition Implementation Guide

## Overview
This document outlines all changes needed to add the requested features to the Webex CE integration.

## Files Created ✅
1. `binary_sensor.py` - Recording, streaming, availability, and proximity sensors
2. `button.py` - Call control and display wake buttons
3. `services.yaml` - Service definitions for dial, DTMF, camera control, messages, webviews

## Files That Need Updates

### 1. `__init__.py` - Add platforms and register services
**Changes needed:**
- Add `Platform.BINARY_SENSOR` and `Platform.BUTTON` to PLATFORMS list
- Add service registration in `async_setup_entry` for all services defined in services.yaml
- Add event subscription for UI Extensions in client setup

### 2. `client.py` - Add event handling
**Changes needed:**
- Add `subscribe_events` method to handle xEvent subscriptions
- Add event callback registration for UserInterface Extensions Widget Action
- Fire Home Assistant events when UI extension buttons are pressed

### 3. `sensor.py` - Add many new sensors
**New sensors to add:**
- Network IPv4 Address
- Network IPv6 Address
- Network Speed
- Network VLAN ID
- System Uptime
- Hardware Temperature
- CPU Load
- Memory Usage
- Engagement Close Proximity (as sensor, not binary)
- Connected Input Sources (multiple)
- Peripheral Devices (multiple)
- USB Devices
- Audio Input Levels (multiple microphones)
- Audio Output Levels
- Current Meeting Title
- Current Meeting Organizer
- Current Meeting Start Time
- Current Meeting End Time
- Next Meeting Title
- Next Meeting Start Time
- Recording Duration
- Streaming Duration

### 4. `switch.py` - Add new switches
**New switches to add:**
- Self View (xCommand Video Selfview Set Mode: On/Off)
- Presentation (xCommand Presentation Start/Stop)

### 5. `number.py` - Add brightness control
**New number entity to add:**
- Touch Panel Brightness (xConfiguration UserInterface TouchPanel Brightness)

### 6. `select.py` - Add new selects
**New selects to add:**
- Presentation Source (Video Input Source 1-5)
- Camera Preset (1-35, with ability to recall presets)

### 7. `strings.json` - Complete reorganization
**Structure should be:**
```
Controls (in order):
1. Standby (select)
2. Self View (switch)
3. Presentation (switch)
4. Presentation Source (select)
5. Video Mute (switch)
6. Microphone Mute (switch)
7. Volume (number)
8. Touch Panel Brightness (number)
9. Camera Preset (select)

Call Controls (buttons):
10. Accept Call
11. Reject Call
12. Disconnect Call
13. Hold Call
14. Resume Call
15. Wakeup Display

Call Status (sensors):
16. Call Status (with attributes)

Room Status (sensors):
17. People Presence
18. People Count
19. Engagement Close Proximity
20. Sound Level
21. Ambient Noise
22. Ambient Temperature
23. Relative Humidity

Meeting/Calendar (sensors + binary_sensor):
24. Availability Status (binary_sensor)
25. Current Meeting
26. Current Meeting Organizer
27. Current Meeting Time Start
28. Current Meeting Time End
29. Next Meeting
30. Next Meeting Time

System Status (sensors):
31. System Uptime
32. CPU Load
33. Memory Usage
34. Hardware Temperature

Network Status (sensors):
35. Network IPv4
36. Network IPv6
37. Network Speed
38. Network VLAN

Peripherals (sensors):
39. Connected Input Sources
40. Peripheral Devices
41. USB Devices

Audio Status (sensors):
42. Audio Input Levels
43. Audio Output Levels

Recording/Streaming (binary_sensors + sensors):
44. Recording Status (binary_sensor)
45. Recording Duration (sensor)
46. Streaming Status (binary_sensor)
47. Streaming Duration (sensor)
```

## Service Implementations Needed in `__init__.py`

All services need handlers that:
1. Validate config entry is loaded
2. Get the client from entry.runtime_data
3. Execute the appropriate xCommand
4. Handle errors properly

### Service: `dial`
- xCommand: `Dial`, params: `Number: <number>`

### Service: `send_dtmf`
- xCommand: `Call DTMFSend`, params: `DTMFString: <dtmf>`

### Service: `camera_preset_activate`
- xCommand: `Camera Preset Activate`, params: `PresetId: <preset_id>`

### Service: `camera_preset_store`
- xCommand: `Camera Preset Store`, params: `PresetId: <preset_id>`

### Service: `camera_position_set`
- xCommand: `Camera PositionSet`, params: `CameraId: <id>`, `Pan: <pan>`, `Tilt: <tilt>`, `Zoom: <zoom>`

### Service: `camera_ramp`
- xCommand: `Camera Ramp`, params: `CameraId: <id>`, `<Direction>: <speed>`

### Service: `camera_ramp_stop`
- xCommand: `Camera Ramp`, params: `CameraId: <id>`, `Stop: {}`

### Service: `display_message`
- xCommand: `UserInterface Message TextLine Display`, params: `Text: <text>`, `Duration: <duration>`

### Service: `clear_message`
- xCommand: `UserInterface Message TextLine Clear`

### Service: `display_webview`
- xCommand: `UserInterface WebView Display`, params: `Url: <url>`, `Title: <title>`, `Mode: <mode>`

### Service: `close_webview`
- xCommand: `UserInterface WebView Clear`

## Event Handling for UI Extensions

In `client.py`, add method to subscribe to events:

```python
async def subscribe_ui_events(self, callback: callable) -> None:
    """Subscribe to UI extension events."""
    if not self._client:
        raise RuntimeError("Client not connected")

    # Subscribe to UserInterface Extensions Widget Action events
    await self._client.subscribe_event(
        "UserInterface Extensions Widget Action",
        callback
    )
```

Then in `__init__.py`, in `async_setup_entry`:

```python
async def handle_ui_event(event_data):
    """Handle UI extension button press events."""
    # event_data will contain:
    # - WidgetId: The ID of the widget/button pressed
    # - Type: Usually "pressed" or "released"
    # - Value: Additional value if applicable

    hass.bus.fire(
        f"{DOMAIN}_ui_event",
        {
            "widget_id": event_data.get("WidgetId"),
            "type": event_data.get("Type"),
            "value": event_data.get("Value"),
        }
    )

await client.subscribe_ui_events(handle_ui_event)
```

## Implementation Priority

Due to scope, implement in this order:
1. ✅ binary_sensor.py (DONE)
2. ✅ button.py (DONE)
3. ✅ services.yaml (DONE)
4. Update __init__.py (add platforms, register services, add event handling)
5. Update client.py (add event subscription method)
6. Expand sensor.py (add all new sensors)
7. Expand switch.py (add self view and presentation)
8. Expand number.py (add brightness)
9. Expand select.py (add presentation source and camera preset)
10. Update strings.json (complete reorganization with all translations)

## Testing Considerations

After implementation:
1. Test all call control buttons
2. Test dial service
3. Test camera controls
4. Test message display
5. Test webview display
6. Test UI extension event firing
7. Verify all sensors update correctly
8. Check that booking/calendar info displays
9. Verify network and system metrics
10. Test recording/streaming status detection

## Notes

- Some sensors may not be available on all device models
- UI Extensions events require custom UI panels to be configured on the device
- Camera controls assume Camera ID 1 is the main camera
- Booking/calendar info requires calendar integration on the device
- Some features require specific RoomOS versions

