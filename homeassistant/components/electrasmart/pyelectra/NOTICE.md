# Vendored code: pyElectra

This directory contains a vendored, Home Assistant style-conformant port of the
[`pyElectra`](https://github.com/jafar-atili/pyElectra) API client, which is
licensed under the Apache License 2.0 (license text:
https://github.com/jafar-atili/pyElectra/blob/master/LICENSE).

## Why it is vendored

Home Assistant pinned `pyElectra==1.2.4`. The library is effectively
unmaintained (last release 2024) and that release crashes setup for devices
whose `GET_DEVICES` response omits the `deviceToken` field:

```
KeyError: 'deviceToken'
```

An upstream fix exists ([pyElectra#20](https://github.com/jafar-atili/pyElectra/pull/20))
but has gone unmerged, so this integration vendors the client and applies the
fix locally so affected users are unblocked.

## Divergences from upstream (pyElectra 1.2.4 / master)

- `device/__init__.py`: `deviceToken` is read with `.get("deviceToken", "")`
  instead of a hard dict access. The token is a dead attribute (not used
  anywhere downstream), so this is safe. Fixes the upstream crash in
  `fetch_devices()` for units that don't receive a `deviceToken`.
- Style-only: the port conforms to Home Assistant's ruff configuration
  (module docstrings, no `from __future__ import annotations`, `list` instead
  of `typing.List`, ≤88 column lines). No other behaviour is changed.

## Syncing

To update, port the relevant changes from upstream `src/electrasmart/` into
the matching files here and re-apply the `deviceToken` divergence above. If
upstream ever ships a fixed release, prefer dropping this vendored copy and
restoring a `requirements` entry instead.