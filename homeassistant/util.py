""" Helper methods for various modules. """

import re

RE_SANITIZE_FILENAME = re.compile(r"(~|(\.\.)|/|\+)")
RE_SLUGIFY = re.compile(r'[^A-Za-z0-9_]+')


def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return RE_SANITIZE_FILENAME.sub("", filename)


def slugify(text):
    """ Slugifies a given text. """
    text = text.strip().replace(" ", "_")

    return RE_SLUGIFY.sub("", text)
