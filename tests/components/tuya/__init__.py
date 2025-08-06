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
    "cz_0g1fmqh6d5io7lcn": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SWITCH,
    ],
    "cz_2jxesipczks0kdct": [
        # https://github.com/home-assistant/core/issues/147149
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cz_cuhokdii7ojyw8k2": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SWITCH,
    ],
    "cz_dntgh2ngvshfxpsz": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SWITCH,
    ],
    "cz_hj0a5c7ckzzexu8l": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cz_t0a4hwsf8anfsadp": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "dc_l3bpgg8ibsagon4x": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_8szt7whdvwpmxglk": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_8y0aquaa8v6tho8w": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_baf9tt9lb8t5uc7z": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_d4g0fbsoaal841o6": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_djnozmdyqyriow8z": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_ekwolitfjhxn55js": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_fuupmcr2mb1odkja": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_hp6orhaqm6as3jnv": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_hpc8ddyfv85haxa7": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_iayz2jmtlipjnxj7": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_idnfq7xbx8qewyoa": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_ilddqqih3tucdk68": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_j1bgp31cffutizub": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_lmnt3uyltk1xffrt": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_mki13ie507rlry4r": [
        # https://github.com/home-assistant/core/pull/126242
        Platform.LIGHT,
    ],
    "dj_nbumqpv8vz61enji": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_nlxvjzy1hoeiqsg6": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_oe0cpnjg": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_riwp3k79": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_tmsloaroqavbucgn": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_ufq2xwuzd4nb0qdr": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_vqwcnabamzrc2kab": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_xokdfs6kh5ednakk": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_zakhnlpdiu0ycdxn": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_zav1pa32pyxray78": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
    ],
    "dj_zputiamzanuk6yky": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
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
    "hps_2aaelwxk": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.BINARY_SENSOR,
        Platform.NUMBER,
    ],
    "kg_gbm9ata1zrzaez4a": [
        # https://github.com/home-assistant/core/issues/148347
        Platform.SWITCH,
    ],
    "kj_CAjWAxBUZt7QZHfz": [
        # https://github.com/home-assistant/core/issues/146023
        Platform.FAN,
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
    "pc_t2afic7i3v1bwhfp": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SWITCH,
    ],
    "pc_trjopo1vdlt9q1tg": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.SWITCH,
    ],
    "pir_3amxzozho9xp4mkh": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "pir_fcdjzz3s": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "pir_wqz93nrdomectyoz": [
        # https://github.com/home-assistant/core/issues/149704
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
    "sd_lr33znaodtyarrrz": [
        # https://github.com/home-assistant/core/issues/141278
        Platform.BUTTON,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ],
    "sfkzq_o6dagifntoafakst": [
        # https://github.com/home-assistant/core/issues/148116
        Platform.SWITCH,
    ],
    "sgbj_ulv4nnue7gqp0rjk": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SIREN,
    ],
    "sp_drezasavompxpcgm": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.CAMERA,
        Platform.LIGHT,
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "sp_rjKXWRohlvOTyLBu": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.CAMERA,
        Platform.LIGHT,
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "sp_sdd5f5f2dl5wydjf": [
        # https://github.com/home-assistant/core/issues/144087
        Platform.CAMERA,
        Platform.NUMBER,
        Platform.SENSOR,
        Platform.SELECT,
        Platform.SIREN,
        Platform.SWITCH,
    ],
    "tdq_1aegphq4yfd50e6b": [
        # https://github.com/home-assistant/core/issues/143209
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "tdq_9htyiowaf5rtdhrv": [
        # https://github.com/home-assistant/core/issues/143209
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "tdq_cq1p0nt0a4rixnex": [
        # https://github.com/home-assistant/core/issues/146845
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "tdq_nockvv2k39vbrxxk": [
        # https://github.com/home-assistant/core/issues/145849
        Platform.SWITCH,
    ],
    "tdq_pu8uhxhwcp3tgoz7": [
        # https://github.com/home-assistant/core/issues/141278
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "tdq_uoa3mayicscacseb": [
        # https://github.com/home-assistant/core/issues/128911
        # SDK information is empty
    ],
    "tyndj_pyakuuoc": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.LIGHT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "wfcon_b25mh8sxawsgndck": [
        # https://github.com/home-assistant/core/issues/149704
    ],
    "wk_aqoouq7x": [
        # https://github.com/home-assistant/core/issues/146263
        Platform.CLIMATE,
        Platform.SWITCH,
    ],
    "wg2_nwxr8qcu4seltoro": [
        # https://github.com/orgs/home-assistant/discussions/430
        Platform.BINARY_SENSOR,
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
    "ywbj_gf9dejhmzffgdyfj": [
        # https://github.com/home-assistant/core/issues/149704
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "ywcgq_h8lvyoahr6s6aybf": [
        # https://github.com/home-assistant/core/issues/145932
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    "ywcgq_wtzwyhkev3b4ubns": [
        # https://github.com/home-assistant/core/issues/103818
        Platform.NUMBER,
        Platform.SENSOR,
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
