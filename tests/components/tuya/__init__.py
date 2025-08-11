"""Tests for the Tuya component."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import DeviceListener, ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_MOCKS = {
    "cl_zah67ekd": [
        # https://github.com/home-assistant/core/issues/71242
        Platform.COVER,
        Platform.SELECT,
    ],
    "clkg_nhyj64w2": [
        # https://github.com/home-assistant/core/issues/136055
        Platform.COVER,
        Platform.LIGHT,
    ],
    "co2bj_yrr3eiyiacm31ski": [
        # https://github.com/home-assistant/core/issues/133173
        Platform.BINARY_SENSOR,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SIREN,
    ],
    "cs_ka2wfrdoogpvgzfi": [
        # https://github.com/home-assistant/core/issues/119865
        Platform.BINARY_SENSOR,
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cs_qhxmvae667uap4zh": [
        # https://github.com/home-assistant/core/issues/141278
        Platform.FAN,
        Platform.HUMIDIFIER,
    ],
    "cs_vmxuxszzjwp5smli": [
        # https://github.com/home-assistant/core/issues/119865
        Platform.FAN,
        Platform.HUMIDIFIER,
    ],
    "cs_zibqa9dutqyaxym2": [
        Platform.BINARY_SENSOR,
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cwjwq_agwu93lr": [
        # https://github.com/orgs/home-assistant/discussions/79
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cwwsq_wfkzyy0evslzsmoi": [
        # https://github.com/home-assistant/core/issues/144745
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    "cwysj_z3rpyvznfcch99aa": [
        # https://github.com/home-assistant/core/pull/146599
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cz_2jxesipczks0kdct": [
        # https://github.com/home-assistant/core/issues/147149
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "dj_mki13ie507rlry4r": [
        # https://github.com/home-assistant/core/pull/126242
        Platform.LIGHT
    ],
    "dlq_0tnvg2xaisqdadcf": [
        # https://github.com/home-assistant/core/issues/102769
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "dlq_kxdr6su0c55p7bbo": [
        # https://github.com/home-assistant/core/issues/143499
        Platform.SENSOR,
    ],
    "fs_g0ewlb1vmwqljzji": [
        # https://github.com/home-assistant/core/issues/141231
        Platform.FAN,
        Platform.LIGHT,
        Platform.SELECT,
    ],
    "fs_ibytpo6fpnugft1c": [
        # https://github.com/home-assistant/core/issues/135541
        Platform.FAN,
    ],
    "gyd_lgekqfxdabipm3tn": [
        # https://github.com/home-assistant/core/issues/133173
        Platform.LIGHT,
    ],
    "kg_gbm9ata1zrzaez4a": [
        # https://github.com/home-assistant/core/issues/148347
        Platform.SWITCH,
    ],
    "kj_CAjWAxBUZt7QZHfz": [
        # https://github.com/home-assistant/core/issues/146023
        Platform.FAN,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "kj_yrzylxax1qspdgpp": [
        # https://github.com/orgs/home-assistant/discussions/61
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "ks_j9fa8ahzac8uvlfl": [
        # https://github.com/orgs/home-assistant/discussions/329
        Platform.FAN,
        Platform.LIGHT,
        Platform.SWITCH,
    ],
    "kt_5wnlzekkstwcdsvm": [
        # https://github.com/home-assistant/core/pull/148646
        Platform.CLIMATE,
    ],
    "mal_gyitctrjj1kefxp2": [
        # Alarm Host support
        Platform.ALARM_CONTROL_PANEL,
        Platform.NUMBER,
        Platform.SWITCH,
    ],
    "mcs_7jIGJAymiH8OsFFb": [
        # https://github.com/home-assistant/core/issues/108301
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "qccdz_7bvgooyjhiua1yyq": [
        # https://github.com/home-assistant/core/issues/136207
        Platform.SWITCH,
    ],
    "qxj_fsea1lat3vuktbt6": [
        # https://github.com/orgs/home-assistant/discussions/318
        Platform.SENSOR,
    ],
    "qxj_is2indt9nlth6esa": [
        # https://github.com/home-assistant/core/issues/136472
        Platform.SENSOR,
    ],
    "rqbj_4iqe2hsfyd86kwwc": [
        # https://github.com/orgs/home-assistant/discussions/100
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "sfkzq_o6dagifntoafakst": [
        # https://github.com/home-assistant/core/issues/148116
        Platform.SWITCH,
    ],
    "tdq_cq1p0nt0a4rixnex": [
        # https://github.com/home-assistant/core/issues/146845
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "tyndj_pyakuuoc": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "wk_aqoouq7x": [
        # https://github.com/home-assistant/core/issues/146263
        Platform.CLIMATE,
        Platform.SWITCH,
    ],
    "wk_fi6dne5tu4t1nm6j": [
        # https://github.com/orgs/home-assistant/discussions/243
        Platform.CLIMATE,
        Platform.NUMBER,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "wsdcg_g2y6z3p3ja2qhyav": [
        # https://github.com/home-assistant/core/issues/102769
        Platform.SENSOR,
    ],
    "wxkg_l8yaz4um5b3pwyvf": [
        # https://github.com/home-assistant/core/issues/93975
        Platform.EVENT,
        Platform.SENSOR,
    ],
    "ydkt_jevroj5aguwdbs2e": [
        # https://github.com/orgs/home-assistant/discussions/288
        # unsupported device - no platforms
    ],
    "zndb_ze8faryrxr0glqnn": [
        # https://github.com/home-assistant/core/issues/138372
        Platform.SENSOR,
    ],
}


class MockDeviceListener(DeviceListener):
    """Mocked DeviceListener for testing."""

    async def async_send_device_update(
        self,
        hass: HomeAssistant,
        device: CustomerDevice,
        updated_status_properties: dict[str, Any] | None = None,
    ) -> None:
        """Mock update device method."""
        property_list: list[str] = []
        if updated_status_properties:
            for key, value in updated_status_properties.items():
                if key not in device.status:
                    raise ValueError(
                        f"Property {key} not found in device status: {device.status}"
                    )
                device.status[key] = value
                property_list.append(key)
        self.update_device(device, property_list)
        await hass.async_block_till_done()


async def initialize_entry(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Initialize the Tuya component with a mock manager and config entry."""
    # Setup
    mock_manager.device_map = {
        mock_device.id: mock_device,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with patch(
        "homeassistant.components.tuya.ManagerCompat", return_value=mock_manager
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
