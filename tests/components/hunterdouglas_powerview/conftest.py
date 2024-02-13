"""Tests for the Hunter Douglas PowerView integration."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture(scope="session")
def powerview_userdata():
    """Return the userdata fixture."""
    return json.loads(load_fixture("hunterdouglas_powerview/userdata.json"))


@pytest.fixture(scope="session")
def powerview_fwversion():
    """Return the fwversion fixture."""
    return json.loads(load_fixture("hunterdouglas_powerview/fwversion.json"))


@pytest.fixture(scope="session")
def powerview_scenes():
    """Return the scenes fixture."""
    return json.loads(load_fixture("hunterdouglas_powerview/scenes.json"))


@pytest.fixture
def mock_powerview_v2_hub(powerview_userdata, powerview_fwversion, powerview_scenes):
    """Mock a Powerview v2 hub."""
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData.get_resources",
        return_value=powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Rooms.get_resources",
        return_value={"roomData": []},
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Scenes.get_resources",
        return_value=powerview_scenes,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Shades.get_resources",
        return_value={"shadeData": []},
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.ApiEntryPoint",
        return_value=powerview_fwversion,
    ):
        yield
