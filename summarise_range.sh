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

# Validate date format
if ! date -d "$START_DATE" &>/dev/null; then
    echo "Error: Invalid start date format. Use YYYY-MM-DD"
    exit 1
fi

if ! date -d "$END_DATE" &>/dev/null; then
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
    
    # Move to next date
    current_date=$(date -I -d "$current_date + 1 day")
done

echo ""
echo "================================================"
echo "Completed processing all dates from $START_DATE to $END_DATE"
