"""Test the frigidaire config flow."""
from unittest.mock import patch

import frigidaire

from homeassistant import config_entries, setup
from homeassistant.components.frigidaire.const import DOMAIN
from homeassistant.core import HomeAssistant

FAKE_APPLIANCE = frigidaire.Appliance(
    {
        "appliance_id": "test",
        "appliance_type": "test",
        "pnc": "test",
        "elc": "test",
        "sn": "test",
        "mac": "test",
        "cpv": "test",
        "nickname": "test",
    }
)

FAKE_APPLIANCE_DETAIL_CONTAINERS = [
    {
        "propertyName": "Coefficient",
        "tId": "1",
        "group": 0,
        "numberValue": 72,
        "translation": "Coefficient",
    },
    {
        "propertyName": "Unit",
        "tId": "0",
        "group": 0,
        "numberValue": 1,
        "translation": "Unit",
    },
    {
        "propertyName": "Exponent",
        "tId": "3",
        "group": 0,
        "numberValue": 0,
        "translation": "Exponent",
    },
]

FAKE_APPLIANCE_DETAILS = frigidaire.ApplianceDetails(
    [
        frigidaire.ApplianceDetail(
            {
                "stringValue": "Fahrenheit",
                "numberValue": 1,
                "spkTimestamp": 1622052985620,
                "description": "Temperature Representation",
                "haclCode": "0420",
                "source": "AC1",
                "containers": [],
            }
        ),
        frigidaire.ApplianceDetail(
            {
                "stringValue": None,
                "numberValue": 0,
                "spkTimestamp": 1624311177889,
                "description": "AC-Mode",
                "haclCode": "1000",
                "source": "AC1",
                "containers": [],
            }
        ),
        frigidaire.ApplianceDetail(
            {
                "stringValue": None,
                "numberValue": None,
                "spkTimestamp": 1624312954475,
                "description": "Ambient Temperature",
                "haclCode": "0430",
                "source": "AC1",
                "containers": FAKE_APPLIANCE_DETAIL_CONTAINERS,
            }
        ),
        frigidaire.ApplianceDetail(
            {
                "stringValue": None,
                "numberValue": None,
                "spkTimestamp": 1624312954475,
                "description": "Target Temperature",
                "haclCode": "0432",
                "source": "AC1",
                "containers": FAKE_APPLIANCE_DETAIL_CONTAINERS,
            }
        ),
    ]
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch("frigidaire.Frigidaire.authenticate", return_value=None,), patch(
        "frigidaire.Frigidaire.get_appliances",
        return_value=[FAKE_APPLIANCE],
    ), patch(
        "frigidaire.Frigidaire.get_appliance_details",
        return_value=FAKE_APPLIANCE_DETAILS,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "frigidaire.Frigidaire.authenticate",
        side_effect=frigidaire.FrigidaireException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "frigidaire.Frigidaire.authenticate",
        side_effect=frigidaire.FrigidaireException(
            "Failed to authenticate, sessionKey was not in response"
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_no_appliances(hass: HomeAssistant) -> None:
    """Test we handle no appliances."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "frigidaire.Frigidaire.authenticate",
        return_value=None,
    ), patch("frigidaire.Frigidaire.get_appliances", return_value=[]):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "no_appliances"}


async def test_form_broad_exception(hass: HomeAssistant) -> None:
    """Test we handle generic exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "frigidaire.Frigidaire.authenticate",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
