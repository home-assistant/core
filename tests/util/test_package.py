"""
Tests Home Assistant package util methods.
"""
import unittest
import sys
import tempfile
import homeassistant.util.package as package

TEST_EXIST_REQ = "pip>=7.0.0"
TEST_NEW_REQ = "pyhelloworld3==1.0.0"
TEST_ZIP_REQ = \
    "https://github.com/rmkraus/pyhelloworld3/archive/" \
    "5ba878316d68ea164e2cf5bd085d0cf1fd76bd15.zip#pyhelloworld3==1.0.0"


class TestPackageUtil(unittest.TestCase):
    """ Tests for homeassistant.util.package module """

    def setUp(self):
        """ Create local library for testing """
        self.lib_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """ Remove local library """
        del self.lib_dir

    def test_install_existing_package(self):
        """ Test an install attempt on an existing package """
        self.assertTrue(package.check_package_exists(
            TEST_EXIST_REQ, self.lib_dir.name))

        self.assertTrue(package.install_package(TEST_EXIST_REQ))

    def test_install_package_locally(self):
        """ Test an install attempt to the local library """
        self.assertFalse(package.check_package_exists(
            TEST_NEW_REQ, self.lib_dir.name))

        self.assertTrue(package.install_package(
            TEST_NEW_REQ, True, self.lib_dir.name))

        sys.path.insert(0, self.lib_dir.name)
        import pyhelloworld3

        self.assertEqual(pyhelloworld3.__version__, '1.0.0')

    def test_install_package_zip(self):
        """ Test an install attempt from a zip path """
        self.assertFalse(package.check_package_exists(
            TEST_ZIP_REQ, self.lib_dir.name))

        self.assertTrue(package.install_package(
            TEST_ZIP_REQ, True, self.lib_dir.name))

        sys.path.insert(0, self.lib_dir.name)
        import pyhelloworld3

        self.assertEqual(pyhelloworld3.__version__, '1.0.0')
