# SD-WAN experiment log (Phase 2 - Week-6 Requirement 2: acquired-site integration)

Every result below comes from a command that was actually run on 2026-11-12, or is explicitly marked **design/research only**. Raw console output: `evidence/logs/` (UTC timestamps). Sanitised API JSON: `evidence/api/`. Experiment IDs SD-xx follow the plan; requirement IDs are listed per experiment (see `../Ansible proofs/ansible/docs/REQUIREMENTS.md` for B/T/S/O and §"New requirements" below for W-IDs).

## New requirements derived from the Week-6 brief (Requirement 2)

| ID | Requirement (from CIO brief, Week 6) | Type | Priority |
|---|---|---|---|
| W1 | Securely connect the acquired company's site to Northstar without unnecessarily disrupting its operations | Business / security | Must |
| W2 | Centrally manage WAN connectivity so that each further acquisition or new manufacturing site can be added with predictable effort | Operational / scalability | Must |
| W3 | Segment traffic: Corporate Services, Engineering Systems, Infrastructure Management (aligned with the data-centre environments in Requirement 1) | Security | Must |
| W4 | Use more than one transport per site and steer critical applications onto the path that meets their needs (application-aware routing) | Performance / resilience | Should |
| W5 | Provide WAN visibility and programmatic access (APIs) for monitoring and automation | Fault / performance / config management | Should |
| W6 | Evaluate SD-WAN critically against conventional WAN/site-to-site VPN, including cost, dependency and migration risk; do not treat the Cisco partnership as a reason in itself | Business | Must |

**Change trace:** Phase 1 assumed one main site plus the acquired site managed by Ansible over a flat lab network (B2). The Week-6 brief (earlier-than-planned acquisition, further acquisitions, Cisco partnership) added W1–W6 and moved the inter-site connectivity problem from "reach the second site" to "operate a growing multi-site WAN". Ansible's role is narrowed accordingly (INT-01).

---

## SD-01 - DevNet sandbox environment assessment

Raw output: `evidence/logs/20261112-222708_01_SD-01_tls_check.txt`, `…_224657_…`/`…_05_SD-02_inventory_overlay_policy.txt`.

| Item | Finding (2026-11-12) |
|---|---|
| Sandbox | Cisco DevNet **always-on** Catalyst SD-WAN sandbox, SD-WAN Manager at `sandbox-sdwan-2.cisco.com:443` (`sandbox-sdwan-1` closed) |
| Software | Manager/Controller/Validator **20.18.2.1**; WAN Edges Catalyst 8000V **17.18.01a** (from API) |
| Access | HTTPS REST API; session login `POST /j_security_check` + `GET /dataservice/client/token` (XSRF token header) |
| Credentials | Cisco's publicly published shared read-only account (source: CiscoDevNet *Postman-for-AlwaysOn-Cisco-SD-WAN* environment file). Held only in `~/.sdwan_env` (mode 600) outside the repo |
| Permissions | Role **operator** (from `/client/server`) = read-only. No policy/template changes possible → SD-04/SD-05 cannot be tested by changing configuration |
| Inventory | 7 devices: Manager01, Controller01 (vSmart), Validator01 (vBond), Edge1–4 (sites 1–4) |
| Shared environment | Used by anyone on the Internet; state can change; availability not guaranteed (Cisco announced sandbox platform changes in 2026) |
| **TLS** | **Failed normal verification:** certificate for `sandbox-sdwan-2.cisco.com` expired **2026-09-27**, and the server sends only the leaf certificate (no intermediate), so clients also report "unable to get local issuer certificate". Windows curl: `SEC_E_CERT_EXPIRED`; OpenSSL: verify errors 20, 21, 10 |

- **Decision:** do not disable TLS verification. The client verifies normally by default and supports **certificate pinning** (SHA-256 `35:78:CE:58:…:84:ED:03`, recorded in log 01) as an explicit, logged alternative.
- **Limitation:** the pin was taken from the same connection that it protects (trust on first use); it is only as good as that first observation. For production the correct fix is a valid certificate from a trusted CA (SD-WAN Manager supports enterprise CA certificates).

## SD-02 - Device inventory API (read-only client)

Code: `scripts/sdwan_client.py`, `scripts/run_client.sh`, `scripts/summarise.py`. Raw output: logs 02–07; JSON: `evidence/api/20261112-224657_*`, `20261112-224846_*`.

- **Requirement:** W5, W2. **Hypothesis:** the operational state of the whole overlay can be retrieved from one central API, without logging in to any router.
- **Client design:** env-var credentials; `(10 s, 30 s)` timeouts; HTTP status + JSON-type checks; vManage's "HTTP 200 with login page" failure mode detected; GET-only; logout at the end; sensitive keys sanitised before saving (the session `CSRFToken` was replaced with `[removed]`).

| Test | Result |
|---|---|
| Default TLS, dummy credentials (log 02) | **Refused** before login (`CERTIFICATE_VERIFY_FAILED`) - credentials never sent |
| Pinned, **wrong** fingerprint (log 04) | **Refused** before login ("Fingerprints did not match") - pinning really authenticates the server |
| First pinned run (log 03) | **Failed**: `requests` re-imposed CA verification over the pinned adapter. Fixed by letting the adapter own the TLS decision (fingerprint check replaces, not removes, verification) |
| Pinned, correct fingerprint (logs 05, 06) | **Passed**: login as `devnetuser` (operator), platform 20.18.2.1 |

**Inventory (GET /dataservice/device), 2026-11-12 22:46 UTC:**

| Host | System IP | Site | Type | Model | Reachability | Version |
|---|---|---|---|---|---|---|
| Manager01 | 100.0.0.1 | 100 | vmanage | vmanage | reachable | 20.18.2.1 |
| Controller01 | 100.0.0.101 | 100 | vsmart | vsmart | reachable | 20.18.2.1 |
| Validator01 | 100.0.0.201 | 100 | vbond | vedge-cloud | reachable | 20.18.2.1 |
| Edge1–Edge4 | 10.0.0.1–.4 | 1–4 | vedge | vedge-C8000V | reachable | 17.18.01a.0.182 |

- **Result:** passed. One authenticated session returned inventory, control connections, OMP peers, TLOCs, BFD sessions, OMP routes and app-route statistics for every device (overlay snapshot ≈ 40 s for 7 devices, mostly per-device calls).
- **Analysis:** this is the management-plane difference from Phase 1: in a traditional WAN the same information requires logging in to each router (or SNMP polling per device). Here the controller already aggregates it, so monitoring/automation integrates with **one** API (W5).

## SD-03 - Architecture: what the sandbox shows, and the proposed Northstar design

### Observed in the sandbox (evidence: log 07, `…224846_overlay_state.json`)

| Plane | Observation | Meaning |
|---|---|---|
| Orchestration | Validator01 (vBond) has DTLS sessions to Manager and Controller | First point of contact; authenticates devices and tells them where the controllers are |
| Management | Manager01: DTLS up to 4 edges, Controller, Validator | Single place for configuration, monitoring and API |
| Control | Controller01 (vSmart): 8 DTLS sessions to edges (4 edges × 2 transports) + OMP peering with all 4 edges | Edges do not exchange routes with each other; the Controller reflects routes/TLOCs/policy via OMP |
| Transport (TLOCs) | Each edge advertises **2 TLOCs**: colour `mpls` (172.16.2.x) and `biz-internet` (172.16.1.x), encapsulation **IPsec** | A TLOC = (system-IP, colour, encapsulation) = one WAN attachment point |
| Data plane | Each edge: **6 BFD sessions, all `up`**, IPsec, 1 s hello × 7 multiplier, uptime ≈ 168 days, 0 transitions; tunnels only same-colour (mpls↔mpls, internet↔internet) | Full mesh built automatically: 4 sites × 2 colours = 2 × (4×3/2) = **12 IPsec tunnels**, none configured individually |
| Service side | OMP routes received only in **VPN 1** (8 routes per edge) | Single service VPN: no segmentation configured in this fabric |

### Proposed design for Northstar (design only, not deployed)

See `docs/ARCHITECTURE.md` for the diagram (Figure source).

| Element | Proposal | Justification |
|---|---|---|
| Controllers | Cisco-hosted (cloud) Manager/Controller/Validator, ≥ 2 Controllers | Avoids running controller VMs on-site; 2 Controllers so the control plane survives one failure. Trade-off: dependency on Cisco cloud and subscription |
| Main site (site-id 100) | 2 × WAN Edge (C8000-series), MPLS + business Internet | Device and transport redundancy at the data-centre site that hosts shared services |
| Acquired site (200) | 1 × WAN Edge initially, Internet + 4G/5G backup; existing LAN left in place behind it | W1: integrate without re-addressing; edge can run alongside the old VPN during migration |
| Future sites (300+) | 1 × WAN Edge, dual Internet or Internet + cellular | W2: a new site = ship a router, it calls home (zero-touch via Validator); no per-tunnel config |
| VPN 0 / 512 | Transport and out-of-band management | Standard separation of underlay from services |
| Service VPNs | VPN 10 Corporate, VPN 20 Engineering, VPN 30 Infrastructure Management (SD-04) | W3; matches the ACI VRFs proposed for the data centre (Requirement 1) |

## SD-04 - Segmentation (design research + read-only inspection)

- **Requirement:** W3, S-security. **Evidence available:** read-only policy inventory (log 05/06): **0 centralised policies, 0 VPN lists, 0 site lists, 0 control definitions**; routes exist in VPN 1 only. The operator role cannot create VPNs or policies → **segmentation was not tested; classified as design research.**
- **Proposal:**

| Service VPN | Contents | Default reachability | Controlled exceptions |
|---|---|---|---|
| VPN 10 Corporate | Users, AD/DNS, file, ERP clients | All sites ↔ main-site data centre | Internet via local breakout + cloud security (Requirement 4 SSE) |
| VPN 20 Engineering | CAD/PLM, engineering file servers, test systems | Engineering sites ↔ data centre only | No route leaking to Corporate; specific shared services via firewall in DC |
| VPN 30 Infrastructure Mgmt | Device management, Ansible control node, monitoring (OpenNMS) | Management hosts ↔ all devices | Only VPN allowed to reach device management addresses |

- **How it works:** each service VPN is a separate VRF on every edge; OMP carries the VPN label with each route, so a prefix in VPN 20 is never installed in VPN 10. Inter-VPN traffic is impossible unless explicitly leaked by a centralised control policy or routed through a firewall (preferred: Cisco Secure Firewall in the DC - Requirement 3 - so it is inspected and logged).
- **Analysis:** segmentation is end-to-end across the WAN with no per-tunnel config, unlike a traditional IPsec VPN where each segment would need its own tunnels/VRFs on every router. Risk: a mistaken leak policy breaks segmentation for **every** site at once - central control centralises mistakes too, so policy changes need review (INT-01 change control).

## SD-05 - Application-aware routing (read-only data + design)

- **Requirement:** W4. **Measured (log 07, `overlay_state.json` app_route_stats, 36 samples per edge = 6 tunnels × 6 intervals):** loss 0 %, latency 0 ms, jitter 0 ms on every tunnel; **0 data packets** sent/received. **SLA classes defined (8)**, e.g. Realtime ≤ 150 ms / 30 ms / 1 %, Voice-And-Video ≤ 300 / 60 / 2 %, Transactional-Data ≤ 200 / 200 / 1 %, Business-Critical ≤ 250 / 100 / 1 %, Bulk-Data ≤ 500 / 500 / 5 %. **All referenced by 0 policies; 0 app-route definitions.**
- **Interpretation:** the probes run (BFD measures every tunnel), but the sandbox transports are idealised virtual links with no traffic and no impairment, and no AAR policy is active. So **path selection under degradation could not be demonstrated**; the data shows the measurement mechanism exists, not that it works under stress. Classified **partly validated (mechanism) / design research (behaviour)**.
- **Proposed policy for Northstar (design):**

| Application group | SLA class (sandbox thresholds) | Preferred colour | Fallback |
|---|---|---|---|
| Voice/video (Teams, telephony) | Voice-And-Video | mpls | biz-internet if SLA met, else best path |
| ERP / transactional | Transactional-Data | mpls | biz-internet |
| Engineering file/PLM transfers | Bulk-Data | biz-internet (bandwidth) | mpls |
| Device management / monitoring | Business-Critical | mpls | any |

- **Test plan (not executed - needs a reservable sandbox or CML lab with an admin role):** (1) apply the policy; (2) generate traffic per class; (3) impair the `mpls` transport with `tc netem` delay/loss above the class threshold; (4) record time to path switch via `/device/app-route/statistics` and `/device/tunnel/statistics`; (5) remove impairment and record failback. Expected: switch after the SLA is violated for the configured window. Cisco Live material notes classic AAR reacts on BFD-based averaging windows (minutes) while enhanced AAR reacts in seconds - must be confirmed for 20.18 before quoting.

## SD-06 - Traditional site-to-site VPN vs Catalyst SD-WAN (research + one measured point)

**Measured point:** the sandbox's 4-site, 2-transport full mesh has 12 IPsec tunnels and 24 BFD sessions; none was configured per tunnel (all derived from TLOCs distributed by OMP). With a traditional design, a full mesh needs C·N(N-1)/2 tunnels configured on both ends: N = 2 sites → 2 tunnels, N = 6 → 30, N = 10 → 90 (two transports).

| Criterion | Traditional IPsec / routing | Catalyst SD-WAN | Evidence type |
|---|---|---|---|
| Adding a site | Configure tunnels/crypto on the new router **and** every peer (or hub-and-spoke with hairpinning) | New edge authenticates to Validator, receives config from Manager; tunnels built automatically | Measured (tunnel count) + vendor docs |
| Segmentation | Per-VRF tunnels/DMVPN per segment, per router | Service VPNs carried end-to-end by OMP | Design research |
| Visibility | Per-device CLI/SNMP | Central API/dashboard (SD-02 showed whole-fabric state in one session) | Measured |
| Policy consistency | Each router configured separately (drift risk - cf. AN-04) | Central policy pushed by Controller | Design research |
| Resilience | Routing protocol convergence; manual path policy | Multiple TLOCs + BFD per tunnel; AAR | Partly observed (BFD) |
| Security | Mature, open standards (IPsec RFC 4301) | Same IPsec data plane + certificate-based device identity; **new central attack surface** (Manager/Controllers, their certificates - SD-01 found an expired certificate on Cisco's own sandbox) | Measured + research |
| Cost / licensing | Existing routers, no subscription | Subscription licensing per edge + controller hosting; **no price obtained** - needs a Cisco/partner quote | Not established |
| Vendor dependency | Multi-vendor possible | Single-vendor control plane; exit cost high | Research |
| Skills | Existing team skills | New skills (training offered by the partnership) | Research |
| Migration risk | n/a | Parallel running required; acquired site's existing VPN kept until cut-over | Design |

- **Conclusion:** for two sites, SD-WAN is hard to justify on tunnel count alone; the case rests on **W2 (more acquisitions), W3 (segmentation) and W5 (central visibility/API)**. Cost was not established and must be obtained before a decision (W6). The partnership is not itself a technical justification.

## INT-01 - Ansible and SD-WAN Manager together (design)

| Task | Owner | Why |
|---|---|---|
| Linux server baseline, services, drift correction (AN-02..05) | **Ansible** | Proven in Phase 1 |
| Day-0 edge onboarding (certificates, Validator discovery) | **SD-WAN Manager** (PnP/ZTP) | Edges in controller mode are managed by Manager, not by CLI |
| WAN Edge configuration (templates/configuration groups, VPNs) | **SD-WAN Manager** | Pushing CLI to controller-managed edges would conflict with Manager (configuration drift) |
| Centralised policy (segmentation, AAR) | **SD-WAN Manager** | Controller distributes via OMP |
| Bulk/repeatable Manager operations (create site from inventory, attach configuration, export state for audit) | **Ansible → Manager API** (`cisco.catalystwan` / `cisco.sdwan` collections, or the REST API as in SD-02) | Keeps one inventory (Git) as source of truth; version compatibility with 20.18 **not verified** - Cisco tooling documents support per Manager release |
| Monitoring / alarms | OpenNMS (team) polling Manager API + devices | SD-02 shows the API exposes reachability, BFD and TLOC state |
| Change control / audit | Git (playbooks, policy definitions) + Manager audit log | B3 |

- **Limit found in practice:** the always-on sandbox is read-only, so the Ansible→Manager path was not exercised; only read access was proven (SD-02).

## References used in this file (Harvard; full list kept with the individual report)

Cisco (2024) *Cisco Catalyst SD-WAN Design Guide*; Cisco DevNet (n.d.) *Postman for AlwaysOn Cisco SD-WAN*; Cisco DevNet (n.d.) *Ansible Collections - Catalyst SD-WAN*; Kent and Seo (2005) RFC 4301; Katz and Ward (2010) RFC 5880; Fu, Wang and Wang (2024); Ouamri et al. (2025).
