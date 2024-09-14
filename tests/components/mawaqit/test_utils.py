"""Unit tests for Mawaqit component utility functions."""

# from unittest.mock import patch, Mock, MagicMock, mock_open
# import pytest
# import json
# import os
# import aiohttp
# from tests.common import MockConfigEntry
# from homeassistant.components.mawaqit import config_flow
# @pytest.mark.asyncio
# async def test_read_all_mosques_NN_file(mock_mosques_test_data):
#     sample_data, expected_output = mock_mosques_test_data
#     with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
#         assert config_flow.read_all_mosques_NN_file() == expected_output


# @pytest.fixture(scope="function")
# def test_folder_setup():
#     # Define the folder name
#     folder_name = "./test_dir"
#     # Create the folder
#     os.makedirs(folder_name, exist_ok=True)
#     # Pass the folder name to the test
#     yield folder_name
#     # No deletion here, handled by another fixture


# @pytest.fixture(scope="function", autouse=True)
# def test_folder_cleanup(request, test_folder_setup):
#     # This fixture does not need to do anything before the test,
#     # so it yields control immediately
#     yield
#     # Teardown: Delete the folder after the test runs
#     folder_path = test_folder_setup  # Corrected variable name

#     def cleanup():
#         if os.path.exists(folder_path):
#             os.rmdir(folder_path)  # Make sure the folder is empty before calling rmdir

#     request.addfinalizer(cleanup)

# @pytest.fixture
# async def mock_file_io():
#     # Utility fixture for mocking open
#     with patch("builtins.open", mock_open()) as mocked_file:
#         yield mocked_file

# @pytest.mark.asyncio
# async def test_write_all_mosques_NN_file(mock_file_io, test_folder_setup):
#     # test for write_all_mosques_NN_file
#     with patch(
#         "homeassistant.components.mawaqit.config_flow.CURRENT_DIR", new="./test_dir"
#     ):
#         mosques = [{"label": "Mosque A", "uuid": "uuid1"}]
#         config_flow.write_all_mosques_NN_file(mosques)
#         mock_file_io.assert_called_with(
#             f"{test_folder_setup}/data/all_mosques_NN.txt", "w"
#         )
#         assert mock_file_io().write.called, "The file's write method was not called."


# @pytest.mark.asyncio
# async def test_read_my_mosque_NN_file(hass):
#     # Sample data to be returned by the mock
#     sample_mosque = {"label": "My Mosque", "uuid": "myuuid"}
#     mock_file_data = json.dumps(sample_mosque)

#     test_dir = "./test_dir"
#     expected_file_path = f"{test_dir}/data/my_mosque_NN.txt"

#     with (
#         patch("builtins.open", mock_open(read_data=mock_file_data)) as mock_file,
#         patch(
#             "homeassistant.components.mawaqit.config_flow.CURRENT_DIR",
#             new=f"{test_dir}",
#         ),
#     ):
#         # Call the function to be tested
#         result = await config_flow.read_my_mosque_NN_file(hass)
#         # Assert the file was opened correctly
#         mock_file.assert_called_once_with(expected_file_path)
#         # Verify the function returns the correct result
#         assert result == sample_mosque


# @pytest.mark.asyncio
# # @patch('path.to.your.config_flow_module.CURRENT_DIR', './test_dir')
# async def test_write_my_mosque_NN_file(mock_file_io, test_folder_setup):
#     # test for write_my_mosque_NN_file
#     with patch(
#         "homeassistant.components.mawaqit.config_flow.CURRENT_DIR", new="./test_dir"
#     ):
#         mosque = {"label": "My Mosque", "uuid": "myuuid"}
#         config_flow.write_my_mosque_NN_file(mosque)
#         mock_file_io.assert_called_with(
#             f"{test_folder_setup}/data/my_mosque_NN.txt", "w"
#         )
#         assert mock_file_io().write.called, "The file's write method was not called."


# @pytest.mark.asyncio
# async def test_create_data_folder_already_exists(mock_data_folder):
#     # test for create_data_folder
#     mock_exists, mock_makedirs = mock_data_folder
#     mock_exists.return_value = True
#     config_flow.create_data_folder()
#     mock_makedirs.assert_not_called()
