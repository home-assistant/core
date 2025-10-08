"""Test DoorBird view."""

from http import HTTPStatus

from homeassistant.components.doorbird.const import API_URL

from .conftest import DoorbirdMockerType

from tests.typing import ClientSessionGenerator


async def test_non_webhook_with_wrong_token(
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test calling the webhook with the wrong token."""
    await doorbird_mocker()
    client = await hass_client()

    response = await client.get(f"{API_URL}/doorbell?token=wrong")
    assert response.status == HTTPStatus.UNAUTHORIZED
