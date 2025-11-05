"""Tests for Apple TV."""

import sys

import pytest

if sys.version_info < (3, 14):
    # Make asserts in the common module display differences
    pytest.register_assert_rewrite("tests.components.apple_tv.common")
