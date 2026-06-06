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

Always use the rule name (e.g., `home-assistant-logger-period`) rather than the
error code (e.g., `C7401`) for readability.

**Single line** -- add the disable comment at the end of the line:

```python
hass.data[DOMAIN] = data  # pylint: disable=home-assistant-use-runtime-data
```

**Next line only** -- if the inline comment would make the line too long,
use `disable-next` on the line above:

```python
# pylint: disable-next=home-assistant-use-runtime-data
hass.data[DOMAIN] = data
```

**Entire module** -- place the disable comment at the top of the file,
after the module docstring:

```python
"""My integration setup."""
# pylint: disable=home-assistant-use-runtime-data
```

# Automated code analysis

Every check has a code following the
[pylint convention](https://pylint.readthedocs.io/en/stable/development_guide/how_tos/custom_checkers.html):

- `{C,W,E,R}74{00-99}`, where `74` is the base ID for Home Assistant.
- `C` = Convention, `W` = Warning, `E` = Error, `R` = Refactor.

| Code | Rule | Description |
|------|------|-------------|
| `C7401` | [`home-assistant-logger-period`](#c7401-home-assistant-logger-period) | Logger messages must not end with a period |
| `C7402` | [`home-assistant-logger-capital`](#c7402-home-assistant-logger-capital) | Logger messages must start with a capital letter or use debug level |
| `E7401` | [`home-assistant-invalid-inheritance`](#e7401-home-assistant-invalid-inheritance) | Invalid entity class inheritance chain |
| `C7403` | [`home-assistant-relative-import`](#c7403-home-assistant-relative-import) | Use relative imports within an integration |
| `W7401` | [`home-assistant-deprecated-import`](#w7401-home-assistant-deprecated-import) | Import uses a deprecated path |
| `C7404` | [`home-assistant-absolute-import`](#c7404-home-assistant-absolute-import) | Use absolute imports for cross-integration references |
| `C7405` | [`home-assistant-component-root-import`](#c7405-home-assistant-component-root-import) | Do not import from another integration's internals |
| `C7406` | [`home-assistant-helper-namespace-import`](#c7406-home-assistant-helper-namespace-import) | Use the helper namespace import pattern |
| `C7407` | [`home-assistant-import-constant-alias`](#c7407-home-assistant-import-constant-alias) | Aliased DOMAIN import needs a descriptive alias |
| `C7408` | [`home-assistant-import-constant-unnecessary-alias`](#c7408-home-assistant-import-constant-unnecessary-alias) | Unnecessary alias when importing DOMAIN within the same integration |
| `E7402` | [`home-assistant-argument-type`](#e7402-home-assistant-argument-type) | Function argument should have the specified type hint |
| `E7403` | [`home-assistant-return-type`](#e7403-home-assistant-return-type) | Function should have the specified return type hint |
| `R7401` | [`home-assistant-consider-usefixtures-decorator`](#r7401-home-assistant-consider-usefixtures-decorator) | Use `@pytest.mark.usefixtures` for unused fixtures |
| `E7404` | [`home-assistant-missing-super-call`](#e7404-home-assistant-missing-super-call) | Method must call its parent via `super()` |
| `C7409` | [`home-assistant-enforce-sorted-platforms`](#c7409-home-assistant-enforce-sorted-platforms) | PLATFORMS list must be sorted alphabetically |
| `C7410` | [`home-assistant-enforce-greek-micro-char`](#c7410-home-assistant-enforce-greek-micro-char) | Use Greek mu (U+03BC), not ANSI micro sign (U+00B5) |
| `C7411` | [`home-assistant-enforce-class-module`](#c7411-home-assistant-enforce-class-module) | Entity class should be in the correct platform module |
| `W7402` | [`home-assistant-async-callback-decorator`](#w7402-home-assistant-async-callback-decorator) | Coroutine should not be decorated with `@callback` |
| `W7403` | [`home-assistant-pytest-fixture-decorator`](#w7403-home-assistant-pytest-fixture-decorator) | Pytest fixture has invalid scope or autouse config |
| `W7404` | [`home-assistant-async-load-fixtures`](#w7404-home-assistant-async-load-fixtures) | Test fixture files should be loaded asynchronously |
| `W7405` | [`home-assistant-use-runtime-data`](#w7405-home-assistant-use-runtime-data) | Use `entry.runtime_data` instead of `hass.data[DOMAIN]` |
| `W7406` | [`home-assistant-unique-id-ip-based`](#w7406-home-assistant-unique-id-ip-based) | Unique ID should not be based on IP/hostname |
| `W7407` | [`home-assistant-config-flow-polling-field`](#w7407-home-assistant-config-flow-polling-field) | Config flow should not include polling interval fields |
| `W7408` | [`home-assistant-config-flow-name-field`](#w7408-home-assistant-config-flow-name-field) | Config flow should not include name fields |
| `R7402` | [`home-assistant-unused-test-fixture-argument`](#r7402-home-assistant-unused-test-fixture-argument) | Unused test function argument should use `@pytest.mark.usefixtures` |
| `C7415` | [`home-assistant-domain-argument`](#c7415-home-assistant-domain-argument) | Domain argument in tests should be a domain constant or variable |
| `W7418` | [`home-assistant-tests-direct-async-setup-entry`](#w7418-home-assistant-tests-direct-async-setup-entry) | Tests should not call an integration's `async_setup_entry` directly |
| `W7420` | [`home-assistant-tests-direct-platform-async-setup-entry`](#w7420-home-assistant-tests-direct-platform-async-setup-entry) | Tests should not call a platform's `async_setup_entry` directly |
| `W7421` | [`home-assistant-tests-direct-async-migrate-entry`](#w7421-home-assistant-tests-direct-async-migrate-entry) | Tests should not call an integration's `async_migrate_entry` directly |
| `W7422` | [`home-assistant-tests-direct-async-setup`](#w7422-home-assistant-tests-direct-async-setup) | Tests should not call an integration's `async_setup` directly |
| `C7414` | [`home-assistant-enforce-utcnow`](#c7414-home-assistant-enforce-utcnow) | Use `homeassistant.util.dt.utcnow` instead of `datetime.now(UTC)` |
| `W7423` | [`home-assistant-missing-entity-unique-id`](#w7423-home-assistant-missing-entity-unique-id) | Entity class does not statically guarantee a non-None unique id |
| `W7424` | [`home-assistant-entity-unique-id-static`](#w7424-home-assistant-entity-unique-id-static) | Entity class sets `_attr_unique_id` to a static string at class level |
| `C7412` | [`home-assistant-entity-description-redundant-default`](#c7412-home-assistant-entity-description-redundant-default) | Setting an EntityDescription field to its default value is redundant |
| `C7413` | [`home-assistant-duplicate-const`](#c7413-home-assistant-duplicate-const) | Constant duplicates one in `homeassistant.const` with the same value |
| `E7405` | [`home-assistant-action-swallowed-exception`](#e7405-home-assistant-action-swallowed-exception) | Action handler must not swallow exceptions |
| `W7414` | [`home-assistant-service-registered-in-setup-entry`](#w7414-home-assistant-service-registered-in-setup-entry) | Services should be registered in `async_setup`, not `async_setup_entry` |
| `W7417` | [`home-assistant-exception-not-translated`](#w7417-home-assistant-exception-not-translated) | `HomeAssistantError` should use `translation_key`/`translation_domain` |
| `W7419` | [`home-assistant-exception-message-with-translation`](#w7419-home-assistant-exception-message-with-translation) | Don't pass a positional message when `translation_key` is set |
| `E7406` | [`home-assistant-exception-translation-key-missing`](#e7406-home-assistant-exception-translation-key-missing) | Translation key not found in `strings.json` exceptions section |
| `E7408` | [`home-assistant-exception-translation-key-domain-mismatch`](#e7408-home-assistant-exception-translation-key-domain-mismatch) | Only one of `translation_key` / `translation_domain` is set |
| `E7418` | [`home-assistant-exception-placeholder-mismatch`](#e7418-home-assistant-exception-placeholder-mismatch) | Translation placeholders in code don't match `strings.json` |
| `E7409` | [`home-assistant-mdi-icon-not-found`](#e7409-home-assistant-mdi-icon-not-found) | MDI icon string does not exist in the Material Design Icons set |
| `E7410` | [`home-assistant-mdi-icon-json-not-found`](#e7410-home-assistant-mdi-icon-json-not-found) | MDI icon in `icons.json` does not exist in the Material Design Icons set |
| `R7403` | [`home-assistant-tests-redundant-usefixtures`](#r7403-home-assistant-tests-redundant-usefixtures) | `@pytest.mark.usefixtures` redundant when `pytestmark` already applies it |
| `W7409` | [`home-assistant-test-non-deterministic`](#w7409-home-assistant-test-non-deterministic) | Test contains `if`/`match` creating non-deterministic execution |
| `W7410` | [`home-assistant-missing-reauthentication-flow`](#w7410-home-assistant-missing-reauthentication-flow) | Config flow should implement `async_step_reauth` |
| `W7411` | [`home-assistant-missing-parallel-updates`](#w7411-home-assistant-missing-parallel-updates) | Platform module should define `PARALLEL_UPDATES` |
| `W7412` | [`home-assistant-missing-diagnostics`](#w7412-home-assistant-missing-diagnostics) | Integration diagnostics module should implement a diagnostics function |
| `W7413` | [`home-assistant-missing-config-entry-unloading`](#w7413-home-assistant-missing-config-entry-unloading) | Integration should implement `async_unload_entry` |
| `W7415` | [`home-assistant-sequential-executor-jobs`](#w7415-home-assistant-sequential-executor-jobs) | Sequential `async_add_executor_job` calls should be grouped |
| `W7416` | [`home-assistant-missing-has-entity-name`](#w7416-home-assistant-missing-has-entity-name) | Entity class should set `_attr_has_entity_name = True` |


## `home_assistant_logger` checker

Enforces consistent formatting of logger messages across the codebase.


### `C7401`: `home-assistant-logger-period`

User-visible logger messages must not end with a period. Log messages in
Home Assistant follow a convention of not using trailing punctuation.


### `C7402`: `home-assistant-logger-capital`

Logger messages must start with a capital letter. Debug-level messages
are exempt from this rule. If a message does not warrant capitalization,
consider downgrading it to debug level.


## `home_assistant_imports` checker

Enforces import conventions for Home Assistant integrations. Integrations
should use relative imports for their own modules and follow specific
patterns for cross-integration references.


### `C7403`: `home-assistant-relative-import`

Use relative imports within an integration (e.g., `from .const import DOMAIN`
instead of `from homeassistant.components.myintegration.const import DOMAIN`).

### `W7401`: `home-assistant-deprecated-import`

Import uses a deprecated path that has been moved or renamed.

### `C7404`: `home-assistant-absolute-import`

Use absolute imports when referencing modules outside the current integration.

### `C7405`: `home-assistant-component-root-import`

Do not import from another integration's internal modules. Only import from
the integration's top-level public API.

### `C7406`: `home-assistant-helper-namespace-import`

Use the helper namespace import pattern for helper modules.

### `C7407`: `home-assistant-import-constant-alias`

Aliased `DOMAIN` import from another integration should use a descriptive alias.

### `C7408`: `home-assistant-import-constant-unnecessary-alias`

Unnecessary alias when importing `DOMAIN` from within the same integration.


## `home_assistant_enforce_type_hints` checker

Enforces type hints on platform functions, config flow methods, and test
functions. Checks both argument types and return types against the expected
signatures defined by Home Assistant's platform interfaces.


### `E7402`: `home-assistant-argument-type`

Function argument should have the specified type hint. Platform functions
like `async_setup_entry` have well-defined signatures that must be followed.

### `E7403`: `home-assistant-return-type`

Function should have the specified return type hint.

### `R7401`: `home-assistant-consider-usefixtures-decorator`

Test function should use `@pytest.mark.usefixtures("fixture_name")` instead
of accepting an unused fixture as a parameter.


## `home_assistant_decorator` checker

Validates decorator usage on functions and fixtures.


### `W7402`: `home-assistant-async-callback-decorator`

A coroutine function (`async def`) should not be decorated with `@callback`.
The `@callback` decorator is only for synchronous functions that should be
called from the event loop without scheduling.

### `W7403`: `home-assistant-pytest-fixture-decorator`

Pytest fixture has invalid scope or autouse configuration. For example,
`session`-scoped fixtures in component tests should use `package` scope
or lower.


## `home_assistant_inheritance` checker

Validates that entity platform modules only use entity classes from their
own platform (e.g., a `sensor.py` module should not inherit from
`BinarySensorEntity`).

### `E7401`: `home-assistant-invalid-inheritance`

A platform module uses an entity class from a different platform. For
example, a `sensor.py` file should not define classes inheriting from
`BinarySensorEntity`.


## `home_assistant_enforce_super_call` checker

Ensures methods call their parent implementation when required.

### `E7404`: `home-assistant-missing-super-call`

Method must call its parent implementation via `super()`. Certain entity
methods require calling the parent to maintain correct behavior.


## `home_assistant_enforce_sorted_platforms` checker

Ensures platform lists are maintained in alphabetical order.

### `C7409`: `home-assistant-enforce-sorted-platforms`

The `PLATFORMS` (or `_PLATFORMS`) list must be sorted alphabetically. This
makes it easier to review and prevents merge conflicts.


## `home_assistant_enforce_greek_micro_char` checker

Ensures correct Unicode character for the micro prefix.

### `C7410`: `home-assistant-enforce-greek-micro-char`

Constants with a micro unit prefix (e.g., `"μg/m³"`) must use the Greek
small letter mu (U+03BC `μ`), not the ANSI micro sign (U+00B5 `µ`). The
two characters look identical but are different Unicode code points.


## `home_assistant_enforce_class_module` checker

Ensures entity classes are placed in the correct module.

### `C7411`: `home-assistant-enforce-class-module`

A class deriving from a platform entity (e.g., `SensorEntity`) should be
placed in the corresponding platform module (e.g., `sensor.py`), not in
`__init__.py` or an unrelated module.


## `home_assistant_enforce_runtime_data` checker

Enforces the modern `entry.runtime_data` pattern over the legacy
`hass.data[DOMAIN]` dictionary pattern. Only flags integrations that
have a config flow (YAML-only integrations are skipped).

### `W7405`: `home-assistant-use-runtime-data`

Use `entry.runtime_data` instead of `hass.data[DOMAIN]`. The `runtime_data`
approach is type-safe (via `ConfigEntry[T]`), automatically cleaned up on
entry unload, and avoids key collisions in the shared `hass.data` dictionary.

See the [runtime-data quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data)
for migration guidance.


## `home_assistant_async_load_fixtures` checker

Ensures test fixture files are loaded asynchronously.

### `W7404`: `home-assistant-async-load-fixtures`

Test fixture files should be loaded using async I/O, not synchronous
file reads. This prevents blocking the event loop during tests.


## `home_assistant_enforce_config_entry_unique_id_no_ip` checker

Detects `async_set_unique_id` calls where the argument is an IP address
or hostname. IP addresses change when devices get new DHCP leases, breaking
the config entry. Uses variable tracking to catch indirect usage (e.g.,
`uid = data[CONF_HOST]; await self.async_set_unique_id(uid)`).

### `W7406`: `home-assistant-unique-id-ip-based`

`async_set_unique_id` should not use an IP address or hostname. Use a
stable hardware identifier instead: a MAC address (via `format_mac`),
serial number, or device-provided unique ID.

See the [unique-config-entry quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry).


## `home_assistant_enforce_config_flow_no_polling` checker

Detects polling interval fields in config flow schemas. Polling intervals
should be fixed by the integration author, not exposed as user-configurable
fields.

### `W7407`: `home-assistant-config-flow-polling-field`

Config flow should not include polling interval fields like
`CONF_SCAN_INTERVAL`, `update_interval`, or `refresh_interval`. The
integration author determines the appropriate polling frequency based on
API rate limits, device capabilities, and data freshness needs.

See the [appropriate-polling quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling).

## `home_assistant_enforce_config_flow_no_name` checker

Detects name fields (`CONF_NAME`, `"name"`, `CONF_DEVICE_NAME`,
`"device_name"`) in config flow schemas. Config flows should not ask
users to provide a name -- the name is automatically derived from the
device (via discovery) or set by the integration code itself.

Helper integrations (`integration_type: helper` in `manifest.json`) and
subentry flows (`ConfigSubentryFlow` subclasses) are excluded.

### `W7408`: `home-assistant-config-flow-name-field`

Config flow should not include a name field. Users should not set names
in config flows; they come automatically from the device or are set by
the integration.


## `home_assistant_unused_test_fixture_args` checker

**Disabled by default** while existing violations are being cleaned up.


### `R7402`: `home-assistant-unused-test-fixture-argument`

Test functions that receive a fixture argument but never reference it in
the function body should use `@pytest.mark.usefixtures("name")` instead.
This keeps the function signature clean and makes it clear the fixture is
only needed for its side effects.

This rule only applies to `test_*` functions, not to fixture functions.


## `home_assistant_domain_constant` checker

Encourages using `DOMAIN` constants (or variables) when passing a domain to common test helpers.
String literals are allowed for cases where the constant is not imported.
Only runs on test modules.

### `C7415`: `home-assistant-domain-argument`

The domain (or handler) argument to test helpers such as
`async_setup_component`, `async_mock_service`, `MockConfigEntry`,
`hass.services.async_call`, `hass.services.call`, and
`hass.config_entries.flow.async_init` should use a domain constant or variable when available.
The following are accepted:

* a `DOMAIN`/`domain` attribute or one ending in `_DOMAIN`/`_domain`
  (e.g. `sensor.DOMAIN`),
* a `DOMAIN`/`domain` name or one ending in `_DOMAIN`/`_domain`,
* a string literal (for cases where the constant is not imported),
* a subscript expression (e.g. `data["key"]`).


## `home_assistant_tests_direct_async_setup_entry` checker

Detects tests that call an integration's `async_setup_entry` directly.

### `W7418`: `home-assistant-tests-direct-async-setup-entry`

Tests should not invoke an integration's `async_setup_entry` from
`__init__.py` directly. Instead, tests should let Home Assistant perform
the setup via `await hass.config_entries.async_setup(entry.entry_id)` so
that the real setup pipeline (platforms, services, listeners, unload
handlers, etc.) is exercised.

### `W7420`: `home-assistant-tests-direct-platform-async-setup-entry`

Same as `W7418`, but for an entity platform's `async_setup_entry` (e.g.
`homeassistant.components.<integration>.sensor.async_setup_entry`).
Tests should drive setup through `hass.config_entries.async_setup` so
the platform is loaded via the normal Home Assistant flow.

See [epic #77](https://github.com/home-assistant/epics/issues/77).


## `home_assistant_tests_direct_async_migrate_entry` checker

Detects tests that call an integration's `async_migrate_entry` directly.

### `W7421`: `home-assistant-tests-direct-async-migrate-entry`

Tests should not invoke an integration's `async_migrate_entry` from
`__init__.py` directly. Instead, tests should let Home Assistant perform
the setup via `await hass.config_entries.async_setup(entry.entry_id)` so
that the real migration pipeline (version bumps, reloads, post-migration
setup, etc.) is exercised.

See [epic #78](https://github.com/home-assistant/epics/issues/78).


## `home_assistant_tests_direct_async_setup` checker

Detects tests that call an integration's `async_setup` directly.

### `W7422`: `home-assistant-tests-direct-async-setup`

Tests should not invoke an integration's `async_setup` from
`__init__.py` directly. Instead, tests should let Home Assistant drive
the setup through the normal pipeline:

* For integrations with config entries, add a `MockConfigEntry` and
  call `await hass.config_entries.async_setup(entry.entry_id)`.
* For integrations without config entries (system integrations), use
  `await async_setup_component(hass, DOMAIN, {...})` from
  `homeassistant.setup`.

See [epic #79](https://github.com/home-assistant/epics/issues/79).


## `home_assistant_enforce_utcnow` checker

Ensures the Home Assistant helper is used to get the current UTC time.

### `C7414`: `home-assistant-enforce-utcnow`

Use `homeassistant.util.dt.utcnow()` instead of `datetime.datetime.now(UTC)`.
The helper is implemented as
`functools.partial(datetime.datetime.now, UTC)` and avoids the global
lookup of `UTC` on every call, while keeping the codebase consistent in
how the current UTC time is obtained.


## `home_assistant_entity_unique_id` checker

Quality-scale-gated checker for the [`entity-unique-id`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id)
Bronze rule. Only fires for entity-platform modules whose
`quality_scale.yaml` marks `entity-unique-id` as `done`.

### `W7423`: `home-assistant-missing-entity-unique-id`

Entity class does not statically guarantee a non-`None` unique id.
Accepted (in the class or any ancestor):

1. Class body: `_attr_unique_id = <non-None value>`.
2. A method body where every successful path executes
   `self._attr_unique_id = <expr>` (top-level, or in both branches of an
   `if/else`). An early-return guard (`if cond: return`) before the
   assignment breaks the guarantee and is rejected; an
   `if cond: raise ...` guard is accepted since no object is constructed
   when the exception fires.
3. A `unique_id` property/method override on the class.

A subclass that explicitly assigns `_attr_unique_id = None` overrides
any non-`None` value set by an ancestor and is flagged regardless of
what the ancestors do.

Mixin/abstract bases that are subclassed by another class in the same
module are exempted. Use
`# pylint: disable=home-assistant-missing-entity-unique-id` on the
class declaration as the escape hatch for dynamic patterns the static
analysis cannot follow.

### `W7424`: `home-assistant-entity-unique-id-static`

Entity class sets `_attr_unique_id` to a literal string at class body.
Entity unique IDs are scoped per `(domain, platform)` across **all**
config entries of the integration, so a static value collides on the
second config entry of a multi-entry integration.

The rule fires when:

- the class body assigns `_attr_unique_id = "..."` (or
  `_attr_unique_id: str = "..."`) to a literal string, and
- the integration's `manifest.json` does not declare
  `single_config_entry: true`.

Resolve by either computing the id per instance (config-entry id,
serial, MAC, etc.) or declaring the integration as
`single_config_entry: true` when there is genuinely only one instance.

## `home_assistant_entity_description_defaults` checker

Detects fields in `EntityDescription` (and subclasses) that are explicitly
set to their default value.

### `C7412`: `home-assistant-entity-description-redundant-default`

An EntityDescription field is set equal to a default already declared
anywhere in the class hierarchy; the assignment can be removed. Only the
literal defaults `None`, `True`, and `False` are checked; other default
values are not flagged.


## `home_assistant_duplicate_const` checker

Detects constants in integration modules that duplicate one already exported
from `homeassistant.const` with the same value.

### `C7413`: `home-assistant-duplicate-const`

Import the constant from `homeassistant.const` instead of redefining it.


## `home_assistant_actions_swallowed_exceptions` checker

Detects action handlers that catch exceptions without re-raising. Swallowed
exceptions are not surfaced to the user.

### `E7405`: `home-assistant-action-swallowed-exception`

Action handlers must re-raise so the user is notified of the failure.
The checker detects empty `except` blocks, blocks that only log,
`contextlib.suppress(...)`, and equivalent patterns on decorators. It does
not validate the *type* of exception being raised; a separate rule covers
that.


## `home_assistant_actions_service_registration` checker

Detects services registered inside `async_setup_entry` rather than
`async_setup`.

### `W7414`: `home-assistant-service-registered-in-setup-entry`

Services should be registered in `async_setup` so they are available for
automation validation even when no config entry is loaded. Registrations
inside helper functions that are called from `async_setup_entry` are
caught too.

See the [action-setup quality scale rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup).


## `home_assistant_exception_translations` checker

Ensures `HomeAssistantError` and its subclasses use the translation system
(`translation_domain`, `translation_key`) instead of hardcoded English
strings. Also verifies that referenced translation keys exist in the
integration's `strings.json` and that placeholders match.

### `W7417`: `home-assistant-exception-not-translated`

A `HomeAssistantError` subclass is raised with a hardcoded message; use
`translation_domain` and `translation_key` instead. Quality-scale-gated.

### `W7419`: `home-assistant-exception-message-with-translation`

Don't pass a positional message argument when `translation_key` is also set;
the translation system supplies the message.

### `E7406`: `home-assistant-exception-translation-key-missing`

The translation key referenced from code is missing from `strings.json`
under the `exceptions` section.

### `E7408`: `home-assistant-exception-translation-key-domain-mismatch`

Both `translation_key` and `translation_domain` must be set together; only
one of the two was provided.

### `E7418`: `home-assistant-exception-placeholder-mismatch`

The placeholders passed in code (e.g. `translation_placeholders={...}`)
don't match the `{placeholder}` slots in the `strings.json` message.


## `home_assistant_mdi_icons` checker

Validates that `mdi:` icon references in code and `icons.json` refer to
icons that actually exist in the Material Design Icons set.

### `E7409`: `home-assistant-mdi-icon-not-found`

MDI icon reference in Python code does not exist in the Material Design
Icons set.

### `E7410`: `home-assistant-mdi-icon-json-not-found`

MDI icon reference in `icons.json` does not exist in the Material Design
Icons set.


## `home_assistant_tests_redundant_usefixtures` checker

Detects `@pytest.mark.usefixtures(...)` decorators that duplicate a fixture
already applied module-wide, either through a module-level `pytestmark`
or via `autouse=True` on a fixture defined in a parent `conftest.py`.

### `R7403`: `home-assistant-tests-redundant-usefixtures`

Drop the redundant `@pytest.mark.usefixtures` decorator; the fixture is
already applied to every test in the module.


## `home_assistant_test_determinism` checker

`if` and `match` statements inside test functions create non-deterministic
execution paths: some branches may never run, silently hiding failures.

### `W7409`: `home-assistant-test-non-deterministic`

Test function contains an `if` or `match` statement. Use
`@pytest.mark.parametrize` to cover cases explicitly, or split into separate
test functions. `if` statements have several exemptions: guard clauses
(`return`/`raise`/`pytest.skip`/`pytest.xfail`/`pytest.fail`),
conditions that reference a function parameter, and branches that contain
no `assert`. `match` statements have no exemptions.


## `home_assistant_reauthentication_flow` checker

Quality-scale-gated checker for the
[`reauthentication-flow`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow)
Silver rule. Fires only when the integration claims the rule as `done`.

### `W7410`: `home-assistant-missing-reauthentication-flow`

Integration's `config_flow.py` should implement `async_step_reauth`.


## `home_assistant_parallel_updates` checker

Quality-scale-gated checker for the
[`parallel-updates`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates)
Silver rule. Fires only when the integration claims the rule as `done`.

### `W7411`: `home-assistant-missing-parallel-updates`

Platform module should define a module-level `PARALLEL_UPDATES` constant.


## `home_assistant_diagnostics` checker

Quality-scale-gated checker for the
[`diagnostics`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics)
Gold rule. Fires only when the integration claims the rule as `done`.

### `W7412`: `home-assistant-missing-diagnostics`

Integration's `diagnostics.py` should implement
`async_get_config_entry_diagnostics` or `async_get_device_diagnostics`.


## `home_assistant_config_entry_unloading` checker

Quality-scale-gated checker for the
[`config-entry-unloading`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading)
Silver rule. Fires only when the integration claims the rule as `done`.

### `W7413`: `home-assistant-missing-config-entry-unloading`

Integration's `__init__.py` should implement `async_unload_entry`.


## `home_assistant_sequential_executor_jobs` checker

Detects consecutive `async_add_executor_job` calls in integration modules
that could be grouped into a single executor job.

### `W7415`: `home-assistant-sequential-executor-jobs`

Two or more `async_add_executor_job` calls appearing as consecutive
statements (uninterrupted by control flow such as `if`/`try`/`with`/`for`)
should be combined into a single executor job that performs all the work,
avoiding unnecessary context switches back to the event loop between
blocking calls. The rule applies to integration modules only.


## `home_assistant_has_entity_name` checker

Quality-scale-gated checker for the
[`has-entity-name`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name)
Bronze rule. Fires only when the integration claims the rule as `done`.

### `W7416`: `home-assistant-missing-has-entity-name`

Entity class should statically guarantee `_attr_has_entity_name = True`:
either set at class level, set unconditionally at the top of a method, or
supplied by an `entity_description` whose class sets `has_entity_name = True`.
Conditional patterns are rejected.
