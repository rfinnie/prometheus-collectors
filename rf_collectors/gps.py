# SPDX-FileComment: gps-collector
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample gps.yaml:
#
# host: 127.0.0.1
# port: 2947

import json
import socket
import sys
import time

import dateutil.parser

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "gps"
    needs_periodic_export = True
    gpsd_host = "127.0.0.1"
    gpsd_port = 2947
    sock = None

    def setup(self):
        self.gpsd_host = self.config.get("gpsd_host", "127.0.0.1")
        self.gpsd_port = self.config.get("gpsd_port", 2947)

        self.metrics_defs = {
            "PPS": {
                "_clock": (
                    "pps.clock.seconds",
                    "System wall clock, seconds since epoch",
                ),
                "_real": ("pps.real.seconds", "PPS source clock, seconds since epoch"),
                "precision": (
                    "pps.precision.gps",
                    "NTP style estimate of PPS precision",
                ),
            },
            "SKY": {
                "_unused_satellites": (
                    "sky.unused.satellites",
                    "Satellites currently not being used",
                ),
                "_used_satellites": (
                    "sky.used.satellites",
                    "Satellites currently being used",
                ),
                "gdop": (
                    "sky.geometric.dop",
                    "Geometric (hyperspherical) dilution of precision (dimensionless)",
                ),
                "hdop": (
                    "sky.horizontal.dop",
                    "Horizontal dilution of precision (dimensionless)",
                ),
                "pdop": (
                    "sky.position.dop",
                    "Position (spherical/3D) dilution of precision (dimensionless)",
                ),
                "tdop": ("sky.time.dop", "Time dilution of precision (dimensionless)"),
                "vdop": (
                    "sky.vertical.dop",
                    "Vertical (altitude) dilution of precision (dimensionless)",
                ),
                "xdop": (
                    "sky.longitudinal.dop",
                    "Longitudinal (X) dilution of precision (dimensionless)",
                ),
                "ydop": (
                    "sky.latitudinal.dop",
                    "Latitudinal (Y) dilution of precision (dimensionless)",
                ),
            },
            "TPV": {
                "_time": ("tpv.time.seconds", "GPS time"),
                "alt": ("tpv.altitude.meters", "Altitude in meters"),
                "climb": ("tpv.climb.mps", "Climb or sink rate, meters per second"),
                "epc": (
                    "tpv.climb.error.mps",
                    "Estimated climb error in meters per second",
                ),
                "eps": (
                    "tpv.speed.error.mps",
                    "Estimated speed error in meters per second",
                ),
                "ept": (
                    "tpv.time.error.seconds",
                    "Estimated timestamp error in seconds",
                ),
                "epv": (
                    "tpv.vertical.error.meters",
                    "Estimated vertical error in meters",
                ),
                "epx": (
                    "tpv.longitude.error.meters",
                    "Longitude error estimate in meters",
                ),
                "epy": (
                    "tpv.latitude.error.meters",
                    "Latitude error estimate in meters",
                ),
                "mode": ("tpv.mode", "NMEA mode"),
                "speed": ("tpv.speed.mps", "Speed over ground, meters per second"),
                "track": (
                    "tpv.course.degrees",
                    "Course over ground, degrees from true north",
                ),
            },
        }
        if self.config.get("collect_position", True):
            self.metrics_defs["TPV"]["lat"] = (
                "tpv.latitude.degrees",
                "Latitude in degrees",
            )
            self.metrics_defs["TPV"]["lon"] = (
                "tpv.longitude.degrees",
                "Longitude in degrees",
            )

        self.create_instrument(
            "counter", "messages", description="Total messages received"
        )
        for x in self.metrics_defs:
            for y in self.metrics_defs[x]:
                k, h = self.metrics_defs[x][y]
                self.create_instrument("gauge", k, description=h)

    def process_message(self, buf):
        try:
            j = json.loads(buf)
        except Exception:
            return
        if "class" not in j:
            return
        device = j.get("device", "")
        labels = {"device": device}
        self.instruments["messages"].add(
            1, {"device": device, "class": j["class"]}
        )
        if j["class"] in self.metrics_defs:
            for k, g in self.metrics_defs[j["class"]].items():
                if k not in j:
                    continue
                self.instruments[g[0]].set(j[k], labels)
        if j["class"] == "PPS":
            m = self.metrics_defs["PPS"]["_clock"]
            self.instruments[m[0]].set(
                j["clock_sec"] + (j["clock_nsec"] / 1000000000), labels
            )
            m = self.metrics_defs["PPS"]["_real"]
            self.instruments[m[0]].set(
                j["real_sec"] + (j["real_nsec"] / 1000000000), labels
            )
        elif j["class"] == "SKY":
            m = self.metrics_defs["SKY"]["_unused_satellites"]
            self.instruments[m[0]].set(
                len([x["PRN"] for x in j["satellites"] if not x["used"]]), labels
            )
            m = self.metrics_defs["SKY"]["_used_satellites"]
            self.instruments[m[0]].set(
                len([x["PRN"] for x in j["satellites"] if x["used"]]), labels
            )
        elif j["class"] == "TPV" and j.get("time"):
            m = self.metrics_defs["TPV"]["_time"]
            self.instruments[m[0]].set(
                dateutil.parser.parse(j["time"]).timestamp(), labels
            )

    def main_loop_connection(self):
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.gpsd_host, self.gpsd_port))
            self.sock.send(b'?WATCH={"enable":true,"json":true};\n')
        data = self.sock.recv(1024)
        if data == b"":
            raise ValueError("gpsd EOF")
        return data

    def main_loop(self):
        while True:
            try:
                data = self.main_loop_connection()
            except Exception as e:
                if not isinstance(e, ConnectionRefusedError):
                    # Silently ignore connection refused
                    self.logger.exception("Error during gpsd connection")
                self.collection_errors.inc()
                self.sock.close()
                self.sock = None
                time.sleep(1)
                continue
            try:
                begin = time.time()
                self.process_message(data)
                end = time.time()
                self.instruments["collection.duration"].record(end - begin)
            except Exception:
                self.logger.exception("Encountered an error during collection")
                self.instruments["collection.errors"].add(1)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
