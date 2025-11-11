#!/bin/bash
# cleanup.sh - Tear down all VPCs, subnets, namespaces, bridges, and NAT rules

set -e

echo "🧹 Starting cleanup of VPC environment..."

# Function to delete all network namespaces created by vpcctl
cleanup_namespaces() {
    echo "🔹 Cleaning up network namespaces..."
    for ns in $(ip netns list | awk '{print $1}'); do
        if [[ $ns == ns-* ]]; then
            echo "Deleting namespace: $ns"
            ip netns delete "$ns"
        fi
    done
}

# Function to delete all veth interfaces connected to bridges
cleanup_veths() {
    echo "🔹 Cleaning up veth interfaces..."
    for veth in $(ip link show | awk -F: '/veth_/ {print $2}' | tr -d ' '); do
        echo "Deleting veth: $veth"
        ip link delete "$veth" 2>/dev/null || true
    done
}

# Function to delete all bridges created by vpcctl
cleanup_bridges() {
    echo "🔹 Cleaning up bridges..."
    for br in $(ip link show | awk -F: '/br_/ {print $2}' | tr -d ' '); do
        echo "Deleting bridge: $br"
        ip link set "$br" down
        ip link delete "$br" type bridge
    done
}

# Function to remove NAT rules set up by vpcctl
cleanup_nat() {
    echo "🔹 Cleaning up NAT rules..."
    # Flush all POSTROUTING rules from nat table
    iptables -t nat -F
    # Reset forwarding rules
    iptables -F
    # Optionally, disable IP forwarding
    sysctl -w net.ipv4.ip_forward=0
}

# Run cleanup functions
cleanup_namespaces
cleanup_veths
cleanup_bridges
cleanup_nat

echo "✅ Cleanup completed. All VPC resources removed."
