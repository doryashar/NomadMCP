#!/bin/bash
# Installation script for NomadMCP

set -e

echo "🚀 Installing NomadMCP..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Error: Python 3.10 or higher is required (found: $python_version)"
    exit 1
fi
echo "✓ Python $python_version detected"

# Check if opencode is installed
if ! command -v opencode &> /dev/null; then
    echo "⚠️  Warning: OpenCode CLI not found"
    echo "   Install with: npm install -g @opencode/cli"
else
    echo "✓ OpenCode CLI found"
fi

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "⚠️  Warning: GitHub CLI not found"
    echo "   Install with: brew install gh (macOS) or see https://cli.github.com/"
else
    echo "✓ GitHub CLI found"
fi

echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Configure the MCP server in your Claude Code settings:"
echo ""
echo "   {"
echo "     \"mcpServers\": {"
echo "       \"nomad-mcp\": {"
echo "         \"command\": \"python3\","
echo "         \"args\": [\"-m\", \"src.server\"],"
echo "         \"cwd\": \"$(pwd)\""
echo "       }"
echo "     }"
echo "   }"
echo ""
echo "2. Authenticate with GitHub CLI (if not already done):"
echo "   gh auth login"
echo ""
echo "3. Test the server:"
echo "   python3 -m src.server"
echo ""
