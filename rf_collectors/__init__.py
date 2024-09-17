# SPDX-FileComment: collectors-collector
# SPDX-FileCopyrightText: Copyright (C) 2021-2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import argparse
import logging
import math
import os
import pathlib
import random
import sys
import time

import yaml

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporter_http,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporter_grpc,
)


class BaseMetrics:
    prefix = "base"
    interval = 60
    needs_config = False
    needs_requests = False
    needs_periodic_export = False

    args = None
    config = None
    instruments = {}

    def pre_setup(self):
        pass

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
            "/etc/rf-collectors/{}.yaml".format(self.prefix)
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
        self.logger = logging.getLogger(self.prefix)
        self.args = self.parse_args(argv)
        self.interval = self.args.interval
        self.config = self.load_config()

        self.pre_setup()

        resource = Resource(attributes={SERVICE_NAME: "rf-collectors"})
        if self.config.get("exporter_type") == "http":
            self.exporter = OTLPMetricExporter_http(
                endpoint=self.config["exporter_endpoint"]
            )
        elif self.config.get("exporter_type") == "grpc":
            self.exporter = OTLPMetricExporter_grpc(
                endpoint=self.config["exporter_endpoint"]
            )
        else:
            self.exporter = ConsoleMetricExporter()
        if self.needs_periodic_export:
            self.metric_reader = PeriodicExportingMetricReader(self.exporter, self.args.interval * 1000)
        else:
            self.metric_reader = PeriodicExportingMetricReader(self.exporter, math.inf)
        provider = MeterProvider(metric_readers=[self.metric_reader], resource=resource)
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter(self.prefix)
        self.create_instrument(
            "histogram",
            "collection.duration",
            unit="seconds",
            description="Time spent collecting metrics",
        )
        self.create_instrument(
            "counter",
            "collection.errors",
            unit="1",
            description="Errors encountered while collecting metrics",
        )

        if self.needs_requests:
            import requests

            self.requests = requests
            self.r_session = requests.Session()

        self.setup()

        self.main_loop()

    def main_loop(self):
        while True:
            self.logger.debug("Beginning collection run")
            try:
                begin = time.time()
                self.collect_metrics()
                end = time.time()
                self.instruments["collection.duration"].record(end - begin)
            except Exception:
                self.logger.exception("Encountered an error during collection")
                self.instruments["collection.errors"].add(1)

            self.metric_reader.force_flush()

            sleep = random.uniform(
                self.interval * (1 - (self.args.interval_randomize / 100.0)),
                self.interval * (1 + (self.args.interval_randomize / 100.0)),
            )
            self.logger.debug("Sleeping for {}".format(sleep))
            time.sleep(sleep)

    def create_instrument(self, instrument_type, name, **kwargs):
        full_name = "{}.{}".format(self.prefix, name)
        if instrument_type == "counter":
            m = self.meter.create_counter
        elif instrument_type == "gauge":
            m = self.meter.create_gauge
        elif instrument_type == "histogram":
            m = self.meter.create_histogram
        else:
            raise ValueError(instrument_type)
        self.instruments[name] = m(full_name, **kwargs)
