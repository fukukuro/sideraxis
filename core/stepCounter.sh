#!/bin/bash

# srcディレクトリを対象に固定
TARGET_DIR="src"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' not found."
    exit 1
fi

echo "Counting lines in: $TARGET_DIR"
echo "-----------------------------------"

# 1. findでsrc以下の.pyを検索
# 2. grep -v '^$' で空行を除去
# 3. grep -v '^[[:space:]]*#' でコメント行（インデント対応）を除去
# 4. wc -l で合計行数をカウント
find "$TARGET_DIR" -name "*.py" -print0 | xargs -0 grep -v '^[[:space:]]*$' | grep -v '^[[:space:]]*#' | wc -l