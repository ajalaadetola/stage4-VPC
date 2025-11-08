#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

class VPCManager:
    def __init__(self):
        self.vpc_dir = Path("/tmp/vpc_configs")
        self.vpc_dir.mkdir(exist_ok=True)
        
    def run_cmd(self, cmd, check=True):
        """Execute shell command with error handling"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ Error executing: {cmd}")
            print(f"Error: {e.stderr}")
            return None

    def log(self, message):
        """Simple logging with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def create_vpc(self, name, cidr):
        """Create a new VPC with bridge"""
        self.log(f"🚀 Creating VPC: {name} with CIDR: {cidr}")
        
        # Validate CIDR
        if not self.validate_cidr(cidr):
            return False

        # Create bridge
        bridge_name = f"br-{name}"
        if not self.run_cmd(f"ip link show {bridge_name}", check=False):
            self.run_cmd(f"ip link add {bridge_name} type bridge")
            self.run_cmd(f"ip link set {bridge_name} up")
            self.log(f"✅ Created bridge: {bridge_name}")
        else:
            self.log(f"⚠️ Bridge {bridge_name} already exists")

        # Store VPC config
        vpc_config = {
            "name": name,
            "cidr": cidr,
            "bridge": bridge_name,
            "subnets": {}
        }
        
        config_file = self.vpc_dir / f"{name}.json"
        with open(config_file, 'w') as f:
            json.dump(vpc_config, f, indent=2)
            
        self.log(f"✅ VPC {name} created successfully")
        return True

    def delete_vpc(self, name):
        """Delete a VPC and all its resources"""
        self.log(f"🗑️ Deleting VPC: {name}")
        
        config_file = self.vpc_dir / f"{name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {name} not found")
            return False

        # Load config to get resources
        with open(config_file) as f:
            config = json.load(f)

        # Delete all subnets first
        for subnet_name in list(config.get("subnets", {}).keys()):
            self.delete_subnet(name, subnet_name)

        # Delete bridge
        bridge_name = config["bridge"]
        self.run_cmd(f"ip link set {bridge_name} down", check=False)
        self.run_cmd(f"ip link delete {bridge_name} type bridge", check=False)
        self.log(f"✅ Deleted bridge: {bridge_name}")

        # Remove config file
        config_file.unlink()
        self.log(f"✅ VPC {name} deleted successfully")
        return True

    def create_subnet(self, vpc_name, subnet_name, cidr, subnet_type="private"):
        """Create a subnet in VPC"""
        self.log(f"🔧 Creating subnet: {subnet_name} in VPC: {vpc_name} (CIDR: {cidr}, Type: {subnet_type})")
        
        config_file = self.vpc_dir / f"{vpc_name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {vpc_name} not found")
            return False

        # Load VPC config
        with open(config_file) as f:
            config = json.load(f)

        # Create network namespace
        ns_name = f"ns-{vpc_name}-{subnet_name}"
        if not self.run_cmd(f"ip netns list | grep -q {ns_name}", check=False):
            self.run_cmd(f"ip netns add {ns_name}")
            self.log(f"✅ Created namespace: {ns_name}")
        else:
            self.log(f"⚠️ Namespace {ns_name} already exists")

        # Create veth pair
        veth_host = f"veth-{subnet_name}-host"
        veth_ns = f"veth-{subnet_name}-ns"
        
        self.run_cmd(f"ip link add {veth_host} type veth peer name {veth_ns}")
        self.run_cmd(f"ip link set {veth_ns} netns {ns_name}")
        
        # Configure host side
        self.run_cmd(f"ip link set {veth_host} master {config['bridge']}")
        self.run_cmd(f"ip link set {veth_host} up")
        
        # Configure namespace side
        self.run_cmd(f"ip netns exec {ns_name} ip link set lo up")
        self.run_cmd(f"ip netns exec {ns_name} ip link set {veth_ns} up")
        self.run_cmd(f"ip netns exec {ns_name} ip addr add {cidr} dev {veth_ns}")
        
        # Set default route (using first IP in subnet as gateway)
        gateway_ip = cidr.split('/')[0][:-1] + "1"
        self.run_cmd(f"ip netns exec {ns_name} ip route add default via {gateway_ip}")

        # Update config
        config["subnets"][subnet_name] = {
            "cidr": cidr,
            "type": subnet_type,
            "namespace": ns_name,
            "veth_host": veth_host,
            "veth_ns": veth_ns
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        self.log(f"✅ Subnet {subnet_name} created successfully")
        return True

    def delete_subnet(self, vpc_name, subnet_name):
        """Delete a subnet"""
        self.log(f"🗑️ Deleting subnet: {subnet_name} from VPC: {vpc_name}")
        
        config_file = self.vpc_dir / f"{vpc_name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {vpc_name} not found")
            return False

        with open(config_file) as f:
            config = json.load(f)

        if subnet_name not in config["subnets"]:
            self.log(f"❌ Subnet {subnet_name} not found in VPC {vpc_name}")
            return False

        subnet_info = config["subnets"][subnet_name]
        
        # Delete namespace (this automatically removes veth pair)
        self.run_cmd(f"ip netns delete {subnet_info['namespace']}", check=False)
        
        # Remove from config
        del config["subnets"][subnet_name]
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        self.log(f"✅ Subnet {subnet_name} deleted successfully")
        return True

    def setup_nat(self, vpc_name, public_subnet, host_interface="eth0"):
        """Setup NAT for public subnet internet access"""
        self.log(f"🌐 Setting up NAT for VPC: {vpc_name}, Public Subnet: {public_subnet}")
        
        config_file = self.vpc_dir / f"{vpc_name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {vpc_name} not found")
            return False

        with open(config_file) as f:
            config = json.load(f)

        if public_subnet not in config["subnets"]:
            self.log(f"❌ Subnet {public_subnet} not found")
            return False

        # Enable IP forwarding
        self.run_cmd("sysctl -w net.ipv4.ip_forward=1")
        
        # Get VPC CIDR
        vpc_cidr = config["cidr"]
        
        # Configure iptables for NAT
        self.run_cmd(f"iptables -t nat -A POSTROUTING -s {vpc_cidr} -o {host_interface} -j MASQUERADE")
        self.run_cmd(f"iptables -A FORWARD -i {config['bridge']} -o {host_interface} -j ACCEPT")
        self.run_cmd(f"iptables -A FORWARD -i {host_interface} -o {config['bridge']} -m state --state RELATED,ESTABLISHED -j ACCEPT")
        
        self.log(f"✅ NAT setup completed for VPC {vpc_name}")
        return True

    def exec_command(self, vpc_name, subnet_name, command):
        """Execute command in subnet namespace"""
        config_file = self.vpc_dir / f"{vpc_name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {vpc_name} not found")
            return False

        with open(config_file) as f:
            config = json.load(f)

        if subnet_name not in config["subnets"]:
            self.log(f"❌ Subnet {subnet_name} not found")
            return False

        ns_name = config["subnets"][subnet_name]["namespace"]
        full_cmd = f"ip netns exec {ns_name} {command}"
        
        self.log(f"🔧 Executing in {subnet_name}: {command}")
        result = self.run_cmd(full_cmd, check=False)
        
        if result and result.stdout:
            print(result.stdout)
        if result and result.stderr:
            print(result.stderr)
            
        return result.returncode == 0 if result else False

    def list_vpcs(self):
        """List all VPCs and their subnets"""
        self.log("📋 Listing all VPCs:")
        
        vpc_files = list(self.vpc_dir.glob("*.json"))
        if not vpc_files:
            print("No VPCs found")
            return

        for vpc_file in vpc_files:
            with open(vpc_file) as f:
                config = json.load(f)
            
            print(f"\nVPC: {config['name']} ({config['cidr']})")
            print(f"Bridge: {config['bridge']}")
            print("Subnets:")
            
            for subnet_name, subnet_info in config.get("subnets", {}).items():
                print(f"  - {subnet_name}: {subnet_info['cidr']} ({subnet_info['type']})")

    def validate_cidr(self, cidr):
        """Basic CIDR validation"""
        try:
            ip, mask = cidr.split('/')
            mask = int(mask)
            parts = ip.split('.')
            
            if len(parts) != 4:
                return False
            if not all(0 <= int(p) <= 255 for p in parts):
                return False
            if not 0 <= mask <= 32:
                return False
                
            return True
        except:
            return False

    def apply_firewall(self, vpc_name, subnet_name, rules_file=None):
        """Apply basic firewall rules to subnet"""
        self.log(f"🛡️ Applying firewall rules to {subnet_name}")
        
        config_file = self.vpc_dir / f"{vpc_name}.json"
        if not config_file.exists():
            self.log(f"❌ VPC {vpc_name} not found")
            return False

        with open(config_file) as f:
            config = json.load(f)

        if subnet_name not in config["subnets"]:
            self.log(f"❌ Subnet {subnet_name} not found")
            return False

        ns_name = config["subnets"][subnet_name]["namespace"]
        
        # Basic firewall setup
        cmds = [
            f"ip netns exec {ns_name} iptables -F",
            f"ip netns exec {ns_name} iptables -P INPUT DROP",
            f"ip netns exec {ns_name} iptables -P FORWARD DROP", 
            f"ip netns exec {ns_name} iptables -P OUTPUT ACCEPT",
            f"ip netns exec {ns_name} iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
            f"ip netns exec {ns_name} iptables -A INPUT -i lo -j ACCEPT",
        ]
        
        # Apply custom rules from file if provided
        if rules_file and os.path.exists(rules_file):
            try:
                with open(rules_file) as f:
                    rules = json.load(f)
                
                for rule in rules.get("ingress", []):
                    port = rule.get("port")
                    protocol = rule.get("protocol", "tcp")
                    action = rule.get("action", "allow")
                    
                    if action == "allow":
                        cmds.append(f"ip netns exec {ns_name} iptables -A INPUT -p {protocol} --dport {port} -j ACCEPT")
                    else:
                        cmds.append(f"ip netns exec {ns_name} iptables -A INPUT -p {protocol} --dport {port} -j DROP")
                        
            except Exception as e:
                self.log(f"❌ Error reading rules file: {e}")
                return False

        # Default allow SSH and HTTP for demo
        cmds.extend([
            f"ip netns exec {ns_name} iptables -A INPUT -p tcp --dport 22 -j ACCEPT",
            f"ip netns exec {ns_name} iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
        ])

        for cmd in cmds:
            self.run_cmd(cmd)

        self.log(f"✅ Firewall rules applied to {subnet_name}")
        return True

def main():
    parser = argparse.ArgumentParser(description="vpcctl - Manage Linux VPCs")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create VPC
    create_parser = subparsers.add_parser("create-vpc", help="Create a new VPC")
    create_parser.add_argument("name", help="VPC name")
    create_parser.add_argument("cidr", help="VPC CIDR block (e.g., 10.0.0.0/16)")

    # Delete VPC  
    delete_parser = subparsers.add_parser("delete-vpc", help="Delete a VPC")
    delete_parser.add_argument("name", help="VPC name")

    # Create subnet
    subnet_parser = subparsers.add_parser("create-subnet", help="Create a subnet")
    subnet_parser.add_argument("vpc", help="VPC name")
    subnet_parser.add_argument("name", help="Subnet name") 
    subnet_parser.add_argument("cidr", help="Subnet CIDR")
    subnet_parser.add_argument("--type", choices=["public", "private"], default="private", help="Subnet type")

    # Delete subnet
    del_subnet_parser = subparsers.add_parser("delete-subnet", help="Delete a subnet")
    del_subnet_parser.add_argument("vpc", help="VPC name")
    del_subnet_parser.add_argument("name", help="Subnet name")

    # Setup NAT
    nat_parser = subparsers.add_parser("setup-nat", help="Setup NAT for public subnet")
    nat_parser.add_argument("vpc", help="VPC name")
    nat_parser.add_argument("subnet", help="Public subnet name")
    nat_parser.add_argument("--interface", default="eth0", help="Host interface for NAT")

    # Execute command
    exec_parser = subparsers.add_parser("exec", help="Execute command in subnet namespace")
    exec_parser.add_argument("vpc", help="VPC name")
    exec_parser.add_argument("subnet", help="Subnet name")
    exec_parser.add_argument("command", help="Command to execute")

    # List VPCs
    subparsers.add_parser("list-vpcs", help="List all VPCs")

    # Apply firewall
    firewall_parser = subparsers.add_parser("apply-firewall", help="Apply firewall rules")
    firewall_parser.add_argument("vpc", help="VPC name")
    firewall_parser.add_argument("subnet", help="Subnet name")
    firewall_parser.add_argument("--rules-file", help="JSON file with firewall rules")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = VPCManager()

    try:
        if args.command == "create-vpc":
            manager.create_vpc(args.name, args.cidr)
        elif args.command == "delete-vpc":
            manager.delete_vpc(args.name)
        elif args.command == "create-subnet":
            manager.create_subnet(args.vpc, args.name, args.cidr, args.type)
        elif args.command == "delete-subnet":
            manager.delete_subnet(args.vpc, args.name)
        elif args.command == "setup-nat":
            manager.setup_nat(args.vpc, args.subnet, args.interface)
        elif args.command == "exec":
            manager.exec_command(args.vpc, args.subnet, args.command)
        elif args.command == "list-vpcs":
            manager.list_vpcs()
        elif args.command == "apply-firewall":
            manager.apply_firewall(args.vpc, args.subnet, args.rules_file)
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() != 0:
        print("❌ This script must be run as root")
        sys.exit(1)
    
    main()
