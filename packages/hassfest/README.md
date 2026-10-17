# Hassfest

Hassfest checks Home Assistant integration manifests, translations, services,
discovery declarations, and other integration metadata.

This package is under development and is not ready for external consumption or
publication yet. The existing
[home-assistant/actions/hassfest](https://github.com/home-assistant/actions/tree/master/hassfest)
action remains the supported way to check custom integrations.

## Intended standalone usage

```sh
pip install hassfest
hassfest --integration-path /path/to/custom_components/my_integration
```

`python -m hassfest` provides the same command. Repeat `--integration-path` to
check multiple integrations. `--plugins` and `--skip-plugins` select checks;
`--requirements` enables the existing dependency installation and inspection
checks. Standalone runs require an integration path and cannot generate Core
files. There is no automatic integration discovery in this command; the existing
Docker entry point retains its discovery behavior.

Each build uses Core's version and requires exactly that Home Assistant version.
Installing Hassfest therefore installs Home Assistant and its dependencies.
Development builds require the matching Home Assistant development build, which
may not be published on PyPI.

The distribution includes snapshots of Core's `requirements.txt` and
`requirements_all.txt`. Other reference data, including package constraints,
built-in integrations, and integration category strings, comes from the installed
Home Assistant package. An explicit `--core-path` uses that checkout's reference
data and requirements instead. It does not replace the imported Home Assistant
code; use a matching Python environment when supplying a checkout.

## Working in Core

Continue to run `python -m script.hassfest` from the Core repository. That entry
point selects the packaged integration validators alongside Core's local plugins,
uses current checkout data, and preserves the existing validate/generate behavior.
The script bootstrap and test configuration expose the package source directly.
No package installation or requirements snapshot is needed for Core development.

The runner accepts an ordered sequence of modules with `validate(integrations,
config)` and optional `generate(integrations, config)` functions. Core controls
which local modules it supplies. There is no installed-plugin discovery mechanism.
Some integration validators retain their Core generation functions to keep this
extraction focused; the standalone CLI never runs generation.

## Building

From the Core checkout:

```sh
uv build packages/hassfest
```

The build captures Core's version, minimum Python version, and requirements files.
An sdist contains that snapshot and can build a wheel outside the checkout.
Generated build data is ignored by Git. This change adds no publishing workflow.
