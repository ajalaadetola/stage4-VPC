#!/bin/bash

# setup-demo.sh - Setup and run the VPC demo

echo "🚀 Setting up VPC Demo Environment..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo $0"
    exit 1
fi

# Make scripts executable
chmod +x vpcctl cleanup.sh

# Create directories
echo "Creating directories..."
mkdir -p examples logs

# Create firewall rules example
cat > examples/firewall-rules.json << 'EOF'
{
  "ingress": [
    {"port": 80, "protocol": "tcp", "action": "allow", "description": "Allow HTTP"},
    {"port": 443, "protocol": "tcp", "action": "allow", "description": "Allow HTTPS"},
    {"port": 22, "protocol": "tcp", "action": "allow", "description": "Allow SSH"},
    {"port": 8080, "protocol": "tcp", "action": "allow", "description": "Allow custom app"},
    {"port": 3306, "protocol": "tcp", "action": "deny", "description": "Block MySQL"}
  ]
}
EOF

# Create simple web server
cat > examples/web-server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>VPC Web Server</h1><p>Hello from VPC subnet!</p></body></html>')

if __name__ == '__main__':
    port = 8080
    with socketserver.TCPServer(("", port), MyHTTPRequestHandler) as httpd:
        print(f"Web server running on port {port}")
        httpd.serve_forever()
EOF

chmod +x examples/web-server.py

# Create empty log file
touch logs/vpc-demo.log

echo "✅ Demo environment setup complete!"
echo ""
echo "Directory structure created:"
find . -type f -name "*.json" -o -name "*.py" -o -name "*.log" | sort
echo ""
echo "To run the demo:"
echo "  sudo ./vpcctl demo"
echo ""
echo "To run manually:"
echo "  sudo ./vpcctl create-vpc myvpc 10.0.0.0/16"
echo "  sudo ./vpcctl create-subnet myvpc public 10.0.1.0/24 public"
echo "  sudo ./vpcctl create-subnet myvpc private 10.0.2.0/24 private"
echo "  sudo ./vpcctl setup-nat myvpc public eth0"
echo "  sudo ./vpcctl list-vpcs"
