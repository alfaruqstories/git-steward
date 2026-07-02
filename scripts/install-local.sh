#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${HOME}/.local/bin"
mkdir -p "$bin_dir"

cat > "${bin_dir}/git-steward" <<SH
#!/usr/bin/env bash
PYTHONPATH="${repo_dir}/src:\${PYTHONPATH:-}" exec python3 -m git_steward.cli "\$@"
SH
chmod +x "${bin_dir}/git-steward"

echo "Installed ${bin_dir}/git-steward"
echo "Run: git-steward init --root ~/Code"
