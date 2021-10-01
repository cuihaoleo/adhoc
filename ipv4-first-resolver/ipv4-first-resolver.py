#!/usr/bin/env python3

import argparse
import socket
import time

from dnslib import DNSRecord, QTYPE, RCODE
from dnslib.server import BaseResolver, DNSLogger, DNSServer


class IPv4FirstResolver(BaseResolver):
    def __init__(self, address, port, timeout):
        self.timeout = timeout
        self.address = address
        self.port = port

    def resolve(self, request, handler):
        if handler.protocol != "udp":
            raise NotImplementedError()

        qname = request.q.qname

        if request.q.qtype == QTYPE.AAAA:
            question = DNSRecord.question(qname, "A")
            raw_reply = question.send(self.address, self.port, timeout=self.timeout)
            reply = DNSRecord.parse(raw_reply)

            if any(rr.rtype == QTYPE.A for rr in reply.rr):
                return request.reply()

        try:
            raw_reply = request.send(self.address, self.port, timeout=self.timeout)
            reply = DNSRecord.parse(raw_reply)
        except socket.timeout:
            reply = request.reply()
            reply.header.rcode = RCODE.SERVFAIL

        return reply


if __name__ == '__main__':
    p = argparse.ArgumentParser(description="DNS Intercept Proxy")
    p.add_argument("--port", "-p", type=int, default=53,
                   metavar="<port>",
                   help="Local proxy port (default:53)")
    p.add_argument("--address", "-a", default="",
                   metavar="<address>",
                   help="Local proxy listen address (default:all)")
    p.add_argument("--upstream", "-u", default="8.8.8.8:53",
                   metavar="<dns server:port>",
                   help="Upstream DNS server:port (default:8.8.8.8:53)")
    p.add_argument("--timeout", "-o", type=float, default=5,
                   metavar="<timeout>",
                   help="Upstream timeout (default: 5s)")
    p.add_argument("--intercept", "-i", action="append",
                   metavar="<zone record>",
                   help="Intercept requests matching zone record (glob) ('-' for stdin)")
    p.add_argument("--log", default="request,reply,truncated,error",
                   help="Log hooks to enable (default: +request,+reply,+truncated,+error,-recv,-send,-data)")
    p.add_argument("--log-prefix", action='store_true', default=False,
                   help="Log prefix (timestamp/handler/resolver) (default: False)")
    args = p.parse_args()

    args.dns, _, args.dns_port = args.upstream.partition(':')
    args.dns_port = int(args.dns_port or 53)

    resolver = IPv4FirstResolver(args.dns, args.dns_port, args.timeout)
    logger = DNSLogger(args.log, args.log_prefix)

    print("Starting Resolver (%s:%d -> %s:%d)" % (args.address or "*", args.port, args.dns, args.dns_port))
    print()

    udp_server = DNSServer(resolver,
                           port=args.port,
                           address=args.address,
                           logger=logger)
    udp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)
