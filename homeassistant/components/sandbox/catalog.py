"""Picker catalog hook for sandbox-only custom integrations.

A custom (HACS) integration that runs in a stateless sandbox has its code
fetched at ``entry_setup`` and never lands under ``<config>/custom_components``
on the main install. The add-integration picker is built from an on-disk scan
(``loader.async_get_integration_descriptions``), so such an integration has no
picker row and no display name — a discoverability gap, of which ``title`` is a
subset.

This module is the sandbox-namespaced face of the catalog hook, parallel to the
:mod:`~homeassistant.components.sandbox.sources` source resolver: HACS — or any
distribution mechanism — registers a provider that *enumerates* the custom
integrations it knows about, and core merges those descriptors into the picker
and the ``title`` fallback. The hook itself lives in
:mod:`homeassistant.loader` because core (not the sandbox component) consumes it;
this re-export keeps HACS's registration surface in one place.

Contract (decision (a), display-only):

* Deliberately **separate** from the source resolver. The resolver is lazy,
  per-domain and security-critical (it pins ``ref`` to an exact commit sha); the
  catalog is eager, enumerable and purely cosmetic. Fusing them would drag
  display strings through the sha-validation path.
* ``name`` is the load-bearing field — it feeds both the picker row and the
  ``title`` fallback. ``title_translations`` is **optional**: HACS may not have
  the un-fetched tarball's ``translations/`` indexed, and absent it the picker
  degrades to ``name``.
* A wrong or missing ``name`` is cosmetic, so — unlike ``ref`` — core does **no**
  validation of catalog descriptors.
"""

from homeassistant.loader import (
    SandboxCatalogProvider,
    SandboxIntegrationDescriptor,
    async_register_sandbox_catalog_provider,
)

__all__ = [
    "SandboxCatalogProvider",
    "SandboxIntegrationDescriptor",
    "async_register_sandbox_catalog_provider",
]
