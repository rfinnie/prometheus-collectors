# SPDX-FileComment: prometheus-sslchecker
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample sslchecker.yaml:
#
# hosts:
# - hostname: www.example.com
#   port: 443
# - hostname: www.implicit-443.example.com
# - hostname: smtp.example.com
#   port: 25
#   type: starttls
# - hostname: ftp.example.com
#   port: 21
#   type: auth_tls
# - hostname: imap.example.com
#   port: 993
# - hostname: mumble.example.com
#   port: 64738

import datetime
import random
import socket
import ssl
import sys
import time

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "sslchecker"
    needs_config = True
    full_check_complete = False
    spread_interval = 14400

    def collect_metrics(self):
        if self.full_check_complete:
            hosts = []
            chance = 1.0 / (self.spread_interval / self.interval)
            for host in self.config["hosts"]:
                if random.random() < chance:
                    hosts.append(host)
            self.logger.debug("Checking {} random host(s)".format(len(hosts)))
        else:
            hosts = self.config["hosts"]
            self.logger.debug("Doing full check of all hosts")

        skip_labels = self.config.get("skip_labels", [])
        for host in hosts:
            hostname = host["hostname"]
            if "port" not in host:
                host["port"] = 443
            port = host["port"]
            base_labels = {"server_hostname": hostname, "server_port": port}
            try:
                res = self.check_host(host)
            except Exception:
                self.logger.exception("Error on {}:{}".format(hostname, port))
                self.metric(
                    "retrieval_success_boolean",
                    base_labels,
                    "1 for successful retrieval, 0 for failure",
                ).set(0)
                continue
            self.metric(
                "retrieval_time_seconds",
                base_labels,
                "Last certificate retrieval time, seconds since epoch",
            ).set(float(time.time()))
            self.metric(
                "retrieval_success_boolean",
                base_labels,
                "1 for successful retrieval, 0 for failure",
            ).set(1)

            labels = {**base_labels}
            for k, v in {"certificate_cn": res[3], "issuer_cn": res[4]}.items():
                if k not in skip_labels:
                    labels[k] = v

            self.metric("serial_number", labels, "Serial number of certificate").set(
                res[0]
            )
            self.metric(
                "not_before_seconds",
                labels,
                "Not Before time of certificate, seconds since epoch",
            ).set(res[1].timestamp())
            self.metric(
                "not_after_seconds",
                labels,
                "Not After time of certificate, seconds since epoch",
            ).set(res[2].timestamp())

        if not self.full_check_complete:
            self.full_check_complete = True

    def check_host(self, host):
        hostname = host["hostname"]
        port = host["port"]
        now = datetime.datetime.now()
        addr = socket.getaddrinfo(hostname, port)[0]
        sock = socket.socket(addr[0], addr[1], addr[2])
        sock.settimeout(10)
        sock.connect(addr[4])
        if host.get("type") == "starttls":
            # Usually SMTP (port 25)
            sock.recv(1024)
            sock.send(b"STARTTLS\r\n")
            sock.recv(1024)
        elif host.get("type") == "auth_tls":
            # Usually FTP (port 21)
            sock.recv(1024)
            sock.send(b"AUTH TLS\r\n")
            sock.recv(1024)

        ssl_context = ssl.SSLContext()
        ssl_sock = ssl_context.wrap_socket(sock, server_hostname=hostname)
        der_data = ssl_sock.getpeercert(True)
        ssl_sock.close()
        cert = x509.load_der_x509_certificate(der_data, default_backend())
        subject_cn = ""
        issuer_cn = ""
        sans = []
        oid_cn = x509.ObjectIdentifier("2.5.4.3")
        oid_san = x509.ObjectIdentifier("2.5.29.17")
        for attribute in cert.subject:
            if attribute.oid == oid_cn:
                subject_cn = attribute.value
        for attribute in cert.issuer:
            if attribute.oid == oid_cn:
                issuer_cn = attribute.value
        for attribute in cert.extensions:
            if attribute.oid == oid_san:
                sans = sorted([x.value for x in attribute.value])
        self.logger.debug(
            "{}:{} ({}) expires in {}".format(
                hostname, port, subject_cn, (cert.not_valid_after - now)
            )
        )
        self.logger.debug("    Issuer: {}".format(issuer_cn))
        self.logger.debug("    SANs: {}".format(sans))
        return (
            cert.serial_number,
            cert.not_valid_before,
            cert.not_valid_after,
            subject_cn,
            issuer_cn,
            sans,
        )


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
