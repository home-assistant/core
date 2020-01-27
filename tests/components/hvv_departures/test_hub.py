"""Test the HVV Departures GTIHub."""
from asynctest import patch

from homeassistant.components.hvv_departures.hub import GTIHub


async def test_hub(hass):
    """Test if the hub works as expected."""

    hub = GTIHub("api-test.geofox.de", "test-username", "test-password", None)

    with (
        patch(
            "pygti.gti.GTI.init",
            return_value={
                "returnCode": "OK",
                "beginOfService": "23.01.2020",
                "endOfService": "13.12.2020",
                "id": "1.61.0",
                "dataId": "32.14.01",
                "buildDate": "23.01.2020",
                "buildTime": "15:53:15",
                "buildText": "Regelfahrplan 2020",
            },
        )
    ):
        response = await hub.authenticate()

        assert response["returnCode"] == "OK"
