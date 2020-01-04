"""Tests for OpenERZ component."""
from datetime import datetime
import unittest
from unittest.mock import patch

from testfixtures import LogCapture

from homeassistant.components.openerz.sensor import OpenERZSensor

MOCK_DATETIME = datetime(
    year=2019, month=12, day=10, hour=11, minute=15, second=0, microsecond=0
)


class MockAPIResponse:
    """Provide fake response from the OpenERZ API."""

    def __init__(self, is_ok, status_code, json_data):
        """Initialize all the values."""
        self.ok = is_ok
        self.status_code = status_code
        self.json_data = json_data

    def json(self):
        """Return response data."""
        return self.json_data


class TestOpenERZSensor(unittest.TestCase):
    """Test the OpenERZ sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.mock_datetime = MOCK_DATETIME
        self.mock_config = {
            "platform": "openerz",
            "name": "test_name",
            "zip": "1234",
            "waste_type": "glass",
            "entity_id": "sensor.erz_glass_1234",
        }

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_init(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime

            test_openerz = OpenERZSensor(self.mock_config)

            self.assertEqual(test_openerz.zip, "1234")
            self.assertEqual(test_openerz.waste_type, "glass")
            self.assertEqual(test_openerz.friendly_name, "test_name")
            self.assertEqual(test_openerz.start_date, self.mock_datetime)
            self.assertIsNone(test_openerz.end_date)
            self.assertIsNone(test_openerz.last_api_response)
            patched_update.assert_called_once()

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_init_no_name(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime

            del self.mock_config["name"]
            test_openerz = OpenERZSensor(self.mock_config)

            self.assertEqual(test_openerz.friendly_name, "glass")

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_update_start_date(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)

            patched_time.now.return_value = self.mock_datetime.replace(day=11)
            test_openerz.update_start_date()

            expected_start_date = datetime(
                year=2019, month=12, day=11, hour=11, minute=15, second=0, microsecond=0
            )
            self.assertEqual(test_openerz.start_date, expected_start_date)

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_find_end_date(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)

            test_openerz.find_end_date()

            expected_end_date = datetime(
                year=2020, month=1, day=10, hour=11, minute=15, second=0, microsecond=0
            )
            self.assertEqual(test_openerz.end_date, expected_end_date)

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_make_api_request(self, patched_update):
        """Test whether all values initialized properly."""
        with patch(
            "homeassistant.components.openerz.sensor.requests"
        ) as patched_requests:
            patched_requests.get.return_value = {}
            with patch(
                "homeassistant.components.openerz.sensor.datetime"
            ) as patched_time:
                patched_time.now.return_value = self.mock_datetime
                test_openerz = OpenERZSensor(self.mock_config)
                test_openerz.end_date = self.mock_datetime.replace(
                    year=2020, month=1, day=10
                )
                test_openerz.make_api_request()

                expected_headers = {"accept": "application/json"}
                expected_url = "http://openerz.metaodi.ch/api/calendar/glass.json"
                expected_payload = {
                    "zip": "1234",
                    "start": "2019-12-10",
                    "end": "2020-01-10",
                    "offset": 0,
                    "limit": 0,
                    "lang": "en",
                    "sort": "date",
                }
                used_args, used_kwargs = patched_requests.get.call_args_list[0]
                print(used_args)
                print(used_kwargs)
                self.assertEqual(used_args[0], expected_url)
                self.assertDictEqual(used_kwargs["headers"], expected_headers)
                self.assertDictEqual(used_kwargs["params"], expected_payload)

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_parse_api_response_ok(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)
            test_openerz.end_date = self.mock_datetime.replace(
                year=2020, month=1, day=10
            )

            response_data = {
                "_metadata": {"total_count": 1},
                "result": [{"zip": "1234", "type": "glass", "date": "2020-01-10"}],
            }
            test_openerz.last_api_response = MockAPIResponse(True, 200, response_data)

            test_pickup_date = test_openerz.parse_api_response()
            self.assertEqual(test_pickup_date, "2020-01-10")

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_parse_api_response_no_dates(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)
            test_openerz.end_date = self.mock_datetime.replace(
                year=2020, month=1, day=10
            )

            response_data = {"_metadata": {"total_count": 0}, "result": []}

            with LogCapture() as captured_logs:
                test_openerz.last_api_response = MockAPIResponse(
                    True, 200, response_data
                )

                test_pickup_date = test_openerz.parse_api_response()
                self.assertIsNone(test_pickup_date)
                captured_logs.check_present(
                    (
                        "homeassistant.components.openerz.sensor",
                        "WARNING",
                        "Request to OpenERZ returned no results.",
                    )
                )

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_parse_api_response_wrong_zip(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)
            test_openerz.end_date = self.mock_datetime.replace(
                year=2020, month=1, day=10
            )

            response_data = {
                "_metadata": {"total_count": 1},
                "result": [{"zip": "1235", "type": "glass", "date": "2020-01-10"}],
            }

            with LogCapture() as captured_logs:
                test_openerz.last_api_response = MockAPIResponse(
                    True, 200, response_data
                )

                test_pickup_date = test_openerz.parse_api_response()
                self.assertIsNone(test_pickup_date)
                captured_logs.check_present(
                    (
                        "homeassistant.components.openerz.sensor",
                        "WARNING",
                        "Either zip or waste type does not match the ones specified in the configuration.",
                    )
                )

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_parse_api_response_wrong_type(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)
            test_openerz.end_date = self.mock_datetime.replace(
                year=2020, month=1, day=10
            )

            response_data = {
                "_metadata": {"total_count": 1},
                "result": [{"zip": "1234", "type": "metal", "date": "2020-01-10"}],
            }

            with LogCapture() as captured_logs:
                test_openerz.last_api_response = MockAPIResponse(
                    True, 200, response_data
                )

                test_pickup_date = test_openerz.parse_api_response()
                self.assertIsNone(test_pickup_date)
                captured_logs.check_present(
                    (
                        "homeassistant.components.openerz.sensor",
                        "WARNING",
                        "Either zip or waste type does not match the ones specified in the configuration.",
                    )
                )

    @patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    )
    def test_sensor_parse_api_response_not_ok(self, patched_update):
        """Test whether all values initialized properly."""
        with patch("homeassistant.components.openerz.sensor.datetime") as patched_time:
            patched_time.now.return_value = self.mock_datetime
            test_openerz = OpenERZSensor(self.mock_config)
            test_openerz.end_date = self.mock_datetime.replace(
                year=2020, month=1, day=10
            )

            response_data = {"result": [{}]}

            with LogCapture() as captured_logs:
                test_openerz.last_api_response = MockAPIResponse(
                    False, 404, response_data
                )

                test_pickup_date = test_openerz.parse_api_response()
                self.assertIsNone(test_pickup_date)
                captured_logs.check_present(
                    (
                        "homeassistant.components.openerz.sensor",
                        "WARNING",
                        "Last request to OpenERZ was not succesful. Status code: 404",
                    )
                )
