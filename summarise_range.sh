#!/bin/bash

# Script to run hansard summarise commands for a date range
# Usage: ./summarise_range.sh START_DATE END_DATE
# Date format: YYYY-MM-DD

set -e

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 DATE [END_DATE]"
    echo "Example (single date): $0 2025-01-15"
    echo "Example (date range):  $0 2025-01-01 2025-01-31"
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

current_date="$START_DATE"

while [[ ! "$current_date" > "$END_DATE" ]]; do
    echo ""
    echo "Processing date: $current_date"
    echo "--------------------------------"
    
    echo "Running Commons summarisation..."
    uv run digest hansard summarise "$current_date" --source commons --publish
    
    echo "Running Lords summarisation..."
    uv run digest hansard summarise "$current_date" --source lords --publish
    
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
