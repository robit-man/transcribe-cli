---
name: container-forensics
description: "Docker and Kubernetes forensic investigation covering container inventory, privilege checks, image verification, escape detection, and K8s RBAC audit"
tools: Bash, Read, Write, Glob, Grep
---

# container-forensics

Investigates containerized environments for signs of compromise, misconfiguration, or container escape. Covers standalone Docker hosts and Kubernetes clusters. Produces a structured findings document with severity tagging.

## Triggers

- "container forensics"
- "docker investigation"
- "kubernetes forensics"
- "investigate containers"
- "k8s forensics"

## Purpose

Container environments introduce unique attack surfaces: privileged containers, host namespace access, writable image layers, and overpermissioned service accounts. Standard host forensics misses these vectors. This skill applies container-aware investigation procedures and maps findings to MITRE ATT&CK for Containers.

## Behavior

When triggered, this skill:

1. **Detect environment type**:
   - Check for Docker: `docker info 2>/dev/null`
   - Check for Kubernetes: `kubectl cluster-info 2>/dev/null` or presence of `/var/run/secrets/kubernetes.io/`
   - Check for containerd-only (no Docker): `ctr version 2>/dev/null`
   - Determine if running inside a container: check for `/.dockerenv`, inspect cgroup paths

2. **Docker — container inventory and privilege audit**:
   - List all containers (running and stopped): `docker ps -a --format '{{json .}}'`
   - Flag containers with dangerous flags:
     - `--privileged`: `docker inspect <id> | jq '.[].HostConfig.Privileged'`
     - Host network mode: `NetworkMode == "host"`
     - Host PID namespace: `PidMode == "host"`
     - Dangerous capability additions: `CapAdd` containing `SYS_ADMIN`, `NET_ADMIN`, `SYS_PTRACE`
   - Enumerate bind mounts of sensitive host paths (`/`, `/etc`, `/var/run/docker.sock`, `/proc`, `/sys`)

3. **Docker — image verification**:
   - List all local images with digests: `docker images --digests`
   - Check image provenance: compare `RepoDigests` against expected registry
   - Flag images tagged `latest` without a pinned digest
   - Inspect image build history for suspicious `RUN` layers: `docker history --no-trunc <image>`
   - Check for images not associated with any running or stopped container (orphaned images)

4. **Docker — volume and filesystem inspection**:
   - List named volumes: `docker volume ls`
   - Inspect volumes mounted into containers for sensitive data paths
   - Examine container overlay filesystem changes: `docker diff <container_id>`
   - Flag containers with writable root filesystems where `ReadonlyRootfs` is false

5. **Docker — socket and API exposure**:
   - Check if Docker socket is bind-mounted into any container — this grants effective root on the host
   - Check for TCP Docker API exposure: `ss -tlnp | grep ':2375\|:2376'`
   - Review Docker daemon configuration: `/etc/docker/daemon.json`

6. **Container escape indicators**:
   - Processes running in container namespaces that share host PID/network: compare namespace inodes in `/proc/1/ns/` vs `/proc/<container-pid>/ns/`
   - Unexpected cgroup escape patterns in `/proc/<pid>/cgroup`
   - Files written to host paths from within container overlay mounts
   - `runc` or `containerd-shim` process anomalies in host process tree

7. **Kubernetes — cluster-level audit**:
   - List all pods across all namespaces: `kubectl get pods -A -o json`
   - Flag pods running as root: `.spec.containers[].securityContext.runAsUser == 0` or unset
   - Flag pods with `hostPID`, `hostNetwork`, or `hostIPC` set to true
   - Flag pods mounting the Docker socket or host paths
   - List privileged containers across the cluster

8. **Kubernetes — RBAC audit**:
   - List ClusterRoleBindings granting `cluster-admin`: `kubectl get clusterrolebindings -o json | jq '...'`
   - Identify service accounts with wildcard permissions or `*` verbs on sensitive resources
   - Check for default service account token automounting: `automountServiceAccountToken: true`
   - List RoleBindings in high-value namespaces (kube-system, kube-public)

9. **Kubernetes — pod security and network policy**:
   - Check for absent NetworkPolicies (pods with unrestricted egress/ingress)
   - Review PodSecurityAdmission or OPA/Gatekeeper policy coverage
   - List nodes and check for unauthorized node additions: `kubectl get nodes -o wide`

10. **Write findings document**:
    - Save to `.aiwg/forensics/findings/container-forensics.md`
    - Group by: Docker findings, Kubernetes findings, escape indicators
    - Tag each finding: INFO, SUSPICIOUS, MALICIOUS

## Usage Examples

### Example 1 — Docker host
```
docker investigation
```
Audits the local Docker daemon.

### Example 2 — Kubernetes cluster
```
kubernetes forensics
```
Requires `kubectl` configured with appropriate credentials.

### Example 3 — Inside a container
```
container forensics
```
Detects the container context and adjusts collection accordingly.

## Output Locations

- Findings: `.aiwg/forensics/findings/container-forensics.md`
- Raw Docker inspection: `.aiwg/forensics/evidence/docker-inspect.json`
- K8s pod manifest dump: `.aiwg/forensics/evidence/k8s-pods.json`

## Configuration

```yaml
container_forensics:
  dangerous_capabilities:
    - SYS_ADMIN
    - NET_ADMIN
    - SYS_PTRACE
    - SYS_MODULE
  sensitive_host_paths:
    - /
    - /etc
    - /var/run/docker.sock
    - /proc
    - /sys
    - /root
  high_value_namespaces:
    - kube-system
    - kube-public
    - default
```
