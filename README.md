# EP5G_testing

End-to-end latency measurement for an **Ericsson Private 5G (EP5G) Standalone Indoor**
deployment. The tool here measures real userspace UDP round-trip time (RTT) between
two endpoints — phone-to-phone, or phone-to-host — to validate the network against
**URLLC (~5 ms E2E)** and **eMBB (~20 ms E2E)** latency targets.

The measurement uses a plain UDP echo loop rather than ICMP `ping`. ICMP is
kernel-handled and does not traverse a real application socket, so it does not
reflect what an actual application experiences. This script sends and receives over
a userspace UDP socket, which is the path that matters for E2E latency claims in a
research report.

## Contents

| File | Purpose |
|------|---------|
| `e2e_lat.py` | UDP echo server + probing client. Measures min/avg/p50/p95/p99/max RTT, jitter, and loss. |

> Throughput is **not** measured here. A synchronous one-packet-in-flight loop is
> correct for latency but useless for throughput. Use `iperf3` for bandwidth (see
> [Throughput](#throughput-companion) below).

## Requirements

- **Python 3** (standard library only — no `pip install` needed).
- On Android: **Termux**
- Two endpoints on the EP5G network, each with the IP that NMP assigned to its PDU
  session (the `172.16.x.x` addresses in this lab).
- No root required on either phone.

## Installation

### On a computer (Linux / macOS / Windows)

Python 3 is preinstalled on most Linux and macOS systems; on Windows install it from
[python.org](https://www.python.org/downloads/). Then just place `e2e_lat.py`
anywhere and run it. Nothing else to install.

```bash
git clone https://github.com/Ateixs/EP5G_testing.git
cd EP5G_testing
python3 e2e_lat.py        # prints usage
```

### On an Android phone (Termux)

1. Install **Termux** from F-Droid.
2. Install Python inside Termux:
   ```bash
   pkg update && pkg install python -y
   ```
3. Get `e2e_lat.py` onto the phone (see next section), then run it from Termux.

### Transferring the script to a phone

The simplest, most reliable method is a **USB cable**:

1. Connect the phone to a computer. Pull down the notification shade, tap the USB
   notification, and switch it from "Charging" to **File Transfer / MTP**.
   (On macOS, MTP isn't native — use Google's *Android File Transfer* tool.)
2. Copy `e2e_lat.py` into the phone's **Download** folder.
3. In Termux, grant storage access once and copy the file into the home directory:
   ```bash
   termux-setup-storage                              # tap "Allow" on the popup
   cp ~/storage/shared/Download/e2e_lat.py ~
   cd ~
   ```

If `cp` reports "No such file or directory," Windows may have changed the filename —
list what's actually there and adjust:

```bash
ls ~/storage/shared/Download/
cp ~/storage/shared/Download/<actual_name> ~/e2e_lat.py
```

Repeat on the second phone.

## Running the test

One endpoint is the **echo server**; the other is the **probing client**. Use each
endpoint's own EP5G-assigned IP.

```bash
# On the SERVER endpoint (e.g. Phone A = 172.16.6.1):
python e2e_lat.py server 172.16.6.1
# -> prints: echo server listening on 172.16.6.1:5005   (leave this running)

# On the CLIENT endpoint (e.g. Phone B = 172.16.7.1):
python e2e_lat.py client 172.16.6.1 172.16.7.1
```

### Argument order matters

For the **client**, the first IP is the **destination** (the server you are probing),
and the optional second IP is **this host's own source address**:

```
python e2e_lat.py client <server_ip> [this_host_ip]
```

The source IP pins the probe to the correct interface. On Android, both cellular and
Wi-Fi can be up at once, so without pinning, the OS may send from the wrong interface
(symptom: `OSError: [Errno 99] Cannot assign requested address` means the bound
address isn't actually this host's). On a single-interface computer you can omit it:

```bash
python3 e2e_lat.py client 172.16.6.1
```

### Scenarios

- **Phone-to-phone (two air legs):** client on Phone B, destination = Phone A.
  This hairpins through the network controller, so RTT ≈ 2× the single-leg figure.
- **Phone-to-host / edge (single air leg):** run the server on a wired LAN host and
  point the client at it. This is the device-to-edge path relevant to client-server
  URLLC latency.

## Tuning

The `CONFIG` line near the top of `e2e_lat.py` controls the run; the measurement
logic does not need editing:

```python
PORT, COUNT, SIZE, INTERVAL, TIMEOUT = 5005, 300, 200, 0.2, 1.0
```

| Constant   | Meaning | Default |
|------------|---------|---------|
| `PORT`     | UDP port for the echo server | 5005 |
| `COUNT`    | Number of round trips per run | 300 |
| `SIZE`     | Payload bytes per datagram | 200 |
| `INTERVAL` | Seconds between sends (0.2 = 5 packets/s) | 0.2 |
| `TIMEOUT`  | Seconds to wait for an echo before counting loss | 1.0 |

## Reading the output

```
sent=300 recv=297 lost=3 (1.0%)
min=16.21  avg=18.94  p50=18.40  p95=23.10  p99=41.55  max=312.7 ms
jitter(stdev)=6.80 ms
```

- **min / avg** — the floor and central tendency. On this deployment a phone-to-phone
  avg of ~16–20 ms is expected (two ~8 ms air legs plus stack overhead). A single air
  leg (phone-to-host) runs ~8 ms RTT.
- **p95 / p99 / max** — the tail, and the most important numbers for a real-time use
  case. The 1-second spikes observed in this lab surface here as a severe p99/max even
  when the average looks fine. A low average with a huge max is not a usable real-time
  link; the gap between p50 and p99 is the jitter budget.
- **loss** — the effective SLA-violation rate for anything with a deadline.

### Against the targets

- **URLLC (~5 ms E2E):** not achievable phone-to-phone on this architecture — the
  two-air-leg hairpin floor alone is ~8 ms one-way. It is the single-leg client-server
  path that should be evaluated against URLLC.
- **eMBB (~20 ms E2E):** met on the single-air-leg client-server path.

## Throughput companion

Latency and throughput need opposite measurement designs (one packet in flight vs.
flooding the pipe), so throughput is not done here. Use `iperf3`, which is the
research-standard tool and is written in C to avoid Python's per-packet overhead:

```bash
# Server endpoint:
iperf3 -s -B <server_ip>

# Client endpoint — UDP, push toward 100 Mbit/s with 1200-byte packets for 20 s:
iperf3 -u -c <server_ip> -B <client_ip> -b 100M -l 1200 -t 20

# TCP throughput (how eMBB bandwidth is usually quoted):
iperf3 -c <server_ip> -B <client_ip> -t 20
```

For rigorous reporting: Omit warm-up with `-O 3`, run multiple trials, and log JSON with `-J`. As with
latency, phone-to-phone throughput hairpins through the controller across two air legs, so point the client at a wired LAN host for the device-to-edge figure.