#!/bin/bash

# cleanup.sh - Complete VPC resource cleanup

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[CLEANUP]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[CLEANUP]${NC} $*"
}

error() {
    echo -e "${RED}[CLEANUP]${NC} $*"
}

# Check root
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root"
    exit 1
fi

log "🧹 Starting complete VPC cleanup..."

# Remove all network namespaces
log "Removing network namespaces..."
for ns in $(ip netns list | grep -E 'ns-[^ ]*'); do
    log "Deleting namespace: $ns"
    ip netns delete "$ns" 2>/dev/null || warn "Failed to delete namespace $ns"
done

# Remove all bridges
log "Removing bridges..."
for bridge in $(ip link show type bridge 2>/dev/null | grep -o 'br-[^:]*'); do
    log "Deleting bridge: $bridge"
    ip link set "$bridge" down 2>/dev/null || warn "Could not bring down bridge $bridge"
    ip link delete "$bridge" type bridge 2>/dev/null || warn "Could not delete bridge $bridge"
done

# Remove veth interfaces
log "Removing veth interfaces..."
for veth in $(ip link show 2>/dev/null | grep -o 'veth-[^:]*'); do
    log "Deleting veth: $veth"
    ip link delete "$veth" 2>/dev/null || warn "Could not delete veth $veth"
done

# Remove peer interfaces
log "Removing peer interfaces..."
for peer in $(ip link show 2>/dev/null | grep -o 'peer-[^:]*'); do
    log "Deleting peer: $peer"
    ip link delete "$peer" 2>/dev/null || warn "Could not delete peer $peer"
done

# Cleanup iptables rules
log "Cleaning up iptables rules..."

# Remove NAT rules
iptables -t nat -L POSTROUTING --line-numbers 2>/dev/null | grep MASQUERADE | while read line; do
    num=$(echo "$line" | awk '{print $1}')
    iptables -t nat -D POSTROUTING "$num" 2>/dev/null || true
done

# Remove forward rules
iptables -L FORWARD --line-numbers 2>/dev/null | while read line; do
    if echo "$line" | grep -q "br-" || echo "$line" | grep -q "state RELATED"; then
        num=$(echo "$line" | awk '{print $1}')
        iptables -D FORWARD "$num" 2>/dev/null || true
    fi
done

# Remove configuration directory
log "Removing configuration files..."
rm -rf "/tmp/vpc_configs"

# Kill any remaining processes in namespaces
log "Cleaning up processes..."
pkill -f "ip netns exec" 2>/dev/null || true

log "✅ Cleanup completed successfully!"
