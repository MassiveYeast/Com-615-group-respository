#!/usr/bin/env python3
"""Read-only Cisco Catalyst SD-WAN Manager (vManage) REST API client - NEL PoC, experiments SD-02/SD-04/SD-05.

Only HTTP GET calls are made after login: nothing in the fabric is changed.

Credentials come from environment variables, never from this file or the repo:
    SDWAN_HOST   e.g. sandbox-sdwan-2.cisco.com
    SDWAN_USER
    SDWAN_PASS
    SDWAN_PIN_SHA256   (optional) SHA-256 fingerprint of the server certificate, see TLS below

TLS: certificates are verified normally by default. If (and only if) SDWAN_PIN_SHA256 is set,
the client instead accepts exactly one certificate with that fingerprint (certificate pinning).
This is used because the DevNet sandbox certificate had expired (evidence: SD-01 log 01). Pinning
still authenticates the server; it does NOT accept "any" certificate. Verification is never simply
switched off.

Usage:
    python sdwan_client.py <inventory|overlay|policy|all> [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

TIMEOUT = (10, 30)  # (connect, read) seconds
SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "xsrf", "cookie", "jsessionid", "key"}


class SdwanError(RuntimeError):
    """A clear, user-facing error."""


class PinnedFingerprintAdapter(HTTPAdapter):
    """Accept only a server certificate whose SHA-256 fingerprint matches the pinned value."""

    def __init__(self, fingerprint: str, **kwargs):
        self._fingerprint = fingerprint.replace(":", "").lower()
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["assert_fingerprint"] = self._fingerprint
        kwargs["cert_reqs"] = "CERT_NONE"  # CA/expiry check replaced by the exact fingerprint check
        super().init_poolmanager(*args, **kwargs)


def env(name: str, required: bool = True) -> str | None:
    value = os.environ.get(name)
    if required and not value:
        raise SdwanError(f"environment variable {name} is not set")
    return value


def sanitise(obj):
    """Remove values whose key looks sensitive (defence in depth; read-only data should not contain any)."""
    if isinstance(obj, dict):
        return {k: ("[removed]" if any(s in k.lower() for s in SENSITIVE_KEYS) else sanitise(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitise(i) for i in obj]
    return obj


class SdwanManager:
    def __init__(self, host: str, user: str, password: str, pin: str | None):
        self.base = f"https://{host}"
        self.s = requests.Session()
        self.s.headers["Accept"] = "application/json"
        if pin:
            self.s.mount(self.base, PinnedFingerprintAdapter(pin))
            self.tls_mode = f"pinned certificate sha256={pin}"
        else:
            self.tls_mode = "normal CA verification"
        self._login(user, password)

    def _login(self, user: str, password: str) -> None:
        try:
            r = self.s.post(f"{self.base}/j_security_check",
                            data={"j_username": user, "j_password": password},
                            timeout=TIMEOUT, allow_redirects=False)
        except requests.exceptions.SSLError as e:
            raise SdwanError(f"TLS verification failed ({self.tls_mode}): {e}") from None
        except requests.exceptions.RequestException as e:
            raise SdwanError(f"cannot reach {self.base}: {e}") from None
        # vManage answers 200 even for a failed login; a failure returns the HTML login page.
        if r.status_code != 200 or "<html" in r.text.lower():
            raise SdwanError(f"login rejected (HTTP {r.status_code}); check SDWAN_USER/SDWAN_PASS")
        t = self.s.get(f"{self.base}/dataservice/client/token", timeout=TIMEOUT)
        if t.status_code != 200 or "<html" in t.text.lower():
            raise SdwanError(f"could not obtain XSRF token (HTTP {t.status_code})")
        self.s.headers["X-XSRF-TOKEN"] = t.text.strip()

    def get(self, path: str, params: dict | None = None) -> dict:
        try:
            r = self.s.get(f"{self.base}/dataservice{path}", params=params, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise SdwanError(f"GET {path} failed: {e}") from None
        if r.status_code != 200:
            raise SdwanError(f"GET {path} -> HTTP {r.status_code}: {r.text[:200]}")
        try:
            body = r.json()
        except ValueError:
            raise SdwanError(f"GET {path} returned non-JSON (session expired?): {r.text[:120]}") from None
        if not isinstance(body, dict):
            raise SdwanError(f"GET {path} returned unexpected JSON type {type(body).__name__}")
        return body

    def logout(self) -> None:
        try:
            self.s.get(f"{self.base}/logout", params={"nocache": "1"}, timeout=TIMEOUT, allow_redirects=False)
        except requests.exceptions.RequestException:
            pass


# ---------------------------------------------------------------- collectors

def inventory(m: SdwanManager) -> dict:
    devices = m.get("/device").get("data", [])
    fields = ["host-name", "system-ip", "site-id", "device-type", "personality", "device-model",
              "reachability", "status", "version", "uptime-date", "state"]
    rows = [{f: d.get(f) for f in fields} for d in devices]
    return {"devices_raw": devices, "devices": rows, "server": m.get("/client/server").get("data", {})}


def overlay(m: SdwanManager, devices: list[dict]) -> dict:
    """Per-device control/overlay state: control connections, OMP peers, BFD sessions, TLOCs."""
    out = {}
    for d in devices:
        sid, typ = d.get("system-ip"), d.get("device-type")
        if not sid or d.get("reachability") != "reachable":
            continue
        entry = {"device-type": typ, "host-name": d.get("host-name")}
        calls = {"control_connections": "/device/control/connections"}
        if typ in ("vedge", "vsmart"):
            calls["omp_peers"] = "/device/omp/peers"
        if typ == "vedge":
            calls["bfd_sessions"] = "/device/bfd/sessions"
            calls["tloc_advertised"] = "/device/omp/tlocs/advertised"
        for name, path in calls.items():
            try:
                entry[name] = m.get(path, {"deviceId": sid}).get("data", [])
            except SdwanError as e:
                entry[name] = {"error": str(e)}
        out[sid] = entry
    return out


def policy(m: SdwanManager) -> dict:
    """Centralised policy objects (read-only): policies, app-aware-routing and SLA definitions, VPN lists."""
    calls = {
        "centralised_policies": "/template/policy/vsmart",
        "app_route_definitions": "/template/policy/definition/approute",
        "sla_class_lists": "/template/policy/list/sla",
        "vpn_lists": "/template/policy/list/vpn",
        "site_lists": "/template/policy/list/site",
        "control_definitions": "/template/policy/definition/control",
    }
    out = {}
    for name, path in calls.items():
        try:
            out[name] = m.get(path).get("data", [])
        except SdwanError as e:
            out[name] = {"error": str(e)}
    return out


# ---------------------------------------------------------------- output

def write(out_dir: Path, stamp: str, name: str, data) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{stamp}_{name}.json"
    p.write_text(json.dumps(sanitise(data), indent=2, sort_keys=True), encoding="utf-8")
    return p


def print_inventory(rows: list[dict]) -> None:
    cols = ["host-name", "system-ip", "site-id", "device-type", "device-model", "reachability", "version"]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) if rows else len(c) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["inventory", "overlay", "policy", "all"])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "evidence" / "api"))
    a = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(a.out)

    try:
        m = SdwanManager(env("SDWAN_HOST"), env("SDWAN_USER"), env("SDWAN_PASS"), env("SDWAN_PIN_SHA256", False))
    except SdwanError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"# connected to {m.base} as {os.environ['SDWAN_USER']} ({m.tls_mode}) at {stamp} UTC")
    try:
        inv = inventory(m)
        srv = inv["server"]
        print(f"# server: platform version {srv.get('platformVersion')}, user role(s) {srv.get('roles') or srv.get('userMode')}")
        print(f"# saved {write(out_dir, stamp, 'server', srv)}")
        if a.what in ("inventory", "all"):
            print(f"# saved {write(out_dir, stamp, 'device_inventory', inv['devices_raw'])}")
            print(f"\n## Device inventory (GET /dataservice/device): {len(inv['devices'])} devices")
            print_inventory(inv["devices"])
        if a.what in ("overlay", "all"):
            ov = overlay(m, inv["devices"])
            print(f"\n# saved {write(out_dir, stamp, 'overlay_state', ov)}")
            for sid, e in ov.items():
                summary = ", ".join(f"{k}={len(v) if isinstance(v, list) else 'ERR'}" for k, v in e.items() if k not in ("device-type", "host-name"))
                print(f"  {e['host-name']:<14} {sid:<12} {e['device-type']:<8} {summary}")
        if a.what in ("policy", "all"):
            pol = policy(m)
            print(f"\n# saved {write(out_dir, stamp, 'policy_objects', pol)}")
            for k, v in pol.items():
                print(f"  {k:<24} {len(v) if isinstance(v, list) else v}")
    except SdwanError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    finally:
        m.logout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
