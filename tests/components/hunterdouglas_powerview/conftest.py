"""Tests for the Hunter Douglas PowerView integration."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture
def mock_powerview_v2_hub():
    """Mock a Powerview v2 hub."""
    userdata = json.loads(load_fixture("hunterdouglas_powerview/userdata.json"))
    fwversion = json.loads(load_fixture("hunterdouglas_powerview/fwversion.json"))
    scenes = json.loads(load_fixture("hunterdouglas_powerview/scenes.json"))

    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData.get_resources",
        return_value=userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Rooms.get_resources",
        return_value={"roomData": []},
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Scenes.get_resources",
        return_value=scenes,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.Shades.get_resources",
        return_value={"shadeData": []},
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.ApiEntryPoint",
        return_value=fwversion,
    ):
        yield
