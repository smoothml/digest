#!/bin/bash

# Script to run hansard summarise commands for a date range
# Usage: ./summarise_range.sh [-f|--force] DATE [END_DATE]
# Date format: YYYY-MM-DD

set -e

usage() {
    cat <<EOF
Usage: $0 [-f|--force] DATE [END_DATE]

Examples:
  $0 2025-01-15
  $0 -f 2025-01-01 2025-01-31

The -f/--force flag removes any existing markdown posts for the given date(s)
before regenerating summaries.
EOF
}

FORCE=false
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -f|--force)
            FORCE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                POSITIONAL+=("$1")
                shift
            done
            break
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

if [ ${#POSITIONAL[@]} -gt 0 ]; then
    set -- "${POSITIONAL[@]}"
else
    set --
fi

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    usage
    exit 1
fi

START_DATE=$1
END_DATE=${2:-$1}  # Use START_DATE if END_DATE is not provided

# Function to validate date format (works on both macOS and Linux)
validate_date() {
    local date_str=$1
    # Check format with regex
    if ! [[ $date_str =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        return 1
    fi
    # Try to parse with date command (platform-specific)
    if date --version &>/dev/null; then
        # GNU date (Linux)
        date -d "$date_str" &>/dev/null
    else
        # BSD date (macOS)
        date -j -f "%Y-%m-%d" "$date_str" &>/dev/null
    fi
}

# Validate date format
if ! validate_date "$START_DATE"; then
    echo "Error: Invalid start date format. Use YYYY-MM-DD"
    exit 1
fi

if ! validate_date "$END_DATE"; then
    echo "Error: Invalid end date format. Use YYYY-MM-DD"
    exit 1
fi

# Check that start date is before or equal to end date
if [[ "$START_DATE" > "$END_DATE" ]]; then
    echo "Error: Start date must be before or equal to end date"
    exit 1
fi

echo "Processing dates from $START_DATE to $END_DATE"
echo "================================================"

get_day_component() {
    local date_str=$1
    local format=$2
    if date --version &>/dev/null; then
        date -d "$date_str" +"$format"
    else
        date -j -f "%Y-%m-%d" "$date_str" +"$format"
    fi
}

is_weekend() {
    local date_str=$1
    local day_of_week
    day_of_week=$(get_day_component "$date_str" "%u")
    if [[ "$day_of_week" -ge 6 ]]; then
        return 0
    fi
    return 1
}

get_weekday_name() {
    local date_str=$1
    get_day_component "$date_str" "%A"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_CONTENT_DIR="$SCRIPT_DIR/sites/hansard/content"
SUMMARY_FILES=()

find_existing_summary_files() {
    local source_dir=$1
    local date_str=$2
    SUMMARY_FILES=()

    if [ ! -d "$source_dir" ]; then
        return 1
    fi

    shopt -s nullglob
    local matches=(
        "$source_dir/$date_str"-*.md
        "$source_dir/$date_str".md
    )
    shopt -u nullglob

    for file in "${matches[@]}"; do
        if [ -f "$file" ]; then
            SUMMARY_FILES+=("$file")
        fi
    done

    if [ ${#SUMMARY_FILES[@]} -gt 0 ]; then
        return 0
    fi

    return 1
}

run_summarisation() {
    local date=$1
    local source=$2
    local label=$3
    local source_dir="$SITE_CONTENT_DIR/$source"

    if find_existing_summary_files "$source_dir" "$date"; then
        if [ "$FORCE" = true ]; then
            for file in "${SUMMARY_FILES[@]}"; do
                echo "Removing existing $label summary: $file"
                rm -f "$file"
            done
        else
            local first_file
            first_file=$(basename "${SUMMARY_FILES[0]}")
            echo "Skipping $label summarisation (already exists: $first_file)"
            return
        fi
    fi

    echo "Running $label summarisation..."
    uv run digest hansard summarise "$date" --source "$source" --publish
}

current_date="$START_DATE"

while [[ ! "$current_date" > "$END_DATE" ]]; do
    echo ""
    echo "Processing date: $current_date"
    echo "--------------------------------"

    if is_weekend "$current_date"; then
        weekday_name=$(get_weekday_name "$current_date")
        echo "Skipping $current_date ($weekday_name) - weekend"
    else
        run_summarisation "$current_date" "commons" "Commons"
        run_summarisation "$current_date" "lords" "Lords"
        run_summarisation "$current_date" "westminster_hall" "Westminster Hall"
    fi

    # Move to next date (platform-specific)
    if date --version &>/dev/null; then
        # GNU date (Linux)
        current_date=$(date -I -d "$current_date + 1 day")
    else
        # BSD date (macOS)
        current_date=$(date -j -v+1d -f "%Y-%m-%d" "$current_date" +%Y-%m-%d)
    fi
done

echo ""
echo "================================================"
echo "Completed processing all dates from $START_DATE to $END_DATE"
