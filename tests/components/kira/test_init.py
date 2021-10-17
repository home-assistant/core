"""The tests for Kira."""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

import homeassistant.components.kira as kira
from homeassistant.setup import async_setup_component

TEST_CONFIG = {
    kira.DOMAIN: {
        "sensors": [
            {"name": "test_sensor", "host": "127.0.0.1", "port": 34293},
            {"name": "second_sensor", "port": 29847},
        ],
        "remotes": [
            {"host": "127.0.0.1", "port": 34293},
            {"name": "one_more", "host": "127.0.0.1", "port": 29847},
        ],
    }
}

KIRA_CODES = """
- name: test
  code: "K 00FF"
- invalid: not_a_real_code
"""


@pytest.fixture(autouse=True)
def setup_comp():
    """Set up things to be run when tests are started."""
    with patch("homeassistant.components.kira.pykira.KiraReceiver"):
        yield


@pytest.fixture(scope="module")
def work_dir():
    """Set up temporary workdir."""
    work_dir = tempfile.mkdtemp()
    yield work_dir
    shutil.rmtree(work_dir, ignore_errors=True)


async def test_kira_empty_config(hass):
    """Kira component should load a default sensor."""
    await async_setup_component(hass, kira.DOMAIN, {kira.DOMAIN: {}})
    assert len(hass.data[kira.DOMAIN]["sensor"]) == 1


async def test_kira_setup(hass):
    """Ensure platforms are loaded correctly."""
    await async_setup_component(hass, kira.DOMAIN, TEST_CONFIG)
    assert len(hass.data[kira.DOMAIN]["sensor"]) == 2
    assert sorted(hass.data[kira.DOMAIN]["sensor"].keys()) == [
        "kira",
        "kira_1",
    ]
    assert len(hass.data[kira.DOMAIN]["remote"]) == 2
    assert sorted(hass.data[kira.DOMAIN]["remote"].keys()) == [
        "kira",
        "kira_1",
    ]


async def test_kira_creates_codes(work_dir):
    """Kira module should create codes file if missing."""
    code_path = os.path.join(work_dir, "codes.yaml")
    kira.load_codes(code_path)
    assert os.path.exists(code_path), "Kira component didn't create codes file"


async def test_load_codes(work_dir):
    """Kira should ignore invalid codes."""
    code_path = os.path.join(work_dir, "codes.yaml")
    with open(code_path, "w") as code_file:
        code_file.write(KIRA_CODES)
    res = kira.load_codes(code_path)
    assert len(res) == 1, "Expected exactly 1 valid Kira code"
