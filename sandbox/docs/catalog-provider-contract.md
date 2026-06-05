# Catalog provider — picker discoverability for sandbox-only customs

> **Current design (2026-06-05, plan-translation-forwarding Phase A).** Core
> exposes a **display-only** catalog hook so a custom integration whose code
> lives only in a sandbox — never on main's `<config>/custom_components` disk —
> can be listed and named in the add-integration picker **without spawning a
> sandbox**. HACS (or any distribution mechanism) fills it. The hook is
> deliberately separate from the security-critical integration-source resolver.

## The gap

The add-integration picker is built from `integration/descriptions`
(`async_get_integration_descriptions`, `homeassistant/loader.py`), whose custom
half is a scan of `<config>/custom_components` on **main's** disk. Under the
stateless-sandbox model a custom integration's code is fetched at `entry_setup`
into the sandbox and is **never on main's disk**, so:

- it has **no picker row** (the disk scan never sees it), and
- even if a row existed, the `title` translation category has nothing to load —
  the `integration.name` fallback in
  `_async_get_component_strings` (`homeassistant/helpers/translation.py`) needs a
  loaded `Integration`, which main cannot build for code it doesn't have.

This is a **discoverability** gap, of which `title` is a subset. Closing it
needs only a tiny static descriptor per domain — not a sandbox spawn (the picker
never loads `config`/`selector`, only `title`; those load per-flow once the user
starts adding the integration, where the Phase B live RPC handles them).

## The hook

```python
from homeassistant.components.sandbox.catalog import (
    SandboxIntegrationDescriptor,
    async_register_sandbox_catalog_provider,
)

def _catalog() -> list[SandboxIntegrationDescriptor]:
    return [
        {
            "domain": "my_custom",
            "name": "My Custom Integration",   # load-bearing
            "config_flow": True,
            "integration_type": "integration",  # or "helper"
            "iot_class": "cloud_polling",
            "single_config_entry": False,
            # optional; absent -> picker degrades to `name`
            "title_translations": {"en": "My Custom Integration"},
        }
    ]

unregister = async_register_sandbox_catalog_provider(hass, _catalog)
```

`async_register_sandbox_catalog_provider` is re-exported from the sandbox
component (parallel to `async_register_sandbox_source_resolver` in
`sandbox/sources.py`) for a single HACS-facing namespace; the registry itself
lives in `homeassistant.loader` because core — not the sandbox component —
consumes it (`async_get_integration_descriptions` and the translation `title`
fallback). Providers are consulted in registration order; the first to claim a
domain wins. The returned callback unregisters.

## Contract

- **Separate from the source resolver.** The source resolver
  (`IntegrationSourceDict`, `sandbox/sources.py`) is lazy, per-domain, and
  **security-critical**: it pins `ref` to an exact commit sha and core does no
  network I/O, so it trusts that pin. The catalog is **eager, enumerable, and
  cosmetic**. Fusing them would drag display strings through the sha-validation
  path and force the security-critical resolver to also be a full listing API.

- **`name` is load-bearing.** It feeds both the picker row
  (`integration.name || domainToName(...)` in the frontend) and the `title`
  fallback. A descriptor without a usable `name` falls back to a prettified
  domain — acceptable, but worse UX.

- **`title_translations` is optional.** HACS reliably knows the manifest `name`
  (it parses `manifest.json` to validate installs) but may **not** have the
  integration's `translations/<lang>.json` indexed — those live in the repo
  tarball, fetched only at `entry_setup`. When `title_translations[lang]` is
  absent the picker degrades to `name` (the same fallback chain main already
  uses). A localized title is a nice-to-have, not a requirement.

- **No validation.** Unlike `ref` (sha-pinned, security-critical), a wrong or
  missing `name` is cosmetic, so core does **no** strict validation of catalog
  descriptors. A domain that an on-disk scan also finds keeps the on-disk
  metadata — the disk scan wins a collision.

- **Display-only scope.** The catalog carries picker metadata, nothing more. It
  is intentionally **not** the broader "stateless-custom discovery" feature
  (config-flow allow-listing, schema, etc.); those remain out of scope.

## Relationship to the live path (Phase B)

Phase B already forwards a *running* sandboxed integration's strings over the
`sandbox/get_translations` RPC, routed by `entry.sandbox` / the in-progress
`SandboxFlowProxy`. The catalog covers the **cold** picker case where there is
no entry and no running flow — so no group to route to — and the live RPC would
return nothing. The two are complementary: catalog for the cold list + name,
RPC for everything once a flow starts or an entry is loaded.
