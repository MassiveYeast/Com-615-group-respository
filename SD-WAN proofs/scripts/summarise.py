#!/usr/bin/env python3
"""Summarise saved SD-WAN API JSON (evidence/api/<stamp>_*.json) into a readable report. Offline, read-only."""
import json
import sys
from collections import Counter
from pathlib import Path

api = Path(__file__).resolve().parent.parent / "evidence" / "api"
stamp = sys.argv[1] if len(sys.argv) > 1 else sorted(p.name.split("_")[0] for p in api.glob("*_overlay_state.json"))[-1]
load = lambda n: json.loads((api / f"{stamp}_{n}.json").read_text(encoding="utf-8"))
ov, pol = load("overlay_state"), load("policy_objects")

print(f"# Summary of API snapshot {stamp} (UTC)\n")
print("## Control plane (DTLS/TLS control connections)")
for sid, e in ov.items():
    cc = e.get("control_connections", [])
    if isinstance(cc, list) and cc:
        kinds = Counter(f"{c.get('peer-type')}/{c.get('protocol')}/{c.get('state')}" for c in cc)
        print(f"- {e['host-name']} ({sid}): " + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items())))

print("\n## OMP peers")
for sid, e in ov.items():
    for p in e.get("omp_peers", []) if isinstance(e.get("omp_peers"), list) else []:
        print(f"- {e['host-name']} -> peer {p.get('peer')} type={p.get('type')} state={p.get('state')} "
              f"routes rx/inst/sent={p.get('routes-received')}/{p.get('routes-installed')}/{p.get('routes-sent')} "
              f"tlocs rx/inst/sent={p.get('tlocs-received')}/{p.get('tlocs-installed')}/{p.get('tlocs-sent')}")

print("\n## TLOCs advertised (system-ip, colour, encapsulation)")
for sid, e in ov.items():
    for t in e.get("tloc_advertised", []) if isinstance(e.get("tloc_advertised"), list) else []:
        print(f"- {e['host-name']}: {t.get('ip')} color={t.get('color')} encap={t.get('encap')} "
              f"public={t.get('tloc-public-ip')} private={t.get('tloc-private-ip')}")

print("\n## BFD sessions (data-plane tunnels between edges)")
for sid, e in ov.items():
    bfd = e.get("bfd_sessions")
    if isinstance(bfd, list) and bfd:
        states = Counter(b.get("state") for b in bfd)
        pairs = sorted({f"{b.get('local-color')}->{b.get('system-ip')}:{b.get('color')}" for b in bfd})
        print(f"- {e['host-name']}: {dict(states)}; tunnels: {', '.join(pairs)}")

print("\n## App-route statistics (per tunnel: loss %, latency ms, jitter ms)")
for sid, e in ov.items():
    ar = e.get("app_route_stats")
    if isinstance(ar, list):
        for r in ar:
            print(f"- {e['host-name']} {r.get('local-color')}->{r.get('remote-system-ip')}:{r.get('remote-color')} "
                  f"loss={r.get('loss-percentage', r.get('loss'))} latency={r.get('average-latency', r.get('latency'))} "
                  f"jitter={r.get('average-jitter', r.get('jitter'))}")

print("\n## OMP routes received per VPN (service-side segmentation)")
for sid, e in ov.items():
    rr = e.get("omp_routes_received")
    if isinstance(rr, list) and rr:
        vpns = Counter(str(r.get("vpn-id")) for r in rr)
        print(f"- {e['host-name']}: " + ", ".join(f"VPN {k}: {v} routes" for k, v in sorted(vpns.items())))

print("\n## SLA classes defined")
for s in pol.get("sla_class_lists", []):
    entries = s.get("entries", [])
    print(f"- {s.get('name')}: {entries} (referenced by {s.get('referenceCount', '?')} policies)")
for k in ("centralised_policies", "app_route_definitions", "vpn_lists", "site_lists", "control_definitions"):
    v = pol.get(k)
    print(f"- {k}: {len(v) if isinstance(v, list) else v}")
