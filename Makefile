.PHONY: install test demo clean help

install:
	@echo "Installing vpcctl..."
	chmod +x vpcctl cleanup.sh
	cp vpcctl /usr/local/bin/vpcctl || echo "Note: Could not install to /usr/local/bin"

test:
	@echo "Running basic VPC test..."
	sudo ./vpcctl create-vpc testvpc 10.100.0.0/16
	sudo ./vpcctl create-subnet testvpc public 10.100.1.0/24 public
	sudo ./vpcctl create-subnet testvpc private 10.100.2.0/24 private
	sudo ./vpcctl list-vpcs
	sudo ./vpcctl delete-vpc testvpc

demo:
	@echo "Running VPC demo..."
	sudo ./vpcctl create-vpc demovpc 10.200.0.0/16
	sudo ./vpcctl create-subnet demovpc public 10.200.1.0/24 public
	sudo ./vpcctl create-subnet demovpc private 10.200.2.0/24 private
	sudo ./vpcctl setup-nat demovpc public eth0
	sudo ./vpcctl list-vpcs
	@echo "Demo completed. Check connectivity with:"
	@echo "  sudo ./vpcctl exec demovpc public 'ping -c 3 10.200.2.10'"
	@echo "Run 'make clean' to cleanup."

clean:
	sudo ./cleanup.sh

help:
	@echo "Available targets:"
	@echo "  install - Make scripts executable"
	@echo "  test    - Run basic functionality test"
	@echo "  demo    - Run full demo"
	@echo "  clean   - Cleanup all VPC resources"
