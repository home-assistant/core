"""Define tests for the Airzone init."""

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_config_flow import HOST, MAC

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import mock_aiohttp_client

DATA = {
    "skyfi/common/get_datetime?cur=": {
        "text": "ret=OK,sta=2,cur=2023/6/5 13:36:41,reg=au,dst=1,zone=27"
    },
    "common/basic_info": {"text": "", "status": 404},
    "skyfi/common/basic_info": {
        "text": "ret=OK,type=aircon,reg=au,dst=1,ver=1_1_8,rev=1F,pow=1,err=0,location=0,name=%44%61%69%6b%69%6e%41%50%30%30%30%30%30,icon=0,method=home only,port=30050,id=,pw=,lpw_flag=0,adp_kind=3,led=1,en_setzone=1,mac=AABBCCDDEEFF,adp_mode=run,ssid=DaikinAP00000,err_type=0,err_code=0,en_ch=1,holiday=1,en_hol=0,sync_time=0"
    },
    "skyfi/aircon/get_control_info": {
        "text": "ret=OK,pow=1,mode=1,operate=1,bk_auto=1,stemp=21,dt1=21,dt2=28,f_rate=1,dfr1=1,dfr2=1,f_airside=1,airside1=1,airside2=1,f_auto=0,auto1=0,auto2=0,f_dir=0,dfd1=0,dfd2=1,filter_sign_info=0,cent=0,en_cent=0,remo=2"
    },
    "skyfi/aircon/get_model_info": {
        "text": "ret=OK,err=0,model=NOTSUPPORT,type=N,humd=0,s_humd=7,en_zone=4,en_linear_zone=1,en_filter_sign=1,acled=1,land=0,elec=0,temp=1,m_dtct=0,ac_dst=au,dmnd=0,en_temp_setting=1,en_frate=1,en_fdir=0,en_rtemp_a=0,en_spmode=0,en_ipw_sep=0,en_scdltmr=0,en_mompow=0,en_patrol=0,en_airside=1,en_quick_timer=1,en_auto=1,en_dry=1,en_common_zone=0,cool_l=16,cool_h=32,heat_l=16,heat_h=32,frate_steps=3,en_frate_auto=1"
    },
    "skyfi/aircon/get_sensor_info": {"text": "ret=OK,err=0,htemp=21,otemp=-"},
    "skyfi/aircon/get_zone_setting": {
        "text": "ret=OK,zone_name=%5a%6f%6e%65%20%31%3b%5a%6f%6e%65%20%32%3b%5a%6f%6e%65%20%33%3b%5a%6f%6e%65%20%34%3b%2d%3b%2d%3b%2d%3b%2d,zone_onoff=1%3b1%3b0%3b1%3b0%3b0%3b0%3b0,lztemp_c=22%3b22%3b22%3b22%3b22%3b22%3b22%3b22,lztemp_h=21%3b19%3b19%3b0%3b0%3b0%3b0%3b0"
    },
}

INVALID_DATA = {
    **DATA,
    "skyfi/common/basic_info": {"text": "", "status": 404},
}


async def test_unique_id_migrate(hass: HomeAssistant) -> None:
    """Test unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        data={CONF_HOST: HOST, KEY_MAC: HOST},
    )
    config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    with mock_aiohttp_client() as newsession:
        for path, data in INVALID_DATA.items():
            newsession.get(f"http://{HOST}/{path}", **data)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.unique_id == HOST

        assert device_registry.async_get_device({}, {(KEY_MAC, HOST)}).name is None

        assert entity_registry.async_get("climate.daikin_127_0_0_1").unique_id == HOST
        assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(
            HOST
        )

        newsession.clear_requests()

        for path, data in DATA.items():
            newsession.get(f"http://{HOST}/{path}", **data)

        assert config_entry.unique_id != MAC

        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.unique_id == MAC

        assert (
            device_registry.async_get_device({}, {(KEY_MAC, MAC)}).name
            == "DaikinAP00000"
        )

        assert entity_registry.async_get("climate.daikin_127_0_0_1").unique_id == MAC
        assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(MAC)
