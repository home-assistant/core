# Sandbox v2 compat report

Plugin: `hass_client.testing.pytest_plugin`

## Summary

- Integrations passing: **35**
- Integrations with issues: **2**
- Timeouts: **0**
- No tests collected: **0**

- Tests passed: **7646**
- Tests failed: **2**
- Test errors: **0**
- Tests skipped: **17**

## Per-integration results

| integration | status | passed | failed | errors | skipped |
| --- | --- | ---: | ---: | ---: | ---: |
| input_boolean | pass | 18 | 0 | 0 | 0 |
| input_button | pass | 15 | 0 | 0 | 0 |
| input_datetime | pass | 28 | 0 | 0 | 0 |
| input_number | pass | 24 | 0 | 0 | 0 |
| input_select | pass | 26 | 0 | 0 | 0 |
| input_text | pass | 23 | 0 | 0 | 0 |
| counter | pass | 751 | 0 | 0 | 0 |
| timer | pass | 877 | 0 | 0 | 0 |
| schedule | pass | 387 | 0 | 0 | 0 |
| zone | pass | 32 | 0 | 0 | 0 |
| tag | pass | 12 | 0 | 0 | 0 |
| group | pass | 392 | 0 | 0 | 0 |
| person | pass | 34 | 0 | 0 | 0 |
| scene | pass | 41 | 0 | 0 | 0 |
| todo | pass | 281 | 0 | 0 | 0 |
| automation | pass | 117 | 0 | 0 | 0 |
| script | pass | 64 | 0 | 0 | 0 |
| alert | pass | 18 | 0 | 0 | 0 |
| template | pass | 2470 | 0 | 0 | 0 |
| plant | pass | 11 | 0 | 0 | 0 |
| proximity | issues | 27 | 1 | 0 | 0 |
| min_max | pass | 20 | 0 | 0 | 0 |
| statistics | pass | 56 | 0 | 0 | 0 |
| utility_meter | issues | 94 | 1 | 0 | 0 |
| derivative | pass | 76 | 0 | 0 | 0 |
| integration | pass | 61 | 0 | 0 | 0 |
| generic_thermostat | pass | 114 | 0 | 0 | 0 |
| generic_hygrostat | pass | 76 | 0 | 0 | 0 |
| history_stats | pass | 55 | 0 | 0 | 0 |
| threshold | pass | 114 | 0 | 0 | 0 |
| filter | pass | 32 | 0 | 0 | 0 |
| mqtt_statestream | pass | 17 | 0 | 0 | 0 |
| recorder | pass | 932 | 0 | 0 | 17 |
| rest | pass | 128 | 0 | 0 | 0 |
| logbook | pass | 106 | 0 | 0 | 0 |
| command_line | pass | 78 | 0 | 0 | 0 |
| trend | pass | 39 | 0 | 0 | 0 |
