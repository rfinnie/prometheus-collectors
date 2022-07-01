# SPDX-FileComment: prometheus-livepatch
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import subprocess
import sys

from prometheus_client import Gauge
import yaml

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "livepatch"
    interval = 3600

    def setup(self):
        self.metrics = {}
        self.metrics["info"] = Gauge(
            "{}_info".format(self.prefix),
            "Livepatch information",
            ["client_version", "architecture", "cpu_model"],
            registry=self.registry,
        )
        self.metrics["last_check_time"] = Gauge(
            "{}_last_check_time".format(self.prefix),
            "Time livepatch patches were checked (epoch)",
            registry=self.registry,
        )
        self.metrics["kernel_running"] = Gauge(
            "{}_kernel_running".format(self.prefix),
            "Whether a kernel is currently running, plus associated patch info",
            ["kernel", "check_state", "patch_state", "version"],
            registry=self.registry,
        )

    def collect_metrics(self):
        status_text = subprocess.check_output(
            ["/snap/bin/canonical-livepatch", "status", "--format", "yaml"]
        )
        status = yaml.safe_load(status_text)
        self.metrics["info"].labels(
            status["client-version"],
            status["architecture"],
            status["cpu-model"].strip(),
        ).set(1)
        self.metrics["last_check_time"].set(status["last-check"].timestamp())
        for k in status["status"]:
            if "kernel" not in k:
                continue
            if "livepatch" not in k:
                continue
            self.metrics["kernel_running"].labels(
                k["kernel"].strip(),
                k["livepatch"]["checkState"],
                k["livepatch"]["patchState"],
                k["livepatch"]["version"],
            ).set(int(k["running"]))


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
