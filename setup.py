#!/usr/bin/env python3

from setuptools import setup


setup(
    name="rf-collectors",
    description="My personal collection of data collectors",
    author="Ryan Finnie",
    author_email="ryan@finnie.org",
    license="MPL-2.0",
    packages=["rf_collectors"],
    entry_points={
        "console_scripts": [
            "ambientweather-collector = rf_collectors.ambientweather:main",
            "bittorrent-collector-tracker = rf_collectors.bittorrent_tracker:main",
            "dump1090-collector = rf_collectors.dump1090:main",
            "finnix-collector-mirrors = rf_collectors.finnix_mirrors:main",
            "gps-collector = rf_collectors.gps:main",
            "sslchecker-collector = rf_collectors.sslchecker:main",
            "sunpower-collector = rf_collectors.sunpower:main",
            "things-collector = rf_collectors.things:main",
            "ups-collector = rf_collectors.ups:main",
        ]
    },
)
