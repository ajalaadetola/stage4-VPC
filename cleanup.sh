#!/bin/bash

# cleanup.sh - Complete VPC cleanup script

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
for ns in $(ip netns list | grep -o 'ns-[^ ]*'); do
    log "Deleting namespace: $ns"
    ip netns delete "$ns" 2>/dev/null || warn "Failed to delete namespace $ns"
done

# Remove all bridges
log "Removing bridges..."
for bridge in $(ip link show type bridge | grep -o 'br-[^:]*'); do
    log "Deleting bridge: $bridge"
    ip link set "$bridge" down 2>/dev/null || warn "Could not bring down bridge $bridge"
    ip link delete "$bridge" type bridge 2>/dev/null || warn "Could not delete bridge $bridge"
done

# Remove veth interfaces (cleanup any leftovers)
log "Removing veth interfaces..."
for veth in $(ip link show | grep -o 'veth-[^:]*'); do
    log "Deleting veth: $veth"
    ip link delete "$veth" 2>/dev/null || warn "Could not delete veth $veth"
done

# Cleanup iptables rules
log "Cleaning up iptables rules..."

# Remove NAT rules
iptables -t nat -L POSTROUTING --line-numbers | grep MASQUERADE | while read line; do
    local num=$(echo "$line" | awk '{print $1}')
    iptables -t nat -D POSTROUTING "$num" 2>/dev/null || true
done

# Remove forward rules
iptables -L FORWARD --line-numbers | while read line; do
    if echo "$line" | grep -q "br-" || echo "$line" | grep -q "state RELATED"; then
        local num=$(echo "$line" | awk '{print $1}')
        iptables -D FORWARD "$num" 2>/dev/null || true
    fi
done

# Reset policies
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

# Remove configuration directory
log "Removing configuration files..."
rm -rf "/tmp/vpc_configs"

log "✅ Cleanup completed successfully!"
