# Hassfest Core scripts

These scripts work with the [hassfest package](../../packages/hassfest/AGENTS.md).
The package owns the shared runner, integration validation that applies to both
Core and custom integrations, and custom-integration-specific validation.

This directory is intended for Core-only validators and generators. Its entry
point selects plugins and invokes the package's runner, combining shared checks
with Core-specific checks and generation.

The split is still in progress. Mixed validators remain here until their shared
or custom-integration logic can move into the package, leaving Core-only policy
and generation here. Core may import the package; the package must not import
these scripts.
