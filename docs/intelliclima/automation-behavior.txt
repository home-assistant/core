# Automation Behavior Options

When creating automations with triggers or conditions that target multiple entities, you can specify how the automation should behave using behavior options.

## Trigger Behavior

The trigger behavior controls when the trigger fires when multiple entities are specified.

Available options:

- **any**: The trigger fires when any one of the specified entities matches the trigger condition.
- **first**: The trigger fires only on the first matching event from the specified entities.
- **last**: The trigger fires only after all specified entities have matched the trigger condition at least once.

## Condition Behavior

The condition behavior controls how multiple conditions are evaluated.

Available options:

- **all**: All conditions must pass for the automation to run.
- **any**: At least one condition must pass for the automation to run.

## YAML Examples

### Trigger with "any" behavior

```yaml
automation:
  trigger:
    - platform: state
      entity_id:
        - sensor.temperature_living_room
        - sensor.temperature_kitchen
      to: "hot"
      behavior: any
  action:
    - service: notify.mobile_app
      data:
        message: "A room is getting hot!"
```

This automation triggers when any of the listed sensors reports "hot".

### Trigger with "first" behavior

```yaml
automation:
  trigger:
    - platform: state
      entity_id:
        - binary_sensor.door_front
        - binary_sensor.door_back
      to: "on"
      behavior: first
  action:
    - service: notify.mobile_app
      data:
        message: "First door event detected"
```

This automation triggers only on the first matching event.

### Trigger with "last" behavior

```yaml
automation:
  trigger:
    - platform: state
      entity_id:
        - light.living_room
        - light.kitchen
        - light.bedroom
      to: "on"
      behavior: last
  action:
    - service: light.turn_on
      target:
        entity_id: light.hallway
```

This automation triggers only after all specified entities have matched the condition at least once.

### Condition with "all" behavior

```yaml
automation:
  trigger:
    - platform: time
      at: "18:00"
  condition:
    - condition: state
      entity_id: person.alice
      state: "home"
    - condition: state
      entity_id: person.bob
      state: "home"
      behavior: all
  action:
    - service: media_player.play_media
      target:
        entity_id: media_player.living_room
```

This automation runs only if all conditions are true.

### Condition with "any" behavior

```yaml
automation:
  trigger:
    - platform: time
      at: "07:00"
  condition:
    - condition: state
      entity_id: person.alice
      state: "home"
    - condition: state
      entity_id: person.bob
      state: "home"
      behavior: any
  action:
    - service: climate.set_temperature
      data:
        temperature: 21
      target:
        entity_id: climate.living_room
```

This automation runs if at least one condition is true.

## Notes

- Behavior options are available for triggers and conditions that support multiple entities.
- Default behavior is "any" for triggers and "all" for conditions.
- These options allow more precise control over automation logic involving multiple entities.