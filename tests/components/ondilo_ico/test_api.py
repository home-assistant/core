"""Test the Ondilo API."""

from unittest.mock import patch

from homeassistant.components.ondilo_ico.api import OndiloClient, OndiloError

from .consts import ICO_DETAILS, LAST_MEASURES, POOL1, POOL2, TWO_POOLS


async def test_can_get_pools_when_no_error(ondilo_client: OndiloClient) -> None:
    """Test that I can get all pools data when no error."""
    with patch("ondilo.Ondilo.get_pools", return_value=[]):
        assert ondilo_client.get_all_pools_data() == []

    with (
        patch("ondilo.Ondilo.get_pools", return_value=TWO_POOLS),
        patch("ondilo.Ondilo.get_ICO_details", return_value=ICO_DETAILS),
        patch("ondilo.Ondilo.get_last_pool_measures", return_value=LAST_MEASURES),
    ):
        exp_result = TWO_POOLS
        exp_result[0]["ICO"] = ICO_DETAILS
        exp_result[1]["ICO"] = ICO_DETAILS
        exp_result[0]["sensors"] = LAST_MEASURES
        exp_result[1]["sensors"] = LAST_MEASURES
        assert ondilo_client.get_all_pools_data() == exp_result


async def test_no_ico_attached(ondilo_client: OndiloClient) -> None:
    """Test if an ICO is not attached to a pool, then it is not returned in list of pools."""
    with (
        patch("ondilo.Ondilo.get_pools", return_value=[POOL1]),
        patch("ondilo.Ondilo.get_ICO_details", return_value=None),
    ):
        assert ondilo_client.get_all_pools_data() == []

    with (
        patch("ondilo.Ondilo.get_pools", return_value=TWO_POOLS),
        patch("ondilo.Ondilo.get_ICO_details", side_effect=[None, ICO_DETAILS]),
        patch("ondilo.Ondilo.get_last_pool_measures", return_value=LAST_MEASURES),
    ):
        exp_result = [POOL2]
        exp_result[0]["ICO"] = ICO_DETAILS
        exp_result[0]["sensors"] = LAST_MEASURES
        assert ondilo_client.get_all_pools_data() == exp_result


async def test_error_retrieving_ico(ondilo_client: OndiloClient) -> None:
    """Test if there's an error retrieving ICO data, then it is not returned in list of pools."""
    with (
        patch("ondilo.Ondilo.get_pools", return_value=[POOL1]),
        patch("ondilo.Ondilo.get_ICO_details", side_effect=OndiloError(400, "error")),
    ):
        assert ondilo_client.get_all_pools_data() == []


async def test_error_retrieving_measures(ondilo_client: OndiloClient) -> None:
    """Test if there's an error retrieving measures of ICO, then it is not returned in list of pools."""
    with (
        patch("ondilo.Ondilo.get_pools", return_value=[POOL1]),
        patch("ondilo.Ondilo.get_ICO_details", return_value=ICO_DETAILS),
        patch(
            "ondilo.Ondilo.get_last_pool_measures",
            side_effect=OndiloError(400, "error"),
        ),
    ):
        assert ondilo_client.get_all_pools_data() == []
