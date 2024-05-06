"""Tests for the folder_watcher component."""

import os

CWD = os.path.join(os.path.dirname(__file__))
TEST_FOLDER = "test_folder"
TEST_DIR = os.path.join(CWD, TEST_FOLDER)
TEST_TXT = "test.txt"
TEST_FILE = os.path.join(TEST_DIR, TEST_TXT)


def create_folder():
    """Create folder."""
    if not os.path.isdir(TEST_DIR):
        os.mkdir(TEST_DIR)


def create_file(text: str = "test"):
    """Create a test file."""
    create_folder()
    with open(TEST_FILE, "w") as test_file:
        test_file.write(text)


def remove_test_file():
    """Remove test file."""
    if os.path.isfile(TEST_FILE):
        os.remove(TEST_FILE)
        os.rmdir(TEST_DIR)
