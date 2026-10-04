"""Vendored Electra API client (upstream ``pyElectra``).

The ``pyElectra`` library this integration depended on is effectively
unmaintained, and the pinned 1.2.4 release crashes setup on some devices
(``KeyError: 'deviceToken'``). This package is a vendored, Home Assistant
style-conformant port of a client (Apache-2.0) kept inside the integration so
the fixes can ship without waiting on an upstream release. See ``NOTICE.md``.
"""
