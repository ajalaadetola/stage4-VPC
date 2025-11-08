#!/bin/bash

# vpcctl - Linux VPC Manager
# Pure bash implementation using only Linux native networking tools

set -e

# Configuration
VPC_DIR="/tmp/vpc_configs"
LOG_PREFIX="vpcctl"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $([ -n "$VPC_NAME" ] && echo "[$VPC_NAME] ")${*}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $([ -n "$VPC_NAME" ] && echo "[$VPC_NAME] ")${*}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $([ -n "$VPC_NAME" ] && echo "[$VPC_NAME] ")${*}"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $([ -n "$VPC_NAME" ] && echo "[$VPC_NAME] ")${*}"
}

# Validation functions
validate_cidr() {
    local cidr="$1"
    if ! echo "$cidr" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'; then
        log_error "Invalid CIDR format: $cidr"
        return 1
    fi
    
    local ip=$(echo "$cidr" | cut -d'/' -f1)
    local mask=$(echo "$cidr" | cut -d'/' -f2)
    
    # Validate IP components
    local IFS='.'
    local -a octets
    read -ra octets <<< "$ip"
    
    if [ ${#octets[@]} -ne 4 ]; then
        log_error "Invalid IP address: $ip"
        return 1
    fi
    
    for octet in "${octets[@]}"; do
        if [ "$octet" -lt 0 ] || [ "$octet" -gt 255 ]; then
            log_error "Invalid IP octet: $octet"
            return 1
        fi
    done
    
    # Validate mask
    if [ "$mask" -lt 0 ] || [ "$mask" -gt 32 ]; then
        log_error "Invalid network mask: $mask"
        return 1
    fi
    
    return 0
}

validate_vpc_name() {
    local name="$1"
    if ! echo "$name" | grep -Eq '^[a-zA-Z0-9_-]+$'; then
        log_error "Invalid VPC name: $name (only alphanumeric, hyphen, underscore allowed)"
        return 1
    fi
    return 0
}

# Command execution with logging
run_cmd() {
    local cmd="$1"
    local check="${2:-true}"
    
    log_debug "Executing: $cmd"
    
    if eval "$cmd"; then
        return 0
    else
        local result=$?
        if [ "$check" = "true" ]; then
            log_error "Command failed: $cmd (exit code: $result)"
            return $result
        else
            return $result
        fi
    fi
}

# Network namespace operations
namespace_exists() {
    ip netns list | grep -q "$1"
}

create_namespace() {
    local ns="$1"
    if ! namespace_exists "$ns"; then
        log_info "Creating network namespace: $ns"
        run_cmd "ip netns add $ns"
    else
        log_warn "Namespace $ns already exists"
    fi
}

delete_namespace() {
    local ns="$1"
    if namespace_exists "$ns"; then
        log_info "Deleting network namespace: $ns"
        run_cmd "ip netns delete $ns"
    fi
}

# Bridge operations
bridge_exists() {
    ip link show "$1" 2>/dev/null | grep -q "$1"
}

create_bridge() {
    local bridge="$1"
    if ! bridge_exists "$bridge"; then
        log_info "Creating bridge: $bridge"
        run_cmd "ip link add $bridge type bridge"
        run_cmd "ip link set $bridge up"
    else
        log_warn "Bridge $bridge already exists"
    fi
}

delete_bridge() {
    local bridge="$1"
    if bridge_exists "$bridge"; then
        log_info "Deleting bridge: $bridge"
        run_cmd "ip link set $bridge down"
        run_cmd "ip link delete $bridge type bridge"
    fi
}

# VPC configuration management
get_vpc_config_path() {
    echo "$VPC_DIR/$1.conf"
}

vpc_exists() {
    [ -f "$(get_vpc_config_path "$1")" ]
}

save_vpc_config() {
    local vpc_name="$1"
    local key="$2"
    local value="$3"
    
    local config_file="$(get_vpc_config_path "$vpc_name")"
    mkdir -p "$VPC_DIR"
    
    if grep -q "^$key=" "$config_file" 2>/dev/null; then
        sed -i "s/^$key=.*/$key=$value/" "$config_file"
    else
        echo "$key=$value" >> "$config_file"
    fi
}

get_vpc_config() {
    local vpc_name="$1"
    local key="$2"
    local config_file="$(get_vpc_config_path "$vpc_name")"
    
    if [ -f "$config_file" ]; then
        grep "^$key=" "$config_file" | cut -d'=' -f2-
    fi
}

# Core VPC operations
create_vpc() {
    local vpc_name="$1"
    local cidr_block="$2"
    
    log_info "🚀 Creating VPC: $vpc_name with CIDR: $cidr_block"
    
    # Validate inputs
    validate_vpc_name "$vpc_name" || return 1
    validate_cidr "$cidr_block" || return 1
    
    # Check if VPC already exists
    if vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name already exists"
        return 1
    fi
    
    # Set global VPC name for logging
    VPC_NAME="$vpc_name"
    
    # Create bridge
    local bridge_name="br-$vpc_name"
    create_bridge "$bridge_name"
    
    # Assign IP to bridge (first IP in CIDR as gateway)
    local gateway_ip="${cidr_block%.*}.1"
    log_info "Assigning gateway IP: $gateway_ip to bridge $bridge_name"
    run_cmd "ip addr add $gateway_ip/$(echo $cidr_block | cut -d'/' -f2) dev $bridge_name"
    
    # Store VPC configuration
    save_vpc_config "$vpc_name" "CIDR" "$cidr_block"
    save_vpc_config "$vpc_name" "BRIDGE" "$bridge_name"
    save_vpc_config "$vpc_name" "GATEWAY" "$gateway_ip"
    save_vpc_config "$vpc_name" "SUBNETS" ""
    
    log_info "✅ VPC $vpc_name created successfully"
}

delete_vpc() {
    local vpc_name="$1"
    
    log_info "🗑️ Deleting VPC: $vpc_name"
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    # Delete all subnets first
    local subnets=$(get_vpc_config "$vpc_name" "SUBNETS")
    if [ -n "$subnets" ]; then
        IFS=',' read -ra subnet_array <<< "$subnets"
        for subnet in "${subnet_array[@]}"; do
            delete_subnet "$vpc_name" "$subnet"
        done
    fi
    
    # Delete bridge
    local bridge_name=$(get_vpc_config "$vpc_name" "BRIDGE")
    delete_bridge "$bridge_name"
    
    # Remove configuration
    rm -f "$(get_vpc_config_path "$vpc_name")"
    
    log_info "✅ VPC $vpc_name deleted successfully"
}

create_subnet() {
    local vpc_name="$1"
    local subnet_name="$2"
    local subnet_cidr="$3"
    local subnet_type="${4:-private}"
    
    log_info "🔧 Creating subnet: $subnet_name (CIDR: $subnet_cidr, Type: $subnet_type)"
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    validate_cidr "$subnet_cidr" || return 1
    
    # Create network namespace for subnet
    local ns_name="ns-$vpc_name-$subnet_name"
    create_namespace "$ns_name"
    
    # Create veth pair
    local veth_host="veth-$subnet_name-host"
    local veth_ns="veth-$subnet_name-ns"
    
    log_info "Creating veth pair: $veth_host <-> $veth_ns"
    run_cmd "ip link add $veth_host type veth peer name $veth_ns"
    
    # Move one end to subnet namespace
    log_info "Moving $veth_ns to namespace $ns_name"
    run_cmd "ip link set $veth_ns netns $ns_name"
    
    # Add host end to bridge
    local bridge_name=$(get_vpc_config "$vpc_name" "BRIDGE")
    log_info "Connecting $veth_host to bridge $bridge_name"
    run_cmd "ip link set $veth_host master $bridge_name"
    run_cmd "ip link set $veth_host up"
    
    # Configure namespace side
    log_info "Configuring network in namespace $ns_name"
    run_cmd "ip netns exec $ns_name ip link set lo up"
    run_cmd "ip netns exec $ns_name ip link set $veth_ns up"
    
    # Assign IP address
    log_info "Assigning IP address: $subnet_cidr to $veth_ns"
    run_cmd "ip netns exec $ns_name ip addr add $subnet_cidr dev $veth_ns"
    
    # Set up routing
    local gateway_ip=$(get_vpc_config "$vpc_name" "GATEWAY")
    log_info "Setting default route via gateway: $gateway_ip"
    run_cmd "ip netns exec $ns_name ip route add default via $gateway_ip"
    
    # Store subnet configuration
    local current_subs=$(get_vpc_config "$vpc_name" "SUBNETS")
    if [ -z "$current_subs" ]; then
        save_vpc_config "$vpc_name" "SUBNETS" "$subnet_name"
    else
        save_vpc_config "$vpc_name" "SUBNETS" "$current_subs,$subnet_name"
    fi
    
    save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_NS" "$ns_name"
    save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_CIDR" "$subnet_cidr"
    save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_TYPE" "$subnet_type"
    save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_VETH_HOST" "$veth_host"
    save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_VETH_NS" "$veth_ns"
    
    log_info "✅ Subnet $subnet_name created successfully in VPC $vpc_name"
}

delete_subnet() {
    local vpc_name="$1"
    local subnet_name="$2"
    
    log_info "🗑️ Deleting subnet: $subnet_name from VPC: $vpc_name"
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    local ns_name=$(get_vpc_config "$vpc_name" "SUBNET_${subnet_name}_NS")
    local veth_host=$(get_vpc_config "$vpc_name" "SUBNET_${subnet_name}_VETH_HOST")
    
    # Delete namespace (this automatically removes veth pair)
    delete_namespace "$ns_name"
    
    # Remove veth host interface if still exists
    if ip link show "$veth_host" >/dev/null 2>&1; then
        log_info "Removing veth interface: $veth_host"
        run_cmd "ip link delete $veth_host"
    fi
    
    # Remove subnet from configuration
    local current_subs=$(get_vpc_config "$vpc_name" "SUBNETS")
    local new_subs=$(echo "$current_subs" | sed "s/,$subnet_name//g" | sed "s/^$subnet_name,//" | sed "s/^$subnet_name$//")
    save_vpc_config "$vpc_name" "SUBNETS" "$new_subs"
    
    # Remove subnet-specific configs
    for key in NS CIDR TYPE VETH_HOST VETH_NS; do
        save_vpc_config "$vpc_name" "SUBNET_${subnet_name}_${key}" ""
    done
    
    log_info "✅ Subnet $subnet_name deleted successfully"
}

setup_nat() {
    local vpc_name="$1"
    local public_subnet="$2"
    local host_interface="${3:-eth0}"
    
    log_info "🌐 Setting up NAT for VPC: $vpc_name, Public Subnet: $public_subnet"
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    # Enable IP forwarding
    log_info "Enabling IP forwarding"
    run_cmd "sysctl -w net.ipv4.ip_forward=1"
    
    # Get VPC CIDR
    local vpc_cidr=$(get_vpc_config "$vpc_name" "CIDR")
    local bridge_name=$(get_vpc_config "$vpc_name" "BRIDGE")
    
    # Configure iptables for NAT
    log_info "Configuring iptables NAT rules"
    run_cmd "iptables -t nat -A POSTROUTING -s $vpc_cidr -o $host_interface -j MASQUERADE"
    run_cmd "iptables -A FORWARD -i $bridge_name -o $host_interface -j ACCEPT"
    run_cmd "iptables -A FORWARD -i $host_interface -o $bridge_name -m state --state RELATED,ESTABLISHED -j ACCEPT"
    
    log_info "✅ NAT setup completed for VPC $vpc_name"
}

exec_in_subnet() {
    local vpc_name="$1"
    local subnet_name="$2"
    local command="$3"
    
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    local ns_name=$(get_vpc_config "$vpc_name" "SUBNET_${subnet_name}_NS")
    if [ -z "$ns_name" ]; then
        log_error "Subnet $subnet_name not found in VPC $vpc_name"
        return 1
    fi
    
    log_info "Executing in subnet $subnet_name: $command"
    run_cmd "ip netns exec $ns_name $command"
}

list_vpcs() {
    log_info "📋 Listing all VPCs:"
    
    if [ ! -d "$VPC_DIR" ] || [ -z "$(ls -A "$VPC_DIR" 2>/dev/null)" ]; then
        echo "No VPCs found"
        return
    fi
    
    for config_file in "$VPC_DIR"/*.conf; do
        local vpc_name=$(basename "$config_file" .conf)
        local cidr=$(get_vpc_config "$vpc_name" "CIDR")
        local bridge=$(get_vpc_config "$vpc_name" "BRIDGE")
        local subnets=$(get_vpc_config "$vpc_name" "SUBNETS")
        
        echo ""
        echo "VPC: $vpc_name"
        echo "  CIDR: $cidr"
        echo "  Bridge: $bridge"
        echo "  Subnets: ${subnets:-None}"
        
        if [ -n "$subnets" ]; then
            IFS=',' read -ra subnet_array <<< "$subnets"
            for subnet in "${subnet_array[@]}"; do
                local subnet_cidr=$(get_vpc_config "$vpc_name" "SUBNET_${subnet}_CIDR")
                local subnet_type=$(get_vpc_config "$vpc_name" "SUBNET_${subnet}_TYPE")
                echo "    - $subnet: $subnet_cidr ($subnet_type)"
            done
        fi
    done
}

apply_firewall() {
    local vpc_name="$1"
    local subnet_name="$2"
    local rules_file="$3"
    
    log_info "🛡️ Applying firewall rules to subnet: $subnet_name"
    VPC_NAME="$vpc_name"
    
    if ! vpc_exists "$vpc_name"; then
        log_error "VPC $vpc_name not found"
        return 1
    fi
    
    local ns_name=$(get_vpc_config "$vpc_name" "SUBNET_${subnet_name}_NS")
    if [ -z "$ns_name" ]; then
        log_error "Subnet $subnet_name not found in VPC $vpc_name"
        return 1
    fi
    
    # Basic firewall setup
    log_info "Setting up basic firewall rules"
    run_cmd "ip netns exec $ns_name iptables -F"
    run_cmd "ip netns exec $ns_name iptables -P INPUT DROP"
    run_cmd "ip netns exec $ns_name iptables -P FORWARD DROP"
    run_cmd "ip netns exec $ns_name iptables -P OUTPUT ACCEPT"
    run_cmd "ip netns exec $ns_name iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT"
    run_cmd "ip netns exec $ns_name iptables -A INPUT -i lo -j ACCEPT"
    
    # Apply custom rules from file if provided
    if [ -n "$rules_file" ] && [ -f "$rules_file" ]; then
        log_info "Applying custom rules from: $rules_file"
        apply_custom_firewall_rules "$ns_name" "$rules_file"
    else
        # Default rules for demo
        log_info "Applying default firewall rules"
        run_cmd "ip netns exec $ns_name iptables -A INPUT -p tcp --dport 22 -j ACCEPT"
        run_cmd "ip netns exec $ns_name iptables -A INPUT -p tcp --dport 80 -j ACCEPT"
        run_cmd "ip netns exec $ns_name iptables -A INPUT -p tcp --dport 443 -j ACCEPT"
    fi
    
    log_info "✅ Firewall rules applied to subnet $subnet_name"
}

apply_custom_firewall_rules() {
    local ns_name="$1"
    local rules_file="$2"
    
    # Simple JSON parsing (basic implementation)
    while IFS= read -r line; do
        if echo "$line" | grep -q '"port"'; then
            local port=$(echo "$line" | grep -o '[0-9]\+')
            local protocol="tcp"
            local action="ACCEPT"
            
            # Look for protocol in next lines
            if IFS= read -r next_line && echo "$next_line" | grep -q '"protocol"'; then
                protocol=$(echo "$next_line" | grep -o '"tcp"\|\"udp\"' | tr -d '"')
            fi
            
            if IFS= read -r action_line && echo "$action_line" | grep -q '"action"'; then
                local action_val=$(echo "$action_line" | grep -o '"allow"\|\"deny\"' | tr -d '"')
                if [ "$action_val" = "allow" ]; then
                    action="ACCEPT"
                else
                    action="DROP"
                fi
            fi
            
            if [ -n "$port" ] && [ -n "$protocol" ]; then
                log_info "Adding rule: $protocol port $port -> $action"
                run_cmd "ip netns exec $ns_name iptables -A INPUT -p $protocol --dport $port -j $action"
            fi
        fi
    done < "$rules_file"
}

# Main CLI handler
usage() {
    cat << EOF
Usage: $0 <command> [arguments]

Commands:
  create-vpc <name> <cidr>                 Create a new VPC
  delete-vpc <name>                        Delete a VPC
  create-subnet <vpc> <name> <cidr> [type] Create subnet (public/private)
  delete-subnet <vpc> <name>               Delete a subnet
  list-vpcs                                List all VPCs
  setup-nat <vpc> <subnet> [interface]     Setup NAT for public subnet
  exec <vpc> <subnet> <command>            Execute command in subnet
  apply-firewall <vpc> <subnet> [file]     Apply firewall rules

Examples:
  $0 create-vpc myvpc 10.0.0.0/16
  $0 create-subnet myvpc public 10.0.1.0/24 public
  $0 create-subnet myvpc private 10.0.2.0/24 private
  $0 setup-nat myvpc public eth0
  $0 exec myvpc public "ping -c 3 10.0.2.10"
  $0 apply-firewall myvpc public examples/firewall-rules.json

EOF
}

main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi
    
    local command="$1"
    shift
    
    case "$command" in
        create-vpc)
            if [ $# -lt 2 ]; then
                log_error "Usage: create-vpc <name> <cidr>"
                exit 1
            fi
            create_vpc "$1" "$2"
            ;;
        delete-vpc)
            if [ $# -lt 1 ]; then
                log_error "Usage: delete-vpc <name>"
                exit 1
            fi
            delete_vpc "$1"
            ;;
        create-subnet)
            if [ $# -lt 3 ]; then
                log_error "Usage: create-subnet <vpc> <name> <cidr> [type]"
                exit 1
            fi
            create_subnet "$1" "$2" "$3" "$4"
            ;;
        delete-subnet)
            if [ $# -lt 2 ]; then
                log_error "Usage: delete-subnet <vpc> <name>"
                exit 1
            fi
            delete_subnet "$1" "$2"
            ;;
        list-vpcs)
            list_vpcs
            ;;
        setup-nat)
            if [ $# -lt 2 ]; then
                log_error "Usage: setup-nat <vpc> <subnet> [interface]"
                exit 1
            fi
            setup_nat "$1" "$2" "$3"
            ;;
        exec)
            if [ $# -lt 3 ]; then
                log_error "Usage: exec <vpc> <subnet> <command>"
                exit 1
            fi
            exec_in_subnet "$1" "$2" "$3"
            ;;
        apply-firewall)
            if [ $# -lt 2 ]; then
                log_error "Usage: apply-firewall <vpc> <subnet> [rules-file]"
                exit 1
            fi
            apply_firewall "$1" "$2" "$3"
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Check if running as root for most operations
if [ "$1" != "list-vpcs" ] && [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root for network operations"
    exit 1
fi

main "$@"
