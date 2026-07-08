# Compat failure clusters

10562 FAILED/ERROR lines across 825 integrations; 1292 distinct signatures; 18 timeouts.

| # | failures | integrations | signature |
|---:|---:|---:|---|
| 1 | 1040 | 172 | `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.FORM: 'form'>` |
| 2 | 822 | 218 | `AssertionError @ tests/<suite>: assert [+ received] == [- snapshot]` |
| 3 | 809 | 85 | `AssertionError @ tests/<suite>: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.LOADED: 'loaded'>` |
| 4 | 788 | 333 | `AssertionError @ tests/<suite>: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.SETUP_RETRY: 'setup_retry'>` |
| 5 | 662 | 61 | `ServiceNotFound @ homeassistant/core.py: Action EID not found` |
| 6 | 519 | 87 | `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'state'` |
| 7 | 377 | 71 | `AssertionError @ tests/<suite>: Regex pattern did not match.` |
| 8 | 332 | 50 | `AttributeError @ tests/<suite>: 'MockConfigEntry' object has no attribute 'runtime_data'` |
| 9 | 274 | 234 | `AssertionError @ tests/<suite>: assert <FlowResultType.CREATE_ENTRY: 'create_entry'> is <FlowResultType.ABORT: 'abort'>` |
| 10 | 262 | 140 | `AssertionError @ tests/<suite>: assert <FlowResultType.FORM: 'form'> is <FlowResultType.ABORT: 'abort'>` |
| 11 | 259 | 66 | `AssertionError @ tests/<suite>: assert 0 == 1` |
| 12 | 164 | 105 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'already_configured'` |
| 13 | 144 | 27 | `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'attributes'` |
| 14 | 108 | 19 | `IndexError @ tests/<suite>: list index out of range` |
| 15 | 108 | 2 | `TypeError @ tests/<suite>: 'NoneType' object is not callable` |
| 16 | 98 | 29 | `AssertionError @ tests/<suite>: assert None` |
| 17 | 97 | 49 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'no_devices_found'` |
| 18 | 97 | 8 | `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.MENU: 'menu'>` |
| 19 | 74 | 41 | `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>` |
| 20 | 66 | 30 | `AssertionError @ tests/<suite>: assert 'N.N.N.N' == 'N.N.N.N'` |
| 21 | 57 | 20 | `KeyError @ tests/<suite>: 'url'` |
| 22 | 56 | 13 | `KeyError @ tests/<suite>: 'step_id'` |
| 23 | 54 | 27 | `AssertionError @ tests/<suite>: assert False` |
| 24 | 54 | 19 | `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.EXTERNAL_STEP: 'external'>` |
| 25 | 52 | 11 | `Failed @ tests/<suite>: DID NOT RAISE <class 'EID.HomeAssistantError'>` |
| 26 | 48 | 30 | `AssertionError @ tests/<suite>: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.MIGRATION_ERROR: 'migration_error'>` |
| 27 | 45 | 22 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'cannot_connect'` |
| 28 | 41 | 26 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'not_supported'` |
| 29 | 39 | 6 | `AssertionError @ tests/<suite>: assert None == {}` |
| 30 | 37 | 9 | `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'unique_id'` |
| 31 | 35 | 6 | `KeyError @ /home/paulus/.local/share/uv/python/cpython-3.14.5-linux-x86_64-gnu/lib/python3.14/collections/__init__.py: 'EID'` |
| 32 | 34 | 1 | `AssertionError @ /home/paulus/.local/share/uv/python/cpython-3.14.5-linux-x86_64-gnu/lib/python3.14/unittest/mock.py: Expected 'action' to be called once. Calle` |
| 33 | 33 | 14 | `AssertionError @ /home/paulus/.local/share/uv/python/cpython-3.14.5-linux-x86_64-gnu/lib/python3.14/unittest/mock.py: expected call not found.` |
| 34 | 33 | 13 | `AssertionError @ tests/<suite>: assert 0 == 2` |
| 35 | 31 | 16 | `AssertionError @ tests/<suite>: assert <FlowResultType.FORM: 'form'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>` |
| 36 | 31 | 19 | `AssertionError @ tests/<suite>: assert None is not None` |
| 37 | 30 | 7 | `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'id'` |
| 38 | 29 | 6 | `TypeError @ tests/<suite>: 'NoneType' object is not subscriptable` |
| 39 | 27 | 13 | `TypeError @ homeassistant/components/sandbox/messages.py: bad argument type for built-in operation` |
| 40 | 25 | 12 | `AssertionError @ tests/<suite>: assert N == <HTTPStatus.OK: N>` |
| 41 | 24 | 7 | `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.SHOW_PROGRESS: 'progress'>` |
| 42 | 24 | 2 | `KeyError @ tests/<suite>: 'options'` |
| 43 | 22 | 12 | `AssertionError @ tests/<suite>: assert N == N` |
| 44 | 22 | 7 | `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'name'` |
| 45 | 21 | 1 | `HomeAssistantError @ homeassistant/components/sandbox/bridge.py: Device HEXID not found in the device registry` |
| 46 | 20 | 4 | `AssertionError @ tests/<suite>: assert 'test-password' == 'new-password'` |
| 47 | 20 | 1 | `AssertionError @ tests/<suite>: assert 0 == N` |
| 48 | 19 | 1 | `TypeError @ tests/<suite>: Unknown argument type: <class 'EID.Mock'>` |
| 49 | 19 | 1 | `AttributeError @ /home/paulus/.local/share/uv/python/cpython-3.14.5-linux-x86_64-gnu/lib/python3.14/unittest/mock.py: Mock object has no attribute 'get_instanta` |
| 50 | 18 | 9 | `AssertionError @ tests/<suite>: assert 2 == 1` |
| 51 | 17 | 1 | `AssertionError @ tests/<suite>: assert {}` |
| 52 | 16 | 8 | `AssertionError @ tests/<suite>: assert 1 == 2` |
| 53 | 16 | 7 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'invalid_discovery_info'` |
| 54 | 16 | 1 | `AssertionError @ tests/<suite>: assert None == [{'cron': '5 5 1 8 1', 'enabled': True, 'next_schedule': EID(N, 5, N, N, N, N, tzinfo=datetime.ti...5 1 8 2', 'en` |
| 55 | 15 | 11 | `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'unknown'` |
| 56 | 15 | 5 | `Failed @ tests/<suite>: DID NOT RAISE <class 'EID.ServiceValidationError'>` |
| 57 | 15 | 1 | `AttributeError @ homeassistant/components/lcn/helpers.py: 'MockConfigEntry' object has no attribute 'runtime_data'` |
| 58 | 14 | 1 | `AssertionError @ tests/<suite>: assert mappingproxy(...y_ssl': True}) == {'encryption'...EID', ...}` |
| 59 | 13 | 7 | `AssertionError @ tests/<suite>: assert 'off' == 'unknown'` |
| 60 | 13 | 3 | `AssertionError @ tests/<suite>: assert 'unknown' == 'N'` |

## Timeouts

accuweather, aemet, air_quality, automation, gardena_bluetooth, homeassistant, husqvarna_automower, ipma, metoffice, nordpool, nws, script, template, tomorrowio, tplink, trace, wemo, zwave_js

## Examples for top 25

### 1. `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.FORM: 'form'>` — 1040 failures / 172 integrations

Top integrations: shelly (56), improv_ble (33), samsungtv (33), fritz (29), elkm1 (28), matter (24), xiaomi_ble (18), yalexs_ble (17)

- `acaia tests/components/acaia/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.FORM: 'form'>`
- `acaia tests/components/acaia/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.FORM: 'form'>`
- `acaia tests/components/acaia/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.FORM: 'form'>`

### 2. `AssertionError @ tests/<suite>: assert [+ received] == [- snapshot]` — 822 failures / 218 integrations

Top integrations: deconz (64), vesync (49), renault (45), nibe_heatpump (22), homee (21), shelly (17), enphase_envoy (15), devolo_home_control (14)

- `actron_air tests/common.py: assert [+ received] == [- snapshot]`
- `actron_air tests/common.py: assert [+ received] == [- snapshot]`
- `adax tests/common.py: assert [+ received] == [- snapshot]`

### 3. `AssertionError @ tests/<suite>: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.LOADED: 'loaded'>` — 809 failures / 85 integrations

Top integrations: xbox (159), iron_os (84), switchbot_cloud (84), icloud (57), html5 (53), sleep_as_android (41), mastodon (35), matter (22)

- `aladdin_connect tests/components/aladdin_connect/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.LOADED: 'loaded'>`
- `aladdin_connect tests/components/aladdin_connect/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.LOADED: 'loaded'>`
- `aquacell tests/components/aquacell/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.LOADED: 'loaded'>`

### 4. `AssertionError @ tests/<suite>: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.SETUP_RETRY: 'setup_retry'>` — 788 failures / 333 integrations

Top integrations: peco (20), xbox (20), matter (19), sense (12), blebox (11), shelly (11), tessie (11), yeelight (11)

- `actron_air tests/components/actron_air/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.SETUP_RETRY: 'setup_retry'>`
- `adguard tests/components/adguard/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.SETUP_RETRY: 'setup_retry'>`
- `advantage_air tests/components/advantage_air/test_init.py: assert <ConfigEntryState.SETUP_ERROR: 'setup_error'> is <ConfigEntryState.SETUP_RETRY: 'setup_retry'>`

### 5. `ServiceNotFound @ homeassistant/core.py: Action EID not found` — 662 failures / 61 integrations

Top integrations: smartthings (124), gree (77), heos (39), samsungtv (34), telegram_bot (33), tesla_fleet (24), switchbot_cloud (21), lcn (19)

- `acaia homeassistant/core.py: Action button.press not found`
- `aladdin_connect homeassistant/core.py: Action cover.open_cover not found`
- `aladdin_connect homeassistant/core.py: Action cover.close_cover not found`

### 6. `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'state'` — 519 failures / 87 integrations

Top integrations: smartthings (93), switcher_kis (49), flux_led (30), satel_integra (25), blebox (21), bond (20), asuswrt (13), lifx (13)

- `airthings_ble tests/components/airthings_ble/test_init.py: 'NoneType' object has no attribute 'state'`
- `airthings_ble tests/components/airthings_ble/test_init.py: 'NoneType' object has no attribute 'state'`
- `airthings_ble tests/components/airthings_ble/test_init.py: 'NoneType' object has no attribute 'state'`

### 7. `AssertionError @ tests/<suite>: Regex pattern did not match.` — 377 failures / 71 integrations

Top integrations: habitica (40), heos (32), shelly (20), miele (15), mealie (14), peblar (14), wled (11), matter (10)

- `actron_air tests/components/actron_air/test_climate.py: Regex pattern did not match.`
- `actron_air tests/components/actron_air/test_climate.py: Regex pattern did not match.`
- `adguard tests/components/adguard/test_switch.py: Regex pattern did not match.`

### 8. `AttributeError @ tests/<suite>: 'MockConfigEntry' object has no attribute 'runtime_data'` — 332 failures / 50 integrations

Top integrations: homematicip_cloud (135), influxdb (56), rituals_perfume_genie (17), waterfurnace (16), lutron_caseta (11), switcher_kis (7), tessie (7), lg_thinq (5)

- `actron_air tests/components/actron_air/test_climate.py: 'MockConfigEntry' object has no attribute 'runtime_data'`
- `actron_air tests/components/actron_air/test_coordinator.py: 'MockConfigEntry' object has no attribute 'runtime_data'`
- `actron_air tests/components/actron_air/test_coordinator.py: 'MockConfigEntry' object has no attribute 'runtime_data'`

### 9. `AssertionError @ tests/<suite>: assert <FlowResultType.CREATE_ENTRY: 'create_entry'> is <FlowResultType.ABORT: 'abort'>` — 274 failures / 234 integrations

Top integrations: whirlpool (6), geniushub (3), minecraft_server (3), touchline (3), adax (2), apcupsd (2), cloudflare_r2 (2), daikin (2)

- `acmeda tests/components/acmeda/test_config_flow.py: assert <FlowResultType.CREATE_ENTRY: 'create_entry'> is <FlowResultType.ABORT: 'abort'>`
- `adax tests/components/adax/test_config_flow.py: assert <FlowResultType.CREATE_ENTRY: 'create_entry'> is <FlowResultType.ABORT: 'abort'>`
- `adax tests/components/adax/test_config_flow.py: assert <FlowResultType.CREATE_ENTRY: 'create_entry'> is <FlowResultType.ABORT: 'abort'>`

### 10. `AssertionError @ tests/<suite>: assert <FlowResultType.FORM: 'form'> is <FlowResultType.ABORT: 'abort'>` — 262 failures / 140 integrations

Top integrations: growatt_server (20), isy994 (8), heos (7), playstation_network (7), broadlink (5), unifi_access (5), rainmachine (4), vizio (4)

- `adguard tests/components/adguard/test_config_flow.py: assert <FlowResultType.FORM: 'form'> is <FlowResultType.ABORT: 'abort'>`
- `adguard tests/components/adguard/test_config_flow.py: assert <FlowResultType.FORM: 'form'> is <FlowResultType.ABORT: 'abort'>`
- `airnow tests/components/airnow/test_config_flow.py: assert <FlowResultType.FORM: 'form'> is <FlowResultType.ABORT: 'abort'>`

### 11. `AssertionError @ tests/<suite>: assert 0 == 1` — 259 failures / 66 integrations

Top integrations: rest (30), fritzbox (27), matter (22), bluetooth (21), samsungtv (19), hue (14), http (10), gree (9)

- `airnow tests/components/airnow/test_config_flow.py: assert 0 == 1`
- `airthings_ble tests/components/airthings_ble/test_init.py: assert 0 == 1`
- `androidtv_remote tests/components/androidtv_remote/test_config_flow.py: assert 0 == 1`

### 12. `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'already_configured'` — 164 failures / 105 integrations

Top integrations: flux_led (8), dlna_dmr (7), elkm1 (6), apple_tv (5), music_assistant (5), shelly (5), steamist (4), dlna_dms (3)

- `acaia tests/components/acaia/test_config_flow.py: assert 'sandbox_flow_error' == 'already_configured'`
- `adguard tests/components/adguard/test_config_flow.py: assert 'sandbox_flow_error' == 'already_configured'`
- `airgradient tests/components/airgradient/test_config_flow.py: assert 'sandbox_flow_error' == 'already_configured'`

### 13. `AttributeError @ tests/<suite>: 'NoneType' object has no attribute 'attributes'` — 144 failures / 27 integrations

Top integrations: smartthings (29), vizio (21), bond (14), cambridge_audio (9), blebox (7), hassio (7), here_travel_time (6), samsungtv (5)

- `androidtv tests/components/androidtv/test_media_player.py: 'NoneType' object has no attribute 'attributes'`
- `backup tests/components/backup/test_event.py: 'NoneType' object has no attribute 'attributes'`
- `backup tests/components/backup/test_event.py: 'NoneType' object has no attribute 'attributes'`

### 14. `IndexError @ tests/<suite>: list index out of range` — 108 failures / 19 integrations

Top integrations: shelly (24), dsmr (21), ps4 (21), hassio (7), husqvarna_automower_ble (7), otbr (5), broadlink (4), switchbot (4)

- `backup tests/components/backup/test_diagnostics.py: list index out of range`
- `backup tests/components/backup/test_event.py: list index out of range`
- `backup tests/components/backup/test_sensors.py: list index out of range`

### 15. `TypeError @ tests/<suite>: 'NoneType' object is not callable` — 108 failures / 2 integrations

Top integrations: shelly (65), togrill (43)

- `shelly tests/components/shelly/conftest.py: 'NoneType' object is not callable`
- `shelly tests/components/shelly/conftest.py: 'NoneType' object is not callable`
- `shelly tests/components/shelly/conftest.py: 'NoneType' object is not callable`

### 16. `AssertionError @ tests/<suite>: assert None` — 98 failures / 29 integrations

Top integrations: shelly (20), opnsense (11), withings (11), nibe_heatpump (8), bond (5), bang_olufsen (4), energyzero (4), flux_led (4)

- `bang_olufsen tests/components/bang_olufsen/test_event.py: assert None`
- `bang_olufsen tests/components/bang_olufsen/test_event.py: assert None`
- `bang_olufsen tests/components/bang_olufsen/test_event.py: assert None`

### 17. `AssertionError @ tests/<suite>: assert 'sandbox_flow_error' == 'no_devices_found'` — 97 failures / 49 integrations

Top integrations: airthings_ble (6), yalexs_ble (5), aranet (3), bthome (3), husqvarna_automower_ble (3), opendisplay (3), xiaomi_ble (3), bluemaestro (2)

- `acaia tests/components/acaia/test_config_flow.py: assert 'sandbox_flow_error' == 'no_devices_found'`
- `airthings_ble tests/components/airthings_ble/test_config_flow.py: assert 'sandbox_flow_error' == 'no_devices_found'`
- `airthings_ble tests/components/airthings_ble/test_config_flow.py: assert 'sandbox_flow_error' == 'no_devices_found'`

### 18. `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.MENU: 'menu'>` — 97 failures / 8 integrations

Top integrations: switchbot (28), plex (16), influxdb (13), onkyo (11), insteon (10), xiaomi_ble (9), lametric (5), velbus (5)

- `influxdb tests/components/influxdb/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.MENU: 'menu'>`
- `influxdb tests/components/influxdb/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.MENU: 'menu'>`
- `influxdb tests/components/influxdb/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.MENU: 'menu'>`

### 19. `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>` — 74 failures / 41 integrations

Top integrations: otbr (9), thread (7), samsungtv (5), bluetooth (4), elkm1 (4), enocean (3), dlna_dmr (2), hassio (2)

- `airgradient tests/components/airgradient/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>`
- `airq tests/components/airq/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>`
- `avea tests/components/avea/test_config_flow.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.CREATE_ENTRY: 'create_entry'>`

### 20. `AssertionError @ tests/<suite>: assert 'N.N.N.N' == 'N.N.N.N'` — 66 failures / 30 integrations

Top integrations: openrgb (7), plugwise (7), sma (5), airobot (4), nut (4), bosch_alarm (3), homee (3), nfandroidtv (3)

- `airobot tests/components/airobot/test_config_flow.py: assert '192.168.1.100' == '192.168.1.200'`
- `airobot tests/components/airobot/test_config_flow.py: assert '192.168.1.100' == '192.168.1.200'`
- `airobot tests/components/airobot/test_config_flow.py: assert '192.168.1.100' == '192.168.1.200'`

### 21. `KeyError @ tests/<suite>: 'url'` — 57 failures / 20 integrations

Top integrations: onedrive (9), google_drive (7), youtube (7), ekeybionyx (5), weheat (4), google_photos (3), google_sheets (3), onedrive_for_business (3)

- `aladdin_connect tests/components/aladdin_connect/test_config_flow.py: 'url'`
- `aladdin_connect tests/components/aladdin_connect/test_config_flow.py: 'url'`
- `dropbox tests/components/dropbox/test_config_flow.py: 'url'`

### 22. `KeyError @ tests/<suite>: 'step_id'` — 56 failures / 13 integrations

Top integrations: sftp_storage (11), telegram_bot (9), smappee (7), opendisplay (6), myuplink (5), devolo_home_network (3), github (3), senz (3)

- `devolo_home_network tests/components/devolo_home_network/test_config_flow.py: 'step_id'`
- `devolo_home_network tests/components/devolo_home_network/test_config_flow.py: 'step_id'`
- `devolo_home_network tests/components/devolo_home_network/test_config_flow.py: 'step_id'`

### 23. `AssertionError @ tests/<suite>: assert False` — 54 failures / 27 integrations

Top integrations: prowl (6), swiss_public_transport (5), androidtv_remote (4), onedrive (4), webostv (4), hassio (3), huawei_lte (3), pyload (3)

- `androidtv_remote tests/components/androidtv_remote/test_init.py: assert False`
- `androidtv_remote tests/components/androidtv_remote/test_init.py: assert False`
- `androidtv_remote tests/components/androidtv_remote/test_media_player.py: assert False`

### 24. `AssertionError @ tests/<suite>: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.EXTERNAL_STEP: 'external'>` — 54 failures / 19 integrations

Top integrations: energyid (10), fitbit (9), microbees (5), tibber (5), application_credentials (4), smartthings (3), withings (3), geocaching (2)

- `application_credentials tests/components/application_credentials/test_init.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.EXTERNAL_STEP: 'external'>`
- `application_credentials tests/components/application_credentials/test_init.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.EXTERNAL_STEP: 'external'>`
- `application_credentials tests/components/application_credentials/test_init.py: assert <FlowResultType.ABORT: 'abort'> is <FlowResultType.EXTERNAL_STEP: 'external'>`

### 25. `Failed @ tests/<suite>: DID NOT RAISE <class 'EID.HomeAssistantError'>` — 52 failures / 11 integrations

Top integrations: fritzbox (15), bond (11), ntfy (10), openevse (5), whirlpool (3), litterrobot (2), openrgb (2), google_mail (1)

- `bond tests/components/bond/test_fan.py: DID NOT RAISE <class 'homeassistant.exceptions.HomeAssistantError'>`
- `bond tests/components/bond/test_light.py: DID NOT RAISE <class 'homeassistant.exceptions.HomeAssistantError'>`
- `bond tests/components/bond/test_light.py: DID NOT RAISE <class 'homeassistant.exceptions.HomeAssistantError'>`

