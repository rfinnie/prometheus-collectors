# SPDX-FileComment: prometheus-dump1090
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample dump1090.yaml:
#
# stations:
# - name: piaware
#   url: http://piaware.example.lan/skyaware/data/aircraft.json

import platform
import sys

from prometheus_client import Counter

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "dump1090"
    needs_requests = True

    def setup(self):
        # < 58 and < 60 mirrors the logic of the PiAware 5.0 JS UI
        self.seen_fresh_time = self.config.get("seen_fresh_time", 58)
        self.seen_pos_fresh_time = self.config.get("seen_pos_fresh_time", 60)

        if "stations" not in self.config:
            self.config["stations"] = [
                {
                    "name": platform.node(),
                    "url": "http://127.0.0.1/skyaware/data/aircraft.json",
                }
            ]

    def collect_metrics(self):
        for station in self.config["stations"]:
            self.collect_station(station)

    def collect_station(self, station):
        r = self.r_session.get(station["url"])
        r.raise_for_status()
        j = r.json()
        aircraft = [x for x in j["aircraft"] if x["seen"] < self.seen_fresh_time]

        labels = {"station": station["name"]}
        vals = [
            ("messages_received", j["messages"], "Number of raw messages received"),
            (
                "airborne_aircraft_total",
                len(aircraft),
                "Total number of current airborne aircraft seen",
            ),
            (
                "airborne_aircraft_positions",
                len(
                    [
                        x
                        for x in aircraft
                        if "lat" in x
                        and "seen_pos" in x
                        and x["seen_pos"] < self.seen_pos_fresh_time
                    ]
                ),
                "Number of current airborne aircraft seen with positions",
            ),
            (
                "airborne_aircraft_mlat",
                len([x for x in aircraft if x.get("mlat")]),
                "Number of current airborne aircraft seen with multilateration",
            ),
            (
                "airborne_aircraft_tisb",
                len([x for x in aircraft if x.get("tisb")]),
                "Number of current airborne aircraft seen with TIS-B information",
            ),
            (
                "airborne_aircraft_squawk",
                len([x for x in aircraft if x.get("squawk")]),
                "Number of current airborne aircraft seen squawking",
            ),
            (
                "airborne_aircraft_ground",
                len([x for x in aircraft if x.get("alt_baro") == "ground"]),
                "Number of current aircraft reported on ground",
            ),
            (
                "airborne_aircraft_messages",
                sum([x["messages"] for x in aircraft if "messages" in x]),
                "Number of messages received by currently seen airborne aircraft",
            ),
            ("station_time_seconds", j["now"], "Station collection time"),
        ]
        for k, v, h in vals:
            self.metric(k, labels, h).set(v)
        self.metric(
            "reports_total", labels, "Total reports received", data_type=Counter
        ).inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
