#!/bin/bash

set -e

echo "🧹 Starting cleanup of VPC environment..."

# 1️⃣ Clean up network namespaces
echo "🔹 Cleaning up network namespaces..."
for ns in $(ip netns list | awk '{print $1}'); do
    echo "Deleting namespace: $ns"
    ip netns delete "$ns"
done

# 2️⃣ Clean up veth interfaces
echo "🔹 Cleaning up veth interfaces..."
for veth in $(ip link show | awk -F: '/veth_/ {print $2}' | tr -d ' '); do
    echo "Deleting veth: $veth"
    ip link delete "$veth" || true
done

# 3️⃣ Clean up bridges
echo "🔹 Cleaning up bridges..."
for br in $(brctl show | awk 'NR>1 {print $1}'); do
    echo "Deleting bridge: $br"
    ip link set "$br" down || true
    brctl delbr "$br" || true
done

# 4️⃣ Clean up NAT rules
echo "🔹 Cleaning up NAT rules..."
sysctl -w net.ipv4.ip_forward=0
iptables -t nat -F
iptables -F
iptables -X

# 5️⃣ Remove VPC configurations
VPC_DIR="/tmp/vpc_configs"
if [ -d "$VPC_DIR" ]; then
    echo "🔹 Removing VPC configuration directory: $VPC_DIR"
    rm -rf "$VPC_DIR"
fi

echo "✅ Cleanup completed. All VPC resources removed."
