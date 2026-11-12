# Proposed Northstar WAN and management architecture (design - not deployed)

GitHub renders these diagrams; screenshot them for the report (or redraw in draw.io). Logical design only: the PoC evidence is the DevNet sandbox (SD-01/02) and the Ansible lab (AN-01..06).

## Figure A - Proposed Catalyst SD-WAN architecture for Northstar (SD-03)

```mermaid
flowchart TB
  subgraph CLOUD["Cisco-hosted control & management (subscription)"]
    MGR["SD-WAN Manager<br/>config, monitoring, REST API"]
    CTL1["Controller 1 (OMP)"]
    CTL2["Controller 2 (OMP)"]
    VAL["Validator<br/>device authentication / NAT traversal"]
  end

  subgraph MAIN["Main site - site-id 100 (offices + data centre)"]
    E1["WAN Edge A"]
    E2["WAN Edge B"]
    DC["DC: ACI fabric (Req 1) + Secure Firewall (Req 3)"]
  end
  subgraph ACQ["Acquired site - site-id 200"]
    E3["WAN Edge"]
    OLD["Existing LAN (kept, not re-addressed)"]
  end
  subgraph NEW["Future sites - site-id 300+"]
    E4["WAN Edge (zero-touch)"]
  end

  MPLS(("MPLS transport<br/>TLOC colour mpls"))
  INET(("Internet transport<br/>TLOC colour biz-internet"))
  LTE(("4G/5G backup<br/>colour lte"))

  E1 --- MPLS
  E2 --- INET
  E3 --- INET
  E3 --- LTE
  E4 --- INET
  E4 --- LTE

  E1 & E2 & E3 & E4 -. "DTLS control + OMP" .-> CTL1 & CTL2
  E1 & E2 & E3 & E4 -. "DTLS management" .-> MGR
  E1 & E2 & E3 & E4 -. "onboarding" .-> VAL

  E1 <== "IPsec overlay tunnels (BFD-monitored)<br/>VPN 10 Corporate | VPN 20 Engineering | VPN 30 Infra Mgmt" ==> E3
  E2 <==> E4
  E1 --- DC
  E3 --- OLD
```

Caption suggestion: *Figure N - Proposed logical SD-WAN design for Northstar: cloud-hosted control plane, dual-transport main site, acquired and future sites joining the same segmented IPsec overlay. Design only; the observed equivalent in the DevNet sandbox is described in SD-03.*

## Figure B - What was observed in the DevNet sandbox (SD-03 evidence)

```mermaid
flowchart LR
  M["Manager01 100.0.0.1"]
  C["Controller01 100.0.0.101"]
  V["Validator01 100.0.0.201"]
  subgraph EDGES["4 × Catalyst 8000V, sites 1-4, each with TLOCs mpls + biz-internet (IPsec)"]
    A["Edge1 10.0.0.1"]
    B["Edge2 10.0.0.2"]
    Cc["Edge3 10.0.0.3"]
    D["Edge4 10.0.0.4"]
  end
  A & B & Cc & D -. "2 DTLS each (1 per colour) + OMP" .-> C
  A & B & Cc & D -. "1 DTLS each" .-> M
  V -. DTLS .- M
  V -. DTLS .- C
  A <== "BFD up, per colour" ==> B
  A <==> Cc
  A <==> D
  B <==> Cc
  B <==> D
  Cc <==> D
```

Caption suggestion: *Figure N - Overlay state retrieved via the SD-WAN Manager API on 12 Nov 2026: 7 reachable devices, 12 IPsec tunnels (6 site pairs × 2 colours, all BFD up), single service VPN (VPN 1). Source: `evidence/api/20261112-224846_overlay_state.json`.*

## Figure C - Integration of Ansible and SD-WAN Manager (INT-01)

```mermaid
flowchart LR
  GIT["Git repository<br/>inventory, playbooks, policy definitions<br/>(source of truth, review)"]
  ANS["Ansible control node<br/>(VPN 30 Infra Mgmt)"]
  SRV["Linux servers at all sites<br/>baseline, services, drift correction"]
  MGR["SD-WAN Manager"]
  EDGES["WAN Edges"]
  NMS["OpenNMS (team)<br/>alarms"]
  PXE["PXE/iPXE (team)<br/>day-0 OS build"]

  GIT --> ANS
  PXE -- "handoff: user + key<br/>(+ unique host keys, EXP-11)" --> SRV
  ANS -- "SSH (AN-02..05)" --> SRV
  ANS -- "REST API / catalystwan<br/>(read proven SD-02, write = design)" --> MGR
  MGR -- "templates / config groups / policy" --> EDGES
  NMS -- "poll API + SNMP/ICMP" --> MGR
  NMS -- "service checks" --> SRV
```

Caption suggestion: *Figure N - Division of responsibilities: Ansible configures servers directly and SD-WAN Manager through its API; edges are configured only by Manager. Solid = demonstrated in PoC (SSH to servers, read-only API); labelled "design" = not tested.*
