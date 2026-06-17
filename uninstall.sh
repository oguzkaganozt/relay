#!/usr/bin/env bash
# uninstall.sh — remove everything install.sh sets up, minus the .deb.
#
# Usage:
#   ./uninstall.sh                    standard uninstall
#   KEEP_CONFIG=1 ./uninstall.sh      keep ~/.config/voxtype/config.toml
#   KEEP_MODEL=1 ./uninstall.sh       keep downloaded model weights (default)
#   FORCE_MODEL_REMOVE=1 ./uninstall.sh  also remove ~/.local/share/voxtype/
#   PURGE_DEB=1 ./uninstall.sh        also run `sudo apt remove voxtype`
#
# This delegates to install.sh --uninstall for the heavy lifting.

set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
exec "$SCRIPT_DIR/install.sh" --uninstall "$@"