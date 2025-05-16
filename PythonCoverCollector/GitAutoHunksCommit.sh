#!/bin/bash

read -p "Enter path to Git repo: " repo_path
cd "$repo_path" || { echo "Invalid path"; exit 1; }
read -p "Enter the main idea of commit" INFO_INFO
count=1
while git diff --quiet || true; do
  printf "y\nq\n" | git add -p
  if git diff --cached --quiet; then
    break
  fi
  git commit -m "$INFO_INFO Stage hunk #$count"
  count=$((count + 1))
done
