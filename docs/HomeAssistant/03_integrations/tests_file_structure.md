---
title: "Integration tests file structure"
sidebar_label: "Tests file structure"
---

Tests for each integration are stored inside a directory named after the integration domain. For example, tests for the mobile app integration should be stored in `tests/components/mobile_app`.

The content of this folder looks like this:

- `__init__.py`: Required for `pytest` to find the tests, you can keep this file limited to a docstring introducing the integration tests `"""Tests for the Mobile App integration."""`.
- `conftest.py`: Pytest test fixtures
- `test_xxx.py`: Tests testing a corresponding part of the integration. Tests of functionality in `__init__.py`, for example setting up, reloading and unloading a config entry, should be in a file named `test_init.py`.

## Sharing test fixtures with other integrations

If your integration is an entity integration which other integrations have platforms with, for example `light` or `sensor`, the integration can provide test fixtures which can be used when writing tests for other integrations.

For example, the `light` integration may provide fixtures for creating mocked light entities by adding fixture stubs to `tests/components/conftest.py`, and the actual implementation of the fixtures in `tests/components/light/common.py`.
