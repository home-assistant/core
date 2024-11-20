"""Fixtures for testing Awair integration."""

import json

import pytest

from tests.common import load_fixture


@pytest.fixture(name="cloud_devices", scope="package")
def cloud_devices_fixture():
    """Fixture representing devices returned by Awair Cloud API."""
    return json.loads(load_fixture("awair/cloud_devices.json"))


@pytest.fixture(name="local_devices", scope="package")
def local_devices_fixture():
    """Fixture representing devices returned by Awair local API."""
    return json.loads(load_fixture("awair/local_devices.json"))


@pytest.fixture(name="gen1_data", scope="package")
def gen1_data_fixture():
    """Fixture representing data returned from Gen1 Awair device."""
    return json.loads(load_fixture("awair/awair.json"))


@pytest.fixture(name="gen2_data", scope="package")
def gen2_data_fixture():
    """Fixture representing data returned from Gen2 Awair device."""
    return json.loads(load_fixture("awair/awair-r2.json"))


@pytest.fixture(name="glow_data", scope="package")
def glow_data_fixture():
    """Fixture representing data returned from Awair glow device."""
    return json.loads(load_fixture("awair/glow.json"))


@pytest.fixture(name="mint_data", scope="package")
def mint_data_fixture():
    """Fixture representing data returned from Awair mint device."""
    return json.loads(load_fixture("awair/mint.json"))


@pytest.fixture(name="no_devices", scope="package")
def no_devicess_fixture():
    """Fixture representing when no devices are found in Awair's cloud API."""
    return json.loads(load_fixture("awair/no_devices.json"))


@pytest.fixture(name="awair_offline", scope="package")
def awair_offline_fixture():
    """Fixture representing when Awair devices are offline."""
    return json.loads(load_fixture("awair/awair-offline.json"))


@pytest.fixture(name="omni_data", scope="package")
def omni_data_fixture():
    """Fixture representing data returned from Awair omni device."""
    return json.loads(load_fixture("awair/omni.json"))


@pytest.fixture(name="user", scope="package")
def user_fixture():
    """Fixture representing the User object returned from Awair's Cloud API."""
    return json.loads(load_fixture("awair/user.json"))


@pytest.fixture(name="local_data", scope="package")
def local_data_fixture():
    """Fixture representing data returned from Awair local device."""
    return json.loads(load_fixture("awair/awair-local.json"))
