"""Test Home Assistant package util methods."""
import os
import pkg_resources
import unittest

from subprocess import PIPE
from distutils.sysconfig import get_python_lib
from unittest.mock import call, patch, Mock

import homeassistant.util.package as package

RESOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'resources'))

TEST_EXIST_REQ = 'pip>=7.0.0'
TEST_NEW_REQ = 'pyhelloworld3==1.0.0'
TEST_ZIP_REQ = 'file://{}#{}' \
    .format(os.path.join(RESOURCE_DIR, 'pyhelloworld3.zip'), TEST_NEW_REQ)


@patch('homeassistant.util.package.Popen')
@patch('homeassistant.util.package.check_package_exists')
class TestPackageUtilInstallPackage(unittest.TestCase):
    """Test for homeassistant.util.package module."""

    def setUp(self):
        """Setup the tests."""
        self.mock_process = Mock()
        self.mock_process.communicate.return_value = (b'message', b'error')
        self.mock_process.returncode = 0

    def test_install_existing_package(self, mock_exists, mock_popen):
        """Test an install attempt on an existing package."""
        mock_popen.return_value = self.mock_process
        mock_exists.return_value = True

        self.assertTrue(package.install_package(TEST_EXIST_REQ))

        self.assertEqual(mock_exists.call_count, 1)
        self.assertEqual(mock_exists.call_args, call(TEST_EXIST_REQ, None))

        self.assertEqual(self.mock_process.communicate.call_count, 0)

    @patch('homeassistant.util.package.sys')
    def test_install(self, mock_sys, mock_exists, mock_popen):
        """Test an install attempt on a package that doesn't exist."""
        mock_exists.return_value = False
        mock_popen.return_value = self.mock_process

        self.assertTrue(package.install_package(TEST_NEW_REQ, False))

        self.assertEqual(mock_exists.call_count, 1)

        self.assertEqual(self.mock_process.communicate.call_count, 1)
        self.assertEqual(mock_popen.call_count, 1)
        self.assertEqual(
            mock_popen.call_args,
            call([
                mock_sys.executable, '-m', 'pip', 'install', '--quiet',
                TEST_NEW_REQ
            ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        )

    @patch('homeassistant.util.package.sys')
    def test_install_upgrade(self, mock_sys, mock_exists, mock_popen):
        """Test an upgrade attempt on a package."""
        mock_exists.return_value = False
        mock_popen.return_value = self.mock_process

        self.assertTrue(package.install_package(TEST_NEW_REQ))

        self.assertEqual(mock_exists.call_count, 1)

        self.assertEqual(self.mock_process.communicate.call_count, 1)
        self.assertEqual(mock_popen.call_count, 1)
        self.assertEqual(
            mock_popen.call_args,
            call([
                mock_sys.executable, '-m', 'pip', 'install', '--quiet',
                TEST_NEW_REQ, '--upgrade'
            ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        )

    @patch('homeassistant.util.package.sys')
    def test_install_target(self, mock_sys, mock_exists, mock_popen):
        """Test an install with a target."""
        target = 'target_folder'
        mock_exists.return_value = False
        mock_popen.return_value = self.mock_process

        self.assertTrue(
            package.install_package(TEST_NEW_REQ, False, target=target)
        )

        self.assertEqual(mock_exists.call_count, 1)

        self.assertEqual(self.mock_process.communicate.call_count, 1)
        self.assertEqual(mock_popen.call_count, 1)
        self.assertEqual(
            mock_popen.call_args,
            call([
                mock_sys.executable, '-m', 'pip', 'install', '--quiet',
                TEST_NEW_REQ, '--target', os.path.abspath(target)
            ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        )

    @patch('homeassistant.util.package._LOGGER')
    @patch('homeassistant.util.package.sys')
    def test_install_error(self, mock_sys, mock_logger, mock_exists,
                           mock_popen):
        """Test an install with a target."""
        mock_exists.return_value = False
        mock_popen.return_value = self.mock_process
        self.mock_process.returncode = 1

        self.assertFalse(package.install_package(TEST_NEW_REQ))

        self.assertEqual(mock_logger.error.call_count, 1)


class TestPackageUtilCheckPackageExists(unittest.TestCase):
    """Test for homeassistant.util.package module."""

    def test_check_package_global(self):
        """Test for a globally-installed package."""
        installed_package = list(pkg_resources.working_set)[0].project_name

        self.assertTrue(package.check_package_exists(installed_package, None))

    def test_check_package_local(self):
        """Test for a locally-installed package."""
        lib_dir = get_python_lib()
        installed_package = list(pkg_resources.working_set)[0].project_name

        self.assertTrue(
            package.check_package_exists(installed_package, lib_dir)
        )

    def test_check_package_zip(self):
        """Test for an installed zip package."""
        self.assertFalse(package.check_package_exists(TEST_ZIP_REQ, None))
