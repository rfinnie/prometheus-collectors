#!/usr/bin/env python3

from setuptools import setup


setup(
    name="prometheus-collectors",
    description="My personal collection of Prometheus collectors",
    author="Ryan Finnie",
    author_email="ryan@finnie.org",
    license="MPL-2.0",
    packages=["prometheus_collectors"],
    entry_points={
        "console_scripts": [
            "prometheus-bittorrent-tracker = prometheus_collectors.bittorrent_tracker:main",
            "prometheus-dump1090 = prometheus_collectors.dump1090:main",
            "prometheus-finnix-mirrors = prometheus_collectors.finnix_mirrors:main",
            "prometheus-gps = prometheus_collectors.gps:main",
            "prometheus-livepatch = prometheus_collectors.livepatch:main",
            "prometheus-sslchecker = prometheus_collectors.sslchecker:main",
            "prometheus-sunpower = prometheus_collectors.sunpower:main",
            "prometheus-things = prometheus_collectors.things:main",
            "prometheus-ups = prometheus_collectors.ups:main",
        ]
    },
)
