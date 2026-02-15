#!/bin/bash

# ==============================================================================
# Symlink fieldmap files from a source BIDS directory to a destination.
#
# Usage:
#   symlink_fmaps.sh <src> <dst> <pattern> [--sub <subject>] [--ses <session>]
#
# Positional arguments:
#   src       Source BIDS directory containing the fieldmap files.
#   dst       Destination BIDS directory where symlinks will be created.
#   pattern   Filename pattern to match (e.g., TB1AFI).
#
# Optional arguments:
#   --sub <subject>   Process only this subject (e.g., sub-001 or just 001).
#   --ses <session>   Process only this session (e.g., ses-01 or just 01).
#                     Requires --sub to be set as well.
#
# Examples:
#   # All subjects and sessions:
#   symlink_fmaps.sh /src /dst TB1AFI
#
#   # Specific subject, all sessions:
#   symlink_fmaps.sh /src /dst TB1AFI --sub sub-001
#
#   # Specific subject and session:
#   symlink_fmaps.sh /src /dst TB1AFI --sub sub-001 --ses ses-01
# ==============================================================================

set -euo pipefail

# --- Parse positional arguments -----------------------------------------------
if [ $# -lt 3 ]; then
    echo "Error: At least 3 arguments required: <src> <dst> <pattern>"
    echo "Usage: $0 <src> <dst> <pattern> [--sub <subject>] [--ses <session>]"
    exit 1
fi

src="$1"
dst="$2"
pattern="$3" # e.g., TB1AFI
shift 3

# --- Parse optional named arguments -------------------------------------------
subject=""
session=""

while [ $# -gt 0 ]; do
    case "$1" in
        --sub)
            subject="$2"
            shift 2
            ;;
        --ses)
            session="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "Usage: $0 <src> <dst> <pattern> [--sub <subject>] [--ses <session>]"
            exit 1
            ;;
    esac
done

# Ensure the sub-/ses- prefix is present if a bare ID was given (e.g., 001 -> sub-001).
if [ -n "$subject" ] && [[ "$subject" != sub-* ]]; then
    subject="sub-${subject}"
fi
if [ -n "$session" ] && [[ "$session" != ses-* ]]; then
    session="ses-${session}"
fi

if [ -n "$session" ] && [ -z "$subject" ]; then
    echo "Error: --ses requires --sub to be specified as well."
    exit 1
fi

# --- Build the find path depending on the filters -----------------------------
if [ -n "$subject" ] && [ -n "$session" ]; then
    search_path="$src/$subject/$session/fmap"
elif [ -n "$subject" ]; then
    search_path="$src/$subject"
else
    search_path="$src"
fi

if [ ! -d "$search_path" ]; then
    echo "Error: Search path '$search_path' does not exist."
    exit 1
fi

# Find files in the source matching the pattern.
# Adjust the pattern if needed.
files=$(find "$search_path" -type f -path "*/ses-*/fmap/*$pattern*")
file_count=$(echo "$files" | grep -c . || true)
echo "Found $file_count file(s) matching pattern '$pattern' in '$search_path'"

if [ "$file_count" -eq 0 ]; then
    echo "Nothing to do."
    exit 0
fi

echo "$files" | while read -r srcfile; do

    # Extract subject (e.g., sub-001) and session (e.g., ses-01) from the file path.
    sub=$(echo "$srcfile" | grep -oP '(?<=/)sub-[^/]+(?=/)')
    ses=$(echo "$srcfile" | grep -oP '(?<=/)ses-[^/]+(?=/)')

    # Define the corresponding destination directory.
    tgt="$dst/$sub/$ses/fmap"

    # Only proceed if the subject/session directory already exists in the
    # destination (i.e., $dst/$sub/$ses). We deliberately omit 'mkdir -p' so
    # that the fmap subdirectory is only created when the parent is present.
    parent="$dst/$sub/$ses"
    if [ ! -d "$parent" ]; then
        echo "Subject/session folder $parent does not exist in destination. Skipping."
        continue
    fi

    if [ ! -d "$tgt" ]; then
        echo "Creating fmap folder $tgt"
        mkdir "$tgt"
    fi
    echo "Linking $srcfile -> $tgt/"
    ln -s "$srcfile" "$tgt/"
done