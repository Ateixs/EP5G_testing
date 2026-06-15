#!/usr/bin/env python3
"""e2e_lat.py - end-to-end UDP round-trip latency measurement. No root needed.

One endpoint runs the echo server, the other runs the probing client. The client
sends COUNT UDP datagrams one at a time (send -> wait for echo -> send next) and
reports min / avg / p50 / p95 / p99 / max RTT, jitter (stdev), and loss.

  Server (echo):   python e2e_lat.py server <server_ip>
  Client (probe):  python e2e_lat.py client <server_ip> [client_ip]

The client's first IP argument is the DESTINATION (the server). The optional
second IP is THIS host's source address, used to pin the probe to a specific
interface (needed on multi-homed hosts such as Android phones with both cellular
and Wi-Fi up). Omit it on a single-interface machine.

Tune the run with the constants on the CONFIG line below; the measurement logic
does not need to be touched.
"""
import socket, sys, time, statistics

# --- CONFIG: port, packet count, payload bytes, send interval (s), recv timeout (s) ---
PORT, COUNT, SIZE, INTERVAL, TIMEOUT = 5005, 300, 200, 0.2, 1.0


def server(ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((ip, PORT))
    print(f"echo server listening on {ip}:{PORT}")
    while True:
        data, addr = s.recvfrom(65535)
        s.sendto(data, addr)


def client(dst, src=""):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if src:
        s.bind((src, 0))          # pin source to the segment IP
    s.settimeout(TIMEOUT)
    rtts, lost = [], 0
    for seq in range(COUNT):
        tag = seq.to_bytes(4, "big")
        t0 = time.perf_counter()
        s.sendto(tag + b"x" * (SIZE - 4), (dst, PORT))
        try:
            while True:                      # ignore late replies from earlier packets
                data, _ = s.recvfrom(65535)
                if data[:4] == tag:
                    rtts.append((time.perf_counter() - t0) * 1000)
                    break
        except socket.timeout:
            lost += 1
        time.sleep(INTERVAL)
    rtts.sort()
    n = len(rtts)
    print(f"sent={COUNT} recv={n} lost={lost} ({100 * lost / COUNT:.1f}%)")
    if n:
        p = lambda q: rtts[min(n - 1, int(n * q))]
        print(f"min={rtts[0]:.2f}  avg={statistics.mean(rtts):.2f}  "
              f"p50={p(.5):.2f}  p95={p(.95):.2f}  p99={p(.99):.2f}  max={rtts[-1]:.2f} ms")
        if n > 1:
            print(f"jitter(stdev)={statistics.stdev(rtts):.2f} ms")


USAGE = (
    "usage:\n"
    "  python e2e_lat.py server <server_ip>\n"
    "  python e2e_lat.py client <server_ip> [client_ip]\n"
    "\n"
    "client: first IP = destination (the server), second IP = this host's source\n"
    "address (optional; pins the probe to one interface on multi-homed hosts)."
)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(USAGE)
    mode = sys.argv[1]
    if mode == "server":
        server(sys.argv[2])
    elif mode == "client":
        client(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        sys.exit(USAGE)
