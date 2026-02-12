"""Fixtures for IntelliClima integration tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaECO,
    IntelliClimaModelType,
)
import pytest

from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.intellifire.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "SuperUser",
            CONF_PASSWORD: "hunter2",
        },
    )


@pytest.fixture
def single_eco_device() -> IntelliClimaDevices:
    """Create IntelliClimaDevices with one ECOCOMFORT 2.0 and no C800."""
    eco = IntelliClimaECO(
        id="56789",
        crono_sn="11223344",
        status="OK",
        online="OK",
        command="OK",
        model=IntelliClimaModelType(modello="ECO", tipo="wifi"),
        name="Test VMC",
        houses_id="12345",
        mode_set="1",
        mode_state="1",
        speed_set="3",
        speed_state="3",
        last_online="2025-11-18 10:22:51",
        creation_date="2025-11-18 10:22:51",
        fw="0.6.8",
        mac="00:11:22:33:44:55",
        macwifi="00:11:22:33:44:55",
        conn_num="1",
        conn_state="0",
        role="1",
        rh_thrs="2",
        lux_thrs="1",
        voc_thrs="1",
        slv_rot="0",
        slv_addr="00:11:22:33:44:55",
        offset_temp="0",
        offset_hum="0",
        year="25",
        month="11",
        day="10",
        dow="0",
        hour="22",
        minute="41",
        second="35",
        dst="1",
        mode_prev="4",
        dir_state="2",
        auto_cycle="194",
        tamb="16.2",
        rh="65",
        voc_state="89",
        plun="",
        pmar="",
        pmer="",
        pgio="",
        pven="",
        psab="",
        pdom="",
        pcustom=None,
        sfondo="img/backgrounds/shutterstock_2.jpg0",
        tperc=None,
        fcool="0",
        ws="1",
        filter_from="2025-11-18 10:22:51",
        filter_active="1",
        timezone=None,
        co2=None,
        sanification=None,
        rssi=None,
        aqi=None,
        co2_thrs=None,
        dev_state=None,
        online_status=True,
        online_status_debug="mock",
    )

    return IntelliClimaDevices(ecocomfort2_devices={eco.id: eco}, c800_devices={})


@pytest.fixture
def mock_cloud_interface(single_eco_device) -> Generator[AsyncMock]:
    """Mock IntelliClimaAPI for tests."""

    with (
        patch(
            "homeassistant.components.intelliclima.IntelliClimaAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.intelliclima.config_flow.IntelliClimaAPI",
            new=mock_client,
        ),
    ):
        # Mock async context manager
        mock_client = mock_client.return_value

        # Mock other async methods if needed
        mock_client.authenticate.return_value = True
        mock_client.get_all_device_status.return_value = single_eco_device

        # Sub-API used by the fan entity
        mock_client.ecocomfort = SimpleNamespace(
            turn_off=AsyncMock(return_value=True),
            set_mode_speed=AsyncMock(return_value=True),
            set_mode_speed_auto=AsyncMock(return_value=True),
        )

        mock_client.auth_token = "fake-token"
        mock_client.user_id = "fake-user-id"
        mock_client.house_id = "fake-house-id"
        yield mock_client  # Yielding to the test
