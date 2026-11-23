#!/bin/sh
# 下载 GitHub 仓库指定提交的源码包并解压到目标目录。
# 用法：fetch-github-archive <owner/repo> <40 位提交> <目标目录> [仓库内子目录]
set -eu
repo=$1 sha=$2 dest=$3 sub=${4:-}
case "$sha" in
  *[!0-9a-f]*|'') echo "invalid commit for $repo: $sha" >&2; exit 1 ;;
esac
[ ${#sha} -eq 40 ] || { echo "commit for $repo must be 40 hex chars" >&2; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 "https://github.com/$repo/archive/$sha.tar.gz" -o "$tmp/src.tar.gz"
tar xzf "$tmp/src.tar.gz" -C "$tmp"
top="$tmp/${repo#*/}-$sha"
src="$top${sub:+/$sub}"
[ -d "$src" ] || { echo "missing path in $repo@$sha: ${sub:-/}" >&2; exit 1; }
mkdir -p "$dest"
cp -R "$src"/. "$dest"/
