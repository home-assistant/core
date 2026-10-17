# Hassfest

Hassfest checks Home Assistant integration manifests, translations, services,
discovery declarations, and other integration metadata.

This package is under development and is not ready for external consumption or
publication yet. The existing
[home-assistant/actions/hassfest](https://github.com/home-assistant/actions/tree/master/hassfest)
action remains the supported way to check custom integrations.

The package currently contains the shared runner, models, utilities, and JSON and
code-owner validators. Validators that mix shared checks with Core policies or
file generation remain in Core until those responsibilities are separated.
There is no standalone command yet.

Each build uses Core's version and requires exactly that Home Assistant version.
Development builds require the matching Home Assistant development build, which
may not be published on PyPI.

## Building

From the Core checkout:

```sh
uv build packages/hassfest
```

The build captures Core's version, minimum Python version, and requirements files.
An sdist contains that snapshot and can build a wheel outside the checkout.
Generated build data is ignored by Git. This change adds no publishing workflow.
