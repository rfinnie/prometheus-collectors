# SPDX-FileComment: dump1090-collector
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample dump1090.yaml:
#
# stations:
# - name: piaware
#   url: http://piaware.example.lan/skyaware/data/aircraft.json

import platform
import sys

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

        for station in self.config["stations"]:
            if not isinstance(station["url"], (list, tuple, set)):
                station["url"] = [station["url"]]

        self.create_instrument(
            "counter", "reports", description="Total reports received"
        )
        vals = [
            ("messages.received", "Number of raw messages received"),
            (
                "airborne.aircraft.total",
                "Total number of current airborne aircraft seen",
            ),
            (
                "airborne.aircraft.positions",
                "Number of current airborne aircraft seen with positions",
            ),
            (
                "airborne.aircraft.mlat",
                "Number of current airborne aircraft seen with multilateration",
            ),
            (
                "airborne.aircraft.tisb",
                "Number of current airborne aircraft seen with TIS-B information",
            ),
            (
                "airborne.aircraft.uat",
                "Number of current airborne aircraft seen via UAT",
            ),
            (
                "airborne.aircraft.squawk",
                "Number of current airborne aircraft seen squawking",
            ),
            (
                "airborne.aircraft.ground",
                "Number of current aircraft reported on ground",
            ),
            (
                "airborne.aircraft.messages",
                "Number of messages received by currently seen airborne aircraft",
            ),
            ("station.time.seconds", "Station collection time"),
        ]
        for k, h in vals:
            self.create_instrument("gauge", k, description=h)

    def collect_metrics(self):
        for station in self.config["stations"]:
            self.collect_station(station)

    def collect_station(self, station):
        aircraft = []
        messages = 0
        station_time = 0
        for url in station["url"]:
            r = self.r_session.get(url)
            r.raise_for_status()
            j = r.json()
            messages += j["messages"]
            aircraft.extend(
                [x for x in j["aircraft"] if x["seen"] < self.seen_fresh_time]
            )
            station_time = j["now"]

        labels = {"station": station["name"]}
        vals = [
            ("messages.received", messages),
            (
                "airborne.aircraft.total",
                len(aircraft),
            ),
            (
                "airborne.aircraft.positions",
                len(
                    [
                        x
                        for x in aircraft
                        if "lat" in x
                        and "seen_pos" in x
                        and x["seen_pos"] < self.seen_pos_fresh_time
                    ]
                ),
            ),
            (
                "airborne.aircraft.mlat",
                len([x for x in aircraft if x.get("mlat")]),
            ),
            (
                "airborne.aircraft.tisb",
                len([x for x in aircraft if x.get("tisb")]),
            ),
            (
                "airborne.aircraft.uat",
                len([x for x in aircraft if x.get("uat_version")]),
            ),
            (
                "airborne.aircraft.squawk",
                len([x for x in aircraft if x.get("squawk")]),
            ),
            (
                "airborne.aircraft.ground",
                len([x for x in aircraft if x.get("alt_baro") == "ground"]),
            ),
            (
                "airborne.aircraft.messages",
                sum([x["messages"] for x in aircraft if "messages" in x]),
            ),
            ("station.time.seconds", station_time),
        ]
        for k, v in vals:
            self.instruments[k].set(v, labels)
        self.instruments["reports"].add(1, labels)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
