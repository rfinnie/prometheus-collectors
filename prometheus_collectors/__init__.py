# SPDX-FileComment: prometheus-collectors
# SPDX-FileCopyrightText: Copyright (C) 2021-2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import argparse
import binascii
import logging
import os
import pathlib
import random
import sys
import time

import prometheus_client
import yaml


class BaseMetrics:
    prefix = "base"
    interval = 60
    registry = None
    args = None
    config = None
    needs_config = False
    collection_duration = None
    collection_errors = None

    def setup(self):
        pass

    def collect_metrics(self):
        pass

    def metrics_args(self, parser):
        pass

    def parse_args(self, argv=None):
        def _optional_path(string):
            return pathlib.Path(string) if string else None

        if argv is None:
            argv = sys.argv

        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog=os.path.basename(argv[0]),
        )

        action_group = parser.add_mutually_exclusive_group(required=True)
        action_group.add_argument(
            "--http-daemon", action="store_true", help="Run an HTTP daemon"
        )
        action_group.add_argument(
            "--prom-daemon", action="store_true", help="Run a .prom-writing daemon"
        )
        action_group.add_argument(
            "--write", action="store_true", help="Write a .prom file"
        )
        action_group.add_argument(
            "--dump", action="store_true", help="Dump a .prom file to stdout"
        )

        parser.add_argument(
            "--prom-file",
            type=pathlib.Path,
            default="/var/lib/prometheus/node-exporter/{}.prom".format(self.prefix),
            help=".prom file to write",
            metavar="FILE",
        )
        parser.add_argument(
            "--http-port",
            type=int,
            default=(
                (binascii.crc32(self.prefix.encode("UTF-8")) & (65535 - 49152)) + 49152
            ),
            help="HTTP port number",
            metavar="PORT",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=self.interval,
            help="Seconds between collections",
            metavar="SECONDS",
        )
        parser.add_argument(
            "--interval-randomize",
            type=float,
            default=10,
            help="Randomize interval by +/- PERCENT percent, 0 to disable",
            metavar="PERCENT",
        )
        default_config_file = pathlib.Path(
            "/etc/prometheus/collectors/{}.yaml".format(self.prefix)
        )
        if (not self.needs_config) and (not default_config_file.exists()):
            default_config_file = None
        parser.add_argument(
            "--config",
            type=_optional_path,
            default=default_config_file,
            help="YAML configuration file",
            metavar="FILE",
        )

        self.metrics_args(parser)
        return parser.parse_args(args=argv[1:])

    def load_config(self):
        if not self.args.config:
            return {}
        with self.args.config.open() as f:
            return yaml.safe_load(f)

    def main(self, argv=None):
        logging_level = logging.DEBUG if sys.stdin.isatty() else logging.INFO
        logging.basicConfig(level=logging_level)
        self.args = self.parse_args(argv)
        self.interval = self.args.interval
        self.config = self.load_config()
        self.metrics = {}
        self.metrics_labels = {}
        if self.args.http_daemon:
            self.registry = prometheus_client.REGISTRY
            self.collection_duration = prometheus_client.Summary(
                "{}_collection_duration_seconds".format(self.prefix),
                "Time spent collecting metrics",
                registry=self.registry,
            )
            self.collection_errors = prometheus_client.Counter(
                "{}_collection_errors_total".format(self.prefix),
                "Errors encountered while collecting metrics",
                registry=self.registry,
            )
        else:
            self.registry = prometheus_client.CollectorRegistry()
        self.setup()

        if self.args.http_daemon:
            prometheus_client.start_http_server(
                self.args.http_port, registry=self.registry
            )
            logging.info("HTTP server running on port {}".format(self.args.http_port))

        self.main_loop()

    def main_loop(self):
        while True:
            logging.debug("Beginning collection run")
            try:
                if self.collection_duration:
                    with self.collection_duration.time():
                        self.collect_metrics()
                else:
                    self.collect_metrics()
            except Exception:
                if self.args.write or self.args.dump:
                    raise
                else:
                    logging.exception("Encountered an error during collection")
                if self.collection_errors:
                    self.collection_errors.inc()

            if self.args.prom_daemon or self.args.write:
                prometheus_client.write_to_textfile(
                    str(self.args.prom_file), registry=self.registry
                )
            elif self.args.dump:
                output = prometheus_client.generate_latest(registry=self.registry)
                print(output.decode("UTF-8"), end="")
            if self.args.write or self.args.dump:
                return

            if self.args.http_daemon or self.args.prom_daemon:
                sleep = random.uniform(
                    self.interval * (1 - (self.args.interval_randomize / 100.0)),
                    self.interval * (1 + (self.args.interval_randomize / 100.0)),
                )
                logging.debug("Sleeping for {}".format(sleep))
                time.sleep(sleep)

    def metric(self, key, labels, help="No help", data_type=prometheus_client.Gauge):
        if key not in self.metrics:
            self.metrics_labels[key] = sorted(labels.keys())
            self.metrics[key] = data_type(
                "{}_{}".format(self.prefix, key),
                help,
                self.metrics_labels[key],
                registry=self.registry,
            )
        label_values = []
        for label_name in self.metrics_labels[key]:
            if label_name in labels:
                label_values.append(labels[label_name])
            else:
                label_values.append("")
        return self.metrics[key].labels(*label_values)
