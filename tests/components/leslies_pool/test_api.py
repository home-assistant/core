"""Test the API for Leslie's Pool Water Tests."""

import unittest
from unittest.mock import MagicMock, patch

from homeassistant.components.leslies_pool.api import LesliesPoolApi


class TestLesliesPoolApi(unittest.TestCase):
    """Test the Leslie's Pool API."""

    def setUp(self):
        """Set up the test."""
        self.api = LesliesPoolApi("testuser", "testpassword", "123456", "TestPool")

    @patch("homeassistant.components.leslies_pool.api.requests.Session.get")
    @patch("homeassistant.components.leslies_pool.api.requests.Session.post")
    def test_authenticate_success(self, mock_post, mock_get):
        """Test successful authentication."""
        login_page_html = '<input name="csrf_token" value="test_csrf_token">'
        mock_get.return_value = MagicMock(status_code=200, text=login_page_html)
        mock_post.return_value = MagicMock(status_code=200)

        result = self.api.authenticate()

        assert result
        mock_get.assert_called_once_with(self.api.LOGIN_PAGE_URL)
        mock_post.assert_called_once_with(
            self.api.LOGIN_URL,
            headers={
                "accept": "application/json, text/javascript, */*; q=0.01",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "user-agent": "Mozilla/5.0",
            },
            data={
                "loginEmail": "testuser",
                "loginPassword": "testpassword",
                "csrf_token": "test_csrf_token",
            },
        )

    @patch("homeassistant.components.leslies_pool.api.requests.Session.get")
    @patch("homeassistant.components.leslies_pool.api.requests.Session.post")
    def test_authenticate_fail(self, mock_post, mock_get):
        """Test failed authentication."""
        login_page_html = '<input name="csrf_token" value="test_csrf_token">'
        mock_get.return_value = MagicMock(status_code=200, text=login_page_html)
        mock_post.return_value = MagicMock(status_code=401)

        result = self.api.authenticate()

        assert not result

    @patch("homeassistant.components.leslies_pool.api.requests.Session.get")
    @patch("homeassistant.components.leslies_pool.api.requests.Session.post")
    def test_fetch_water_test_data(self, mock_post, mock_get):
        """Test fetching water test data."""
        # Mock the response for the landing page request
        mock_get.return_value = MagicMock(status_code=200)

        # Mock the response for the water test data request
        water_test_html = """
        <table class="table table-striped table-bordered table-hover table-sm">
            <tbody>
                <tr>
                    <td>Test</td>
                    <td>1.0</td>
                    <td>2.0</td>
                    <td>7.0</td>
                    <td>80</td>
                    <td>200</td>
                    <td>30</td>
                    <td>0.1</td>
                    <td>0.2</td>
                    <td>300</td>
                    <td>4000</td>
                </tr>
            </tbody>
        </table>
        """
        mock_post.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value={"response": water_test_html})
        )

        data = self.api.fetch_water_test_data()

        assert data["free_chlorine"] == "1.0"
        assert data["total_chlorine"] == "2.0"
        assert data["ph"] == "7.0"
        assert data["alkalinity"] == "80"
        assert data["calcium"] == "200"
        assert data["cyanuric_acid"] == "30"
        assert data["iron"] == "0.1"
        assert data["copper"] == "0.2"
        assert data["phosphates"] == "300"
        assert data["salt"] == "4000"
