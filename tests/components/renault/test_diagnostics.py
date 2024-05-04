"""Test Renault diagnostics."""

import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.renault import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")

VEHICLE_DETAILS = {
    "vin": REDACTED,
    "registrationDate": "2017-08-01",
    "firstRegistrationDate": "2017-08-01",
    "engineType": "5AQ",
    "engineRatio": "601",
    "modelSCR": "ZOE",
    "deliveryCountry": {"code": "FR", "label": "FRANCE"},
    "family": {"code": "X10", "label": "FAMILLE X10", "group": "007"},
    "tcu": {
        "code": "TCU0G2",
        "label": "TCU VER 0 GEN 2",
        "group": "E70",
    },
    "navigationAssistanceLevel": {
        "code": "NAV3G5",
        "label": "LEVEL 3 TYPE 5 NAVIGATION",
        "group": "408",
    },
    "battery": {
        "code": "BT4AR1",
        "label": "BATTERIE BT4AR1",
        "group": "968",
    },
    "radioType": {
        "code": "RAD37A",
        "label": "RADIO 37A",
        "group": "425",
    },
    "registrationCountry": {"code": "FR"},
    "brand": {"label": "RENAULT"},
    "model": {"code": "X101VE", "label": "ZOE", "group": "971"},
    "gearbox": {
        "code": "BVEL",
        "label": "BOITE A VARIATEUR ELECTRIQUE",
        "group": "427",
    },
    "version": {"code": "INT MB 10R"},
    "energy": {"code": "ELEC", "label": "ELECTRIQUE", "group": "019"},
    "registrationNumber": REDACTED,
    "vcd": "SYTINC/SKTPOU/SAND41/FDIU1/SSESM/MAPSUP/SSCALL/SAND88/SAND90/SQKDRO/SDIFPA/FACBA2/PRLEX1/SSRCAR/CABDO2/TCU0G2/SWALBO/EVTEC1/STANDA/X10/B10/EA2/MB/ELEC/DG/TEMP/TR4X2/RV/ABS/CAREG/LAC/VT003/CPE/RET03/SPROJA/RALU16/CEAVRH/AIRBA1/SERIE/DRA/DRAP08/HARM02/ATAR/TERQG/SFBANA/KM/DPRPN/AVREPL/SSDECA/ASRESP/RDAR02/ALEVA/CACBL2/SOP02C/CTHAB2/TRNOR/LVAVIP/LVAREL/SASURV/KTGREP/SGSCHA/APL03/ALOUCC/CMAR3P/NAV3G5/RAD37A/BVEL/AUTAUG/RNORM/ISOFIX/EQPEUR/HRGM01/SDPCLV/TLFRAN/SPRODI/SAN613/SSAPEX/GENEV1/ELC1/SANCML/PE2012/PHAS1/SAN913/045KWH/BT4AR1/VEC153/X101VE/NBT017/5AQ",
    "assets": [
        {
            "assetType": "PICTURE",
            "renditions": [
                {
                    "resolutionType": "ONE_MYRENAULT_LARGE",
                    "url": "https://3dv2.renault.com/ImageFromBookmark?configuration=SKTPOU%2FPRLEX1%2FSTANDA%2FB10%2FEA2%2FDG%2FVT003%2FRET03%2FRALU16%2FDRAP08%2FHARM02%2FTERQG%2FRDAR02%2FALEVA%2FSOP02C%2FTRNOR%2FLVAVIP%2FLVAREL%2FNAV3G5%2FRAD37A%2FSDPCLV%2FTLFRAN%2FGENEV1%2FSAN913%2FBT4AR1%2FNBT017&databaseId=1d514feb-93a6-4b45-8785-e11d2a6f1864&bookmarkSet=RSITE&bookmark=EXT_34_DESSUS&profile=HELIOS_OWNERSERVICES_LARGE",
                },
                {
                    "resolutionType": "ONE_MYRENAULT_SMALL",
                    "url": "https://3dv2.renault.com/ImageFromBookmark?configuration=SKTPOU%2FPRLEX1%2FSTANDA%2FB10%2FEA2%2FDG%2FVT003%2FRET03%2FRALU16%2FDRAP08%2FHARM02%2FTERQG%2FRDAR02%2FALEVA%2FSOP02C%2FTRNOR%2FLVAVIP%2FLVAREL%2FNAV3G5%2FRAD37A%2FSDPCLV%2FTLFRAN%2FGENEV1%2FSAN913%2FBT4AR1%2FNBT017&databaseId=1d514feb-93a6-4b45-8785-e11d2a6f1864&bookmarkSet=RSITE&bookmark=EXT_34_DESSUS&profile=HELIOS_OWNERSERVICES_SMALL_V2",
                },
            ],
        },
        {
            "assetType": "PDF",
            "assetRole": "GUIDE",
            "title": "PDF Guide",
            "description": "",
            "renditions": [
                {
                    "url": "https://cdn.group.renault.com/ren/gb/myr/assets/x101ve/manual.pdf.asset.pdf/1558704861676.pdf"
                }
            ],
        },
        {
            "assetType": "URL",
            "assetRole": "GUIDE",
            "title": "e-guide",
            "description": "",
            "renditions": [{"url": "http://gb.e-guide.renault.com/eng/Zoe"}],
        },
        {
            "assetType": "VIDEO",
            "assetRole": "CAR",
            "title": "10 Fundamentals about getting the best out of your electric vehicle",
            "description": "",
            "renditions": [{"url": "39r6QEKcOM4"}],
        },
        {
            "assetType": "VIDEO",
            "assetRole": "CAR",
            "title": "Automatic Climate Control",
            "description": "",
            "renditions": [{"url": "Va2FnZFo_GE"}],
        },
        {
            "assetType": "URL",
            "assetRole": "CAR",
            "title": "More videos",
            "description": "",
            "renditions": [{"url": "https://www.youtube.com/watch?v=wfpCMkK1rKI"}],
        },
        {
            "assetType": "VIDEO",
            "assetRole": "CAR",
            "title": "Charging the battery",
            "description": "",
            "renditions": [{"url": "RaEad8DjUJs"}],
        },
        {
            "assetType": "VIDEO",
            "assetRole": "CAR",
            "title": "Charging the battery at a station with a flap",
            "description": "",
            "renditions": [{"url": "zJfd7fJWtr0"}],
        },
    ],
    "yearsOfMaintenance": 12,
    "connectivityTechnology": "RLINK1",
    "easyConnectStore": False,
    "electrical": True,
    "rlinkStore": False,
    "deliveryDate": "2017-08-11",
    "retrievedFromDhs": False,
    "engineEnergyType": "ELEC",
    "radioCode": REDACTED,
}

VEHICLE_DATA = {
    "battery": {
        "batteryAutonomy": 141,
        "batteryAvailableEnergy": 31,
        "batteryCapacity": 0,
        "batteryLevel": 60,
        "batteryTemperature": 20,
        "chargingInstantaneousPower": 27,
        "chargingRemainingTime": 145,
        "chargingStatus": 1.0,
        "plugStatus": 1,
        "timestamp": "2020-01-12T21:40:16Z",
    },
    "charge_mode": {
        "chargeMode": "always",
    },
    "cockpit": {
        "totalMileage": 49114.27,
    },
    "hvac_status": {
        "externalTemperature": 8.0,
        "hvacStatus": "off",
    },
    "res_state": {},
}


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "data": {
                "kamereon_account_id": REDACTED,
                "locale": "fr_FR",
                "password": REDACTED,
                "username": REDACTED,
            },
            "title": "Mock Title",
        },
        "vehicles": [{"details": VEHICLE_DETAILS, "data": VEHICLE_DATA}],
    }


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_device_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "VF1AAAAA555777999")}
    )
    assert device is not None

    assert await get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    ) == {"details": VEHICLE_DETAILS, "data": VEHICLE_DATA}
