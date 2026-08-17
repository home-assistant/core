# Draft — home-assistant.io docs for Daikin demand control

Draft changes for `source/_integrations/daikin.markdown` in
[home-assistant/home-assistant.io](https://github.com/home-assistant/home-assistant.io).

## 1. Frontmatter: add `binary_sensor` platform

```yaml
ha_platforms:
  - binary_sensor
  - climate
  - diagnostics
  - sensor
  - switch
```

## 2. New "Binary sensor" section

When the unit supports demand control, the integration creates a
**Demand control** binary sensor that is **On** while demand control is
enabled. Its attributes expose the current demand control settings as
reported by the unit:

- `en_demand`: whether demand control is enabled
- `mode`: the demand control mode (`0` manual, `1` scheduled, `2` auto)
- `max_pow`: the maximum power limit as a percentage of the unit's
  nominal power
- schedule data (`scdl_per_day`, per-day counts and per-event entries)
  when a schedule is set

## 3. New "Services" section

### Action `set_demand_control`

The `set_demand_control` action limits the maximum power of the unit to a
percentage of its nominal power, for example to reduce power consumption
during peak electricity price periods. It is only available on units that
support demand control and on the main climate entity (not the zone
climate entities).

| Data attribute | Optional | Description                                                                               |
| -------------- | -------- | ----------------------------------------------------------------------------------------- |
| `entity_id`    | no       | The main climate entity of the unit, for example `climate.bedroom`.                       |
| `en_demand`    | no       | Whether demand control should be enabled.                                                 |
| `max_pow`      | no       | Maximum power as a percentage of the unit's nominal power (0-100).                        |
| `mode`         | yes      | Demand control mode: `0` (manual), `1` (scheduled), `2` (auto). Defaults to `0` (manual). |

Example:

```yaml
action: daikin.set_demand_control
data:
  entity_id: climate.bedroom
  en_demand: true
  max_pow: 50
  mode: 0
```

{% note %}

- `max_pow` is only applied in manual mode (`mode: 0`).
- `mode: 1` (scheduled) applies the previously configured schedule and
  requires a schedule to have been set first (for example with the ONECTA
  app or the WLAN API).

{% endnote %}
