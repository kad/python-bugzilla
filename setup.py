#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-
# vim: sw=4 ts=4 expandtab ai
#
# $Id: setup.py 1871 2007-06-25 17:32:56Z kanevski $

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


version = "0.14"

setup (name = "bugzilla",
    description = "Access to Bugzilla",
    version = version,
    author = "Alexandr D. Kanevskiy",
    author_email = "packages@bifh.org",
    url = "http://bifh.org/wiki/python-bugzilla",
    license = "GPL",
    packages = ['bugzilla'],
    long_description = "Python library for accessing information in Bugzilla",
    keywords = "python bugzilla",
    platforms="Python 2.3 and later.",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Operating System :: Unix",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ]
    )

