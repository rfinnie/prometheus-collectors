# SPDX-FileComment: prometheus-sunpower - SunPower PVS5/PVS6
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import sys

import requests

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "sunpower"

    meter_defs = [
        ("net_ltea_3phsum_kwh", "Net cumulative energy across all three phases"),
        ("p_3phsum_kw", "Average real power"),
        ("q_3phsum_kvar", "Cumulative reactive power across all three phases"),
        ("s_3phsum_kva", "Cumulative apparent power across all three phases"),
        ("tot_pf_rto", "Power factor ratio"),
        ("freq_hz", "Operating frequency"),
        ("i1_a", "Supply current on CT1 lead"),
        ("i2_a", "Supply current on CT2 lead"),
        ("v1n_v", "Supply voltage CT1 leal, relative to neutral"),
        ("v2n_v", "Supply voltage CT2 lead, relative to neutral"),
        ("v12_v", "Supply voltage sum across CT1 and CT2 leads"),
        (
            "p1_kw",
            "Lead 1 average power, can be positive (excess back to utility) or negative (used from utility)",
        ),
        (
            "p2_kw",
            "Lead 2 average power, can be positive (excess back to utility) or negative (used from utility)",
        ),
        (
            "neg_ltea_3phsum_kwh",
            "Cumulative energy across all three phases, consumed from utility",
        ),
        (
            "pos_ltea_3phsum_kwh",
            "Cumulative energy across all three phases, supplied to utility",
        ),
    ]
    inverter_defs = [
        ("ltea_3phsum_kwh", "Total energy"),
        ("p_3phsum_kw", "AC power"),
        ("vln_3phavg_v", "AC voltage"),
        ("i_3phsum_a", "AC current"),
        ("p_mppt1_kw", "DC power for Maximum Power Point Tracking"),
        ("v_mppt1_v", "DC voltage for Maximum Power Point Tracking"),
        ("i_mppt1_a", "DC current for Maximum Power Point Tracking"),
        ("t_htsnk_degc", "Heatsink temperature"),
        ("freq_hz", "Operating frequency"),
    ]

    def setup(self):
        self.device_url = self.config.get(
            "device_url", "http://172.27.153.1/cgi-bin/dl_cgi?Command=DeviceList"
        )
        self.api_timeout = self.config.get("api_timeout", 15)

    def collect_metrics(self):
        r = requests.get(self.device_url, timeout=self.api_timeout)
        r.raise_for_status()
        j = r.json()

        pvs_serial = [x["SERIAL"] for x in j["devices"] if x["DEVICE_TYPE"] == "PVS"][0]

        for device in j["devices"]:
            if device["DEVICE_TYPE"] == "Power Meter":
                device_prefix = "meter"
                device_defs = self.meter_defs
            elif device["DEVICE_TYPE"] == "Inverter":
                device_prefix = "inverter"
                device_defs = self.inverter_defs
            else:
                continue
            labels = {
                "pvs_serial": pvs_serial,
                "serial": device["SERIAL"],
            }
            for k, k_help in device_defs:
                try:
                    v = float(device[k])
                except KeyError:
                    pass
                except Exception:
                    self.logger.exception(
                        "Encountered an attribute error for {}".format(device)
                    )
                    pass
                else:
                    self.metric("{}_{}".format(device_prefix, k), labels, k_help).set(v)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
