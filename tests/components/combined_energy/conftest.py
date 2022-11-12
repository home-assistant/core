"""Local PyTest config."""
from combined_energy import models
import pytest

from .common import mock_device


@pytest.fixture
def installation() -> models.Installation:
    """Installation fixture."""
    return models.Installation(
        installationId=999998,
        installationName="My System",
        source="a",
        role="OWNER",
        readOnly=False,
        timezone="Australia/NSW",
        dmgId=18714,
        tags=[],
        mqttAccountKura="cet-ecn",
        mqttBrokerEms="mqtt2.combined.energy",
        streetAddress="54827 Blake Lane",
        locality="Mitchellview",
        state="TAS",
        postcode="6339",
        status="ACTIVE",
        reviewStatus="VALIDATED",
        nmi="123456789",
        phase=1,
        orgId=9999,
        tariffPlanId=9999,
        tariffPlanAccepted=1666579319338,
        devices=[mock_device(models.DeviceType.SolarPV, device_id=1)],
        pm={},
        brand="solahart",
    )
