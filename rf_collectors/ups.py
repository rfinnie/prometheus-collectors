# SPDX-FileComment: ups-collector
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample ups.yaml:
#
# upses:
# - host: 127.0.0.1
#   port: 3551

import re
import socket
import struct
import sys

import dateutil.parser
import dateutil.tz

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "ups"
    matches = {
        "LINEV": ("line", "volts"),
        "LOADPCT": ("load", "percent"),
        "BCHARGE": ("battery.charge", "percent"),
        "TIMELEFT": ("time.left", "seconds"),
        "MBATTCHG": ("minimum.battery.charge", "percent"),
        "MINTIMEL": ("minimum.time.left", "seconds"),
        "MAXTIME": ("maximum.time", "seconds"),
        "LOTRANS": ("low.transfer", "volts"),
        "HITRANS": ("high.transfer", "volts"),
        "ALARMDEL": ("alarm.delay", "seconds"),
        "BATTV": ("battery", "volts"),
        "NUMXFERS": ("transfer.count", ""),
        "TONBATT": ("on.battery", "seconds"),
        "CUMONBATT": ("cumulative.on.battery", "seconds"),
        "NOMINV": ("nominal.input", "volts"),
        "NOMBATTV": ("nominal.battery", "volts"),
        "NOMPOWER": ("nominal.power", "watts"),
    }

    def setup(self):
        self.create_instrument(
            "gauge",
            "device.time",
            unit="seconds",
            description="UPS device check-in time",
        )
        self.create_instrument(
            "counter", "reports", description="Total reports received"
        )

        for status_key in self.matches:
            metric_name, metric_unit = self.matches[status_key]
            self.create_instrument(
                "gauge",
                metric_name,
                unit=metric_unit,
                description="UPS {}".format(status_key),
            )

        if "upses" not in self.config:
            self.config["upses"] = [{"host": "127.0.0.1", "port": 3551}]

    def get_apc(self, ups):
        apc_data = b""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ups["host"], ups["port"]))

        sock.send(struct.pack("!H", 6))
        sock.send(b"status")
        while True:
            data = sock.recv(2)
            if data == b"":
                sock.close()
                sock = None
                apc_data = b""
                break
            line_len = struct.unpack("!H", data)[0]
            if line_len == 0:
                break
            data = sock.recv(line_len)
            if data == b"":
                sock.close()
                sock = None
                apc_data = b""
                break
            apc_data += data
        return apc_data.decode("UTF-8")

    def collect_metrics(self):
        for ups in self.config["upses"]:
            self.collect_ups(ups)

    def collect_ups(self, ups):
        if "port" not in ups:
            ups["port"] = 3551

        out = {}

        text = self.get_apc(ups)
        if not text:
            return

        re_line = re.compile(r"^([A-Z ]+?) *: (.*?) *$", re.M)
        kv = {k: v for (k, v) in re_line.findall(text)}
        for k, v in kv.items():
            if k not in self.matches:
                continue
            (m_name, m_suffix) = self.matches[k]
            if k == "ALARMDEL" and v == "No alarm":
                v = "0 Seconds"
            if m_suffix:
                v_suffix = v.split(" ")[-1].lower()
                v = " ".join(v.split(" ")[0:-1])
                if m_suffix == "seconds":
                    if v_suffix == "hours":
                        v = str(float(v) * 3600)
                        v_suffix = "seconds"
                    elif v_suffix == "minutes":
                        v = str(float(v) * 60)
                        v_suffix = "seconds"
                if v_suffix != m_suffix:
                    print("Unexpected: {} {} {}".format(k, v_suffix, m_suffix))
                    continue
            fullname = m_name
            if m_suffix:
                fullname = "{}_{}".format(fullname, m_suffix)
            out[k] = v

        labels = {"model": kv["MODEL"], "name": kv["UPSNAME"], "serial": kv["SERIALNO"]}
        for k, v in out.items():
            self.instruments[self.matches[k][0]].set(v, labels)
        apc_date = dateutil.parser.parse(kv["DATE"])
        if apc_date.tzinfo is None:
            apc_date = apc_date.astimezone(dateutil.tz.tzlocal())
        self.instruments["device.time"].set(float(apc_date.strftime("%s")), labels)
        self.instruments["reports"].add(1, labels)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
