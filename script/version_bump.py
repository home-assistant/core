#!/usr/bin/env python3
"""Helper script to bump the current version."""
import argparse
import re

from homeassistant import const


PARSE_PATCH = r'(?P<patch>\d+)(\.(?P<prerel>\D+)(?P<prerelversion>\d+))?'


def format_patch(patch_parts):
    """Format the patch parts back into a patch string."""
    return '{patch}.{prerel}{prerelversion}'.format(**patch_parts)


def bump_version(cur_major, cur_minor, cur_patch, bump_type):
    """Return a new version given a current version and action."""
    patch_parts = re.match(PARSE_PATCH, cur_patch).groupdict()
    patch_parts['patch'] = int(patch_parts['patch'])
    if patch_parts['prerelversion'] is not None:
        patch_parts['prerelversion'] = int(patch_parts['prerelversion'])

    if bump_type == 'release_patch':
        # Convert 0.67.3 to 0.67.4
        # Convert 0.67.3.beta5 to 0.67.3
        # Convert 0.67.3.dev0 to 0.67.3
        new_major = cur_major
        new_minor = cur_minor

        if patch_parts['prerel'] is None:
            new_patch = str(patch_parts['patch'] + 1)
        else:
            new_patch = str(patch_parts['patch'])

    elif bump_type == 'dev':
        # Convert 0.67.3 to 0.67.4.dev0
        # Convert 0.67.3.beta5 to 0.67.4.dev0
        # Convert 0.67.3.dev0 to 0.67.3.dev1
        new_major = cur_major

        if patch_parts['prerel'] == 'dev':
            new_minor = cur_minor
            patch_parts['prerelversion'] += 1
            new_patch = format_patch(patch_parts)
        else:
            new_minor = cur_minor + 1
            new_patch = '0.dev0'

    elif bump_type == 'beta':
        # Convert 0.67.5 to 0.67.8.beta0
        # Convert 0.67.0.dev0 to 0.67.0.beta0
        # Convert 0.67.5.beta4 to 0.67.5.beta5
        new_major = cur_major
        new_minor = cur_minor

        if patch_parts['prerel'] is None:
            patch_parts['patch'] += 1
            patch_parts['prerel'] = 'beta'
            patch_parts['prerelversion'] = 0

        elif patch_parts['prerel'] == 'beta':
            patch_parts['prerelversion'] += 1

        elif patch_parts['prerel'] == 'dev':
            patch_parts['prerel'] = 'beta'
            patch_parts['prerelversion'] = 0

        else:
            raise Exception('Can only bump from beta or no prerel version')

        new_patch = format_patch(patch_parts)

    return new_major, new_minor, new_patch


def write_version(major, minor, patch):
    """Update Home Assistant constant file with new version."""
    with open('homeassistant/const.py') as fil:
        content = fil.read()

    content = re.sub('MAJOR_VERSION = .*\n',
                     'MAJOR_VERSION = {}\n'.format(major),
                     content)
    content = re.sub('MINOR_VERSION = .*\n',
                     'MINOR_VERSION = {}\n'.format(minor),
                     content)
    content = re.sub('PATCH_VERSION = .*\n',
                     "PATCH_VERSION = '{}'\n".format(patch),
                     content)

    with open('homeassistant/const.py', 'wt') as fil:
        content = fil.write(content)


def main():
    """Execute script."""
    parser = argparse.ArgumentParser(
        description="Bump version of Home Assistant")
    parser.add_argument(
        'type',
        help="The type of the bump the version to.",
        choices=['beta', 'dev', 'release_patch'],
    )
    arguments = parser.parse_args()
    write_version(*bump_version(const.MAJOR_VERSION, const.MINOR_VERSION,
                                const.PATCH_VERSION, arguments.type))


def test_bump_version():
    """Make sure it all works."""
    assert bump_version(0, 56, '0', 'beta') == \
        (0, 56, '1.beta0')
    assert bump_version(0, 56, '0.beta3', 'beta') == \
        (0, 56, '0.beta4')
    assert bump_version(0, 56, '0.dev0', 'beta') == \
        (0, 56, '0.beta0')

    assert bump_version(0, 56, '3', 'dev') == \
        (0, 57, '0.dev0')
    assert bump_version(0, 56, '0.beta3', 'dev') == \
        (0, 57, '0.dev0')
    assert bump_version(0, 56, '0.dev0', 'dev') == \
        (0, 56, '0.dev1')

    assert bump_version(0, 56, '3', 'release_patch') == \
        (0, 56, '4')
    assert bump_version(0, 56, '3.beta3', 'release_patch') == \
        (0, 56, '3')
    assert bump_version(0, 56, '0.dev0', 'release_patch') == \
        (0, 56, '0')


if __name__ == '__main__':
    main()
