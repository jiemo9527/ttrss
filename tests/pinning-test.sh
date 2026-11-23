#!/bin/sh
# 供应链固定检查：插件/主题必须固定到 40 位提交，Actions 必须固定到提交 SHA。
set -eu
cd "$(dirname "$0")/.."
fail=0

# Dockerfile 不允许再出现按分支下载的源码包或原始文件。
if grep -nE 'archive/(master|main|dist)\.tar\.gz|raw\.githubusercontent\.com/[^ ]+/(master|main)/' Dockerfile; then
  echo 'FAIL: Dockerfile 仍有按移动分支下载的来源'; fail=1
fi

# 每个 fetch-github-archive 调用都要带 40 位提交。
n=0
for sha in $(grep -E '^[[:space:]]*fetch-github-archive ' Dockerfile | awk '{print $3}'); do
  n=$((n + 1))
  printf '%s' "$sha" | grep -qE '^[0-9a-f]{40}$' || { echo "FAIL: 未固定的提交 $sha"; fail=1; }
done
[ "$n" -ge 15 ] || { echo "FAIL: 期望至少 15 个固定来源，实际 $n"; fail=1; }

# 外部 Actions 只能用完整提交 SHA 引用（本仓库内 ./ 可复用工作流除外）。
if grep -nE '^[[:space:]-]*uses:[[:space:]]*[^.][^@[:space:]]*@' .github/workflows/*.yml \
  | grep -vE '@[0-9a-f]{40}([[:space:]]|$)'; then
  echo 'FAIL: 有未固定 SHA 的 Action'; fail=1
fi

[ "$fail" = 0 ] && echo "pinning: PASS ($n archives)"
exit "$fail"
