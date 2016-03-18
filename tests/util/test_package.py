"""Test Home Assistant package util methods."""
import os
import tempfile
import unittest

import homeassistant.bootstrap as bootstrap
import homeassistant.util.package as package

RESOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'resources'))

TEST_EXIST_REQ = "pip>=7.0.0"
TEST_NEW_REQ = "pyhelloworld3==1.0.0"
TEST_ZIP_REQ = 'file://{}#{}' \
    .format(os.path.join(RESOURCE_DIR, 'pyhelloworld3.zip'), TEST_NEW_REQ)


class TestPackageUtil(unittest.TestCase):
    """Test for homeassistant.util.package module."""

    def setUp(self):
        """Create local library for testing."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.lib_dir = os.path.join(self.tmp_dir.name, 'lib')

    def tearDown(self):
        """Stop everything that was started."""
        self.tmp_dir.cleanup()

    def test_install_existing_package(self):
        """Test an install attempt on an existing package."""
        self.assertTrue(package.check_package_exists(
            TEST_EXIST_REQ, self.lib_dir))

        self.assertTrue(package.install_package(TEST_EXIST_REQ))

    def test_install_package_zip(self):
        """Test an install attempt from a zip path."""
        self.assertFalse(package.check_package_exists(
            TEST_ZIP_REQ, self.lib_dir))
        self.assertFalse(package.check_package_exists(
            TEST_NEW_REQ, self.lib_dir))

        self.assertTrue(package.install_package(
            TEST_ZIP_REQ, True, self.lib_dir))

        self.assertTrue(package.check_package_exists(
            TEST_ZIP_REQ, self.lib_dir))
        self.assertTrue(package.check_package_exists(
            TEST_NEW_REQ, self.lib_dir))

        bootstrap.mount_local_lib_path(self.tmp_dir.name)

        try:
            import pyhelloworld3
        except ImportError:
            self.fail('Unable to import pyhelloworld3 after installing it.')

        self.assertEqual(pyhelloworld3.__version__, '1.0.0')
