# Pylint plugin for Home Assistant

Custom [pylint](https://www.pylint.org/) checkers for the Home Assistant
codebase. These checkers enforce coding standards, quality scale compliance,
and common review patterns specific to Home Assistant integrations.

This plugin extends pylint with checks that cannot be expressed as
[Ruff](https://docs.astral.sh/ruff/) rules because they require type
inference, cross-file analysis (reading `manifest.json`, `quality_scale.yaml`),
or AST patterns that go beyond what a linter operating on a single file
can detect.

# Setup

This plugin is designed for internal use by Home Assistant Core's CI/CD
pipeline. It is not intended for external use, such as linting custom
integration repositories.

Plugins are loaded via the `load-plugins` setting in `pyproject.toml`.
The `init-hook` adds `pylint/plugins` to `sys.path` so these modules
are importable.


# Why not (just) Ruff?

Home Assistant uses both [Ruff](https://docs.astral.sh/ruff/) and pylint.
Ruff handles fast, single-file linting (import sorting, formatting, common
Python issues). These pylint checkers cover patterns that Ruff cannot:

- **Cross-file analysis**: reading `manifest.json` to check
  `integration_type`, reading `quality_scale.yaml` to verify claims.
- **Type inference**: resolving decorator names like
  `_pytest.fixtures.FixtureFunctionMarker` through imports.
- **Complex AST patterns**: tracing variable assignments to API calls
  (e.g., detecting that a variable assigned from `data[CONF_HOST]` later
  flows into `async_set_unique_id()`).


# Disabling checks

Always use the rule name (e.g., `hass-logger-period`) rather than the
error code (e.g., `W7401`) for readability.

**Single line** -- add the disable comment at the end of the line:

```python
hass.data[DOMAIN] = data  # pylint: disable=hass-use-runtime-data
```

**Next line only** -- if the inline comment would make the line too long,
use `disable-next` on the line above:

```python
# pylint: disable-next=hass-use-runtime-data
hass.data[DOMAIN] = data
```

**Entire module** -- place the disable comment at the top of the file,
after the module docstring:

```python
"""My integration setup."""
# pylint: disable=hass-use-runtime-data
```


# Automated code analysis

Every check has a code following the
[pylint convention](https://github.com/pylint-dev/pylint/blob/v3.1.0/pylint/checkers/__init__.py#L5-L41):

- `{C,W,E,R}74{00-99}`, where `74` is the base ID for Home Assistant.
- `C` = Convention, `W` = Warning, `E` = Error, `R` = Refactor.

| Code | Rule | Description |
|------|------|-------------|
| `W7401` | [`hass-logger-period`](#w7401-hass-logger-period) | Logger messages must not end with a period |
| `W7402` | [`hass-logger-capital`](#w7402-hass-logger-capital) | Logger messages must start with a capital letter |
| `W7411` | [`hass-invalid-inheritance`](#w7411-hass-invalid-inheritance) | Invalid entity class inheritance chain |
| `W7421` | [`hass-relative-import`](#w7421-hass-relative-import) | Use relative imports within an integration |
| `W7422` | [`hass-deprecated-import`](#w7422-hass-deprecated-import) | Import uses a deprecated path |
| `W7423` | [`hass-absolute-import`](#w7423-hass-absolute-import) | Use absolute imports for cross-integration references |
| `W7424` | [`hass-component-root-import`](#w7424-hass-component-root-import) | Do not import from another integration's internals |
| `W7425` | [`hass-helper-namespace-import`](#w7425-hass-helper-namespace-import) | Use the helper namespace import pattern |
| `W7426` | [`hass-import-constant-alias`](#w7426-hass-import-constant-alias) | Aliased DOMAIN import needs a descriptive alias |
| `W7427` | [`hass-import-constant-unnecessary-alias`](#w7427-hass-import-constant-unnecessary-alias) | Unnecessary alias for DOMAIN import |
| `W7431` | [`hass-argument-type`](#w7431-hass-argument-type) | Function argument should have the specified type hint |
| `W7432` | [`hass-return-type`](#w7432-hass-return-type) | Function should have the specified return type hint |
| `W7433` | [`hass-consider-usefixtures-decorator`](#w7433-hass-consider-usefixtures-decorator) | Use `@pytest.mark.usefixtures` for unused fixtures |
| `W7441` | [`hass-missing-super-call`](#w7441-hass-missing-super-call) | Method must call its parent via `super()` |
| `W7451` | [`hass-enforce-sorted-platforms`](#w7451-hass-enforce-sorted-platforms) | PLATFORMS list must be sorted alphabetically |
| `W7452` | [`hass-enforce-greek-micro-char`](#w7452-hass-enforce-greek-micro-char) | Use Greek mu (U+03BC), not ANSI micro sign (U+00B5) |
| `C7461` | [`hass-enforce-class-module`](#c7461-hass-enforce-class-module) | Entity class should be in the correct platform module |
| `W7471` | [`hass-async-callback-decorator`](#w7471-hass-async-callback-decorator) | Coroutine should not be decorated with `@callback` |
| `W7472` | [`hass-pytest-fixture-decorator`](#w7472-hass-pytest-fixture-decorator) | Pytest fixture has invalid scope or autouse config |
| `W7481` | [`hass-async-load-fixtures`](#w7481-hass-async-load-fixtures) | Test fixture files should be loaded asynchronously |
| `W7482` | [`hass-use-runtime-data`](#w7482-hass-use-runtime-data) | Use `entry.runtime_data` instead of `hass.data[DOMAIN]` |
| `W7491` | [`hass-unique-id-ip-based`](#w7491-hass-unique-id-ip-based) | Unique ID should not be based on IP/hostname |
| `W7492` | [`hass-config-flow-polling-field`](#w7492-hass-config-flow-polling-field) | Config flow should not include polling interval fields |


## `hass_logger` checker

Enforces consistent formatting of logger messages across the codebase.


### `W7401`: `hass-logger-period`

User-visible logger messages must not end with a period. Log messages in
Home Assistant follow a convention of not using trailing punctuation.


### `W7402`: `hass-logger-capital`

Logger messages must start with a capital letter. This ensures consistency
across all integrations.


## `hass_imports` checker

Enforces import conventions for Home Assistant integrations. Integrations
should use relative imports for their own modules and follow specific
patterns for cross-integration references.


### `W7421`: `hass-relative-import`

Use relative imports within an integration (e.g., `from .const import DOMAIN`
instead of `from homeassistant.components.myintegration.const import DOMAIN`).

### `W7422`: `hass-deprecated-import`

Import uses a deprecated path that has been moved or renamed.

### `W7423`: `hass-absolute-import`

Use absolute imports when referencing modules outside the current integration.

### `W7424`: `hass-component-root-import`

Do not import from another integration's internal modules. Only import from
the integration's top-level public API.

### `W7425`: `hass-helper-namespace-import`

Use the helper namespace import pattern for helper modules.

### `W7426`: `hass-import-constant-alias`

Aliased `DOMAIN` import from another integration should use a descriptive alias.

### `W7427`: `hass-import-constant-unnecessary-alias`

Unnecessary alias for `DOMAIN` import -- the alias matches the original name.


## `hass_enforce_type_hints` checker

Enforces type hints on platform functions, config flow methods, and test
functions. Checks both argument types and return types against the expected
signatures defined by Home Assistant's platform interfaces.


### `W7431`: `hass-argument-type`

Function argument should have the specified type hint. Platform functions
like `async_setup_entry` have well-defined signatures that must be followed.

### `W7432`: `hass-return-type`

Function should have the specified return type hint.

### `W7433`: `hass-consider-usefixtures-decorator`

Test function should use `@pytest.mark.usefixtures("fixture_name")` instead
of accepting an unused fixture as a parameter.


## `hass_decorator` checker

Validates decorator usage on functions and fixtures.


### `W7471`: `hass-async-callback-decorator`

A coroutine function (`async def`) should not be decorated with `@callback`.
The `@callback` decorator is only for synchronous functions that should be
called from the event loop without scheduling.

### `W7472`: `hass-pytest-fixture-decorator`

Pytest fixture has invalid scope or autouse configuration. For example,
`session`-scoped fixtures in component tests should use `package` scope
or lower.


## `hass_inheritance` checker

Validates entity class inheritance chains.

### `W7411`: `hass-invalid-inheritance`

Entity class has an invalid inheritance chain. Entity classes must properly
inherit from the correct base classes for their platform.


## `hass_enforce_super_call` checker

Ensures methods call their parent implementation when required.

### `W7441`: `hass-missing-super-call`

Method must call its parent implementation via `super()`. Certain entity
methods require calling the parent to maintain correct behavior.


## `hass_enforce_sorted_platforms` checker

Ensures platform lists are maintained in alphabetical order.

### `W7451`: `hass-enforce-sorted-platforms`

The `PLATFORMS` (or `_PLATFORMS`) list must be sorted alphabetically. This
makes it easier to review and prevents merge conflicts.


## `hass_enforce_greek_micro_char` checker

Ensures correct Unicode character for the micro prefix.

### `W7452`: `hass-enforce-greek-micro-char`

Constants with a micro unit prefix (e.g., `"μg/m³"`) must use the Greek
small letter mu (U+03BC `μ`), not the ANSI micro sign (U+00B5 `µ`). The
two characters look identical but are different Unicode code points.


## `hass_enforce_class_module` checker

Ensures entity classes are placed in the correct module.

### `C7461`: `hass-enforce-class-module`

A class deriving from a platform entity (e.g., `SensorEntity`) should be
placed in the corresponding platform module (e.g., `sensor.py`), not in
`__init__.py` or an unrelated module.


## `hass_enforce_runtime_data` checker

Enforces the modern `entry.runtime_data` pattern over the legacy
`hass.data[DOMAIN]` dictionary pattern. Only flags integrations that
have a config flow (YAML-only integrations are skipped).

### `W7482`: `hass-use-runtime-data`

Use `entry.runtime_data` instead of `hass.data[DOMAIN]`. The `runtime_data`
approach is type-safe (via `ConfigEntry[T]`), automatically cleaned up on
entry unload, and avoids key collisions in the shared `hass.data` dictionary.

See the [runtime-data quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data)
for migration guidance.


## `hass_async_load_fixtures` checker

Ensures test fixture files are loaded asynchronously.

### `W7481`: `hass-async-load-fixtures`

Test fixture files should be loaded using async I/O, not synchronous
file reads. This prevents blocking the event loop during tests.


## `hass_enforce_config_entry_unique_id_no_ip` checker

Detects `async_set_unique_id` calls where the argument is an IP address
or hostname. IP addresses change when devices get new DHCP leases, breaking
the config entry. Uses variable tracking to catch indirect usage (e.g.,
`uid = data[CONF_HOST]; await self.async_set_unique_id(uid)`).

### `W7491`: `hass-unique-id-ip-based`

`async_set_unique_id` should not use an IP address or hostname. Use a
stable hardware identifier instead: a MAC address (via `format_mac`),
serial number, or device-provided unique ID.

See the [unique-config-entry quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry).


## `hass_enforce_config_flow_no_polling` checker

Detects polling interval fields in config flow schemas. Polling intervals
should be fixed by the integration author, not exposed as user-configurable
fields.

### `W7492`: `hass-config-flow-polling-field`

Config flow should not include polling interval fields like
`CONF_SCAN_INTERVAL`, `update_interval`, or `refresh_interval`. The
integration author determines the appropriate polling frequency based on
API rate limits, device capabilities, and data freshness needs.

See the [appropriate-polling quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling).

