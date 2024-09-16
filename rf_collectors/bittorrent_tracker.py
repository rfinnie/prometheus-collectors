# SPDX-FileComment: bittorrent-collector-tracker
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample bttrack.yaml:
#
# sites:
# - name: example
#   url: https://tracker.example.com

import sys

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "bttrack"
    needs_config = True
    needs_requests = True

    def setup(self):
        defs = [
            ("torrents", "gauge", "Torrents seen"),
            ("torrents.active", "gauge", "Torrents currently active"),
            ("peers.all", "gauge", "All reported peers"),
            ("peers.seeder_only", "gauge", "Peers currently only seeding"),
            ("peers.leecher_only", "gauge", "Peers currently only leeching"),
            ("peers.seeder_and_leecher", "gauge", "Peers currently seeding and leeching"),
            ("peers.ipv4", "gauge", "Peers reported via IPv4"),
            ("peers.ipv6", "gauge", "Peers reported via IPv6"),
            ("clients", "gauge", "Unique client agents"),
            ("client.versions", "gauge", "Unique client agent versions"),
        ]

        for k, t, h in defs:
            self.create_instrument(t, k, description=h)

    def collect_site(self, site):
        r = self.r_session.get("{}/stats.json".format(site["url"]))
        r.raise_for_status()
        j = r.json()

        labels = {"site": site["name"]}

        for g, k, f in [
            ("torrents", "torrents", float),
            ("torrents.active", "activeTorrents", float),
            ("peers.all", "peersAll", float),
            ("peers.seeder_only", "peersSeederOnly", float),
            ("peers.leecher_only", "peersLeecherOnly", float),
            ("peers.seeder_and_leecher", "peersSeederAndLeecher", float),
            ("peers.ipv4", "peersIPv4", float),
            ("peers.ipv6", "peersIPv6", float),
            ("clients", "clients", lambda v: len(v)),
            ("client.versions", "clients", lambda v: sum([len(x) for x in v.values()])),
        ]:
            try:
                v = f(j[k])
            except KeyError:
                pass
            except Exception:
                self.logger.exception(
                    "Encountered an attribute error for {}".format(site["name"])
                )
                pass
            else:
                self.instruments[g].set(v, labels)

    def collect_metrics(self):
        for site in self.config["sites"]:
            self.collect_site(site)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
