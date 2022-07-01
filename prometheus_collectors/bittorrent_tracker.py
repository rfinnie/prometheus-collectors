# SPDX-FileComment: prometheus-bittorrent-tracker
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample things.yaml:
#
# sites:
# - name: example
#   url: https://tracker.example.com

import logging
import sys

from prometheus_client import Gauge
import requests

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "bttrack"
    needs_config = True

    def setup(self):
        label_names = ["site"]
        self.metrics = {}

        defs = [
            ("torrents", Gauge, "Torrents seen"),
            ("torrents_active", Gauge, "Torrents currently active"),
            ("peers_all", Gauge, "All reported peers"),
            ("peers_seeder_only", Gauge, "Peers currently only seeding"),
            ("peers_leecher_only", Gauge, "Peers currently only leeching"),
            ("peers_seeder_and_leecher", Gauge, "Peers currently seeding and leeching"),
            ("peers_ipv4", Gauge, "Peers reported via IPv4"),
            ("peers_ipv6", Gauge, "Peers reported via IPv6"),
            ("clients", Gauge, "Unique client agents"),
            ("client_versions", Gauge, "Unique client agent versions"),
        ]

        for k, t, h in defs:
            self.metrics[k] = t(
                "{}_{}".format(self.prefix, k), h, label_names, registry=self.registry
            )

    def collect_site(self, site):
        r = requests.get("{}/stats.json".format(site["url"]))
        r.raise_for_status()
        j = r.json()

        labels = [site["name"]]

        for g, k, f in [
            ("torrents", "torrents", float),
            ("torrents_active", "activeTorrents", float),
            ("peers_all", "peersAll", float),
            ("peers_seeder_only", "peersSeederOnly", float),
            ("peers_leecher_only", "peersLeecherOnly", float),
            ("peers_seeder_and_leecher", "peersSeederAndLeecher", float),
            ("peers_ipv4", "peersIPv4", float),
            ("peers_ipv6", "peersIPv6", float),
            ("clients", "clients", lambda v: len(v)),
            ("client_versions", "clients", lambda v: sum([len(x) for x in v.values()])),
        ]:
            try:
                v = f(j[k])
            except KeyError:
                pass
            except Exception:
                logging.exception(
                    "Encountered an attribute error for {}".format(site["name"])
                )
                pass
            else:
                self.metrics[g].labels(*labels).set(v)

    def collect_metrics(self):
        for site in self.config["sites"]:
            self.collect_site(site)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
