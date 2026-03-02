# Create `config.yaml` For Config Flows

## Goal
Document the persisted config entry and subentry payloads in each integration's `config.yaml` under `config_entry`, using selector-based field metadata that is consistent with Home Assistant selectors.

The output must describe what is **actually stored** in config entries (`data`, `options`, and `subentries`), not just what is shown in forms.

## Required Files Per Integration
For each integration with `"config_flow": true` in `manifest.json`, inspect:

1. `config_flow.py`
2. `__init__.py` (for migration and runtime usage confirmation)
3. `const.py` (for `CONF_*`, version constants, and aliases)
4. `strings.json` / translations only as fallback for field names not inferable from code
5. Existing `config.yaml` (target file)

## Version Rules
1. Default version is `major: 1`, `minor: 1` when no explicit version is defined.
2. Read `VERSION` and `MINOR_VERSION` from the config flow class.
3. If the class uses constants (for example `CONFIG_FLOW_VERSION`), resolve them from `const.py`.
4. Document all known config-entry versions when code clearly supports multiple versions:
   - Current version from config flow class.
   - Historical versions from explicit migration branches (for example `async_migrate_entry` checks in `__init__.py`).
5. Apply the same version logic to subentries (default `1.1` when unspecified).

## Storage Target Rules (Critical)
Always determine where values are persisted:

1. `ConfigFlow.async_create_entry(data=...)` -> persisted in config entry `data`.
2. `ConfigFlow.async_create_entry(..., options=...)` -> persisted in config entry `options`.
3. `OptionsFlow.async_create_entry(data=...)` -> persisted in config entry `options`.
4. `SchemaConfigFlowHandler` (default implementation):
   - Config flow values are stored in `options`.
   - Config entry `data` is empty.
   - Exception: class overrides `async_create_entry` (then follow override).
5. `async_update_reload_and_abort(..., data=..., options=...)` updates existing entry payloads and must align with documented fields.

## Form-To-Storage Mapping Rules
When `user_input` is stored directly, form schema must be mirrored in `config.yaml`.

### Config Flow
If step logic returns `async_create_entry(data=user_input)`:
1. Find the matching `async_show_form(..., data_schema=...)` for that step.
2. Extract all schema keys.
3. Add those keys to `config_entry.versions[*].data.fields`.

### Options Flow
If options step returns `async_create_entry(data=user_input)`:
1. Extract step schema keys.
2. Add those keys to `config_entry.versions[*].options.fields`.

### Dict Payloads
If `async_create_entry(data={...})` (or via a local dict variable/function that clearly returns a dict):
1. Extract literal keys.
2. Add keys to the relevant persisted section (`data` or `options`).

## Helper Flow Rules
### `register_discovery_flow(...)`
Creates entry with `data={}` by default. Keep data empty unless integration overrides flow behavior elsewhere.

### `register_webhook_flow(...)`
Creates entry with:
1. `webhook_id`
2. `cloudhook`

These must be documented in `config_entry.versions[*].data.fields`.

### `AbstractOAuth2FlowHandler`
Default OAuth payload includes:
1. `auth_implementation`
2. `token`

If integration overrides `async_oauth_create_entry` and adds additional stored keys, include those too.

## Subentry Rules
1. Find `async_get_supported_subentry_types(...)` mapping and subentry flow classes (`ConfigSubentryFlow`).
2. For each `subentry_type`, document under:
   - `config_entry.subentries.<subentry_type>.versions`
3. Extract persisted subentry payload keys from:
   - `async_create_entry(data=...)` in subentry flow
   - direct subentry update calls with explicit data payloads
4. Apply required/default/selector extraction exactly as for main config/option flows.

## Field Metadata Rules
Each field entry should include:
1. `required` (true/false)
2. `selector` (valid HA selector structure)
3. Optional `default` and `example` when directly known from code

### Required Flag
1. `vol.Required(...)` -> `required: true`
2. `vol.Optional(...)` -> `required: false`
3. Literal dict payloads without schema context -> `required: true` unless clearly optional in code path

### Selector Mapping
Use explicit selector calls when present (for example `TextSelector`, `NumberSelector`, `BooleanSelector`, `LocationSelector`, `SelectSelector`, etc).

If schema uses plain validators:
1. `bool` / `cv.boolean` -> `selector: { boolean: {} }`
2. numeric validators -> `selector: { number: {} }`
3. `vol.In(...)` / constrained choices -> `selector: { select: {} }`
4. unknown / string-like -> `selector: { text: {} }`
5. structured blobs (for example OAuth `token`) -> `selector: { object: {} }`

## Validation Checklist (Per Integration)
1. `config.yaml` exists when `manifest.json` has `config_flow: true`.
2. `config_entry.versions` contains correct version entries.
3. Documented fields exactly match persisted payloads (`data` vs `options`).
4. `required` and selector format are valid.
5. `subentries` are documented when supported.
6. No placeholder empty blocks where code stores actual fields.

## Final QA Commands
Run after updates:

```bash
python -m script.hassfest -p config_entry --action validate
ruff check script/hassfest/config_entry.py
```

## High-Risk Pitfalls
1. Assuming fields in forms are always stored in `data` (wrong for `SchemaConfigFlowHandler`).
2. Missing fields when `data=user_input` is used with a non-empty schema.
3. Skipping helper flows (`register_webhook_flow`, OAuth2 base handler behavior).
4. Ignoring options/subentry flows that store separate payloads.
5. Using placeholders instead of integration-specific field definitions.
