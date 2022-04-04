"""Tests for the filesize component."""
import os

TEST_DIR = os.path.join(os.path.dirname(__file__))
TEST_FILE_NAME = "mock_file_test_filesize.txt"
TEST_FILE_NAME2 = "mock_file_test_filesize2.txt"
TEST_FILE = os.path.join(TEST_DIR, TEST_FILE_NAME)
TEST_FILE2 = os.path.join(TEST_DIR, TEST_FILE_NAME2)


def create_file(path) -> None:
    """Create a test file."""
    with open(path, "w", encoding="utf-8") as test_file:
        test_file.write("test")
