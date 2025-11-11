# Makefile for stage4-VPC project

# Variables
VPCCTL = ./vpcctl
CLEANUP = ./cleanup.sh
SUDO = sudo

.PHONY: all create clean help

all: help

# Help message
help:
	@echo "Usage:"
	@echo "  make create      # Create VPC and subnets"
	@echo "  make clean       # Remove all VPC resources"
	@echo "  make test        # Run simple connectivity test (ping)"

# Create VPC and subnets
create:
	@echo "🛠️  Creating VPC and subnets..."
	$(SUDO) $(VPCCTL) create-vpc myvpc 10.0.0.0/16
	$(SUDO) $(VPCCTL) create-subnet myvpc public 10.0.1.0/24 public
	$(SUDO) $(VPCCTL) create-subnet myvpc private 10.0.2.0/24 private
	$(SUDO) $(VPCCTL) setup-nat myvpc public eth0
	@echo "✅ VPC setup completed."

# Clean up all resources
clean:
	@echo "🧹 Cleaning up VPC resources..."
	$(SUDO) $(CLEANUP)

# Optional simple test
test:
	@echo "🌐 Testing connectivity..."
	$(SUDO) $(VPCCTL) exec myvpc public "ping -c 3 10.0.1.1"
	$(SUDO) $(VPCCTL) exec myvpc public "ping -c 3 10.0.2.2"
