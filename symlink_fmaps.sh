#!/bin/bash

# Set your source and destination directories:
src="$1"
dst="$2"
pattern="$3" # e.g., TB1AFI

# Find files in the source matching the pattern.
# Adjust the pattern if needed (note: the '!' is taken literally here).
files=$(find "$src" -type f -path "*/ses-*/fmap/*$pattern*")
file_count=$(echo "$files" | grep -c .)
echo "Found $file_count file(s) matching pattern '$pattern'"

echo "$files" | while read -r srcfile; do

    # Extract subject (e.g., sub-001) and session (e.g., ses-01) from the file path.
    sub=$(echo "$srcfile" | grep -oP '(?<=/)sub-[^/]+(?=/)')
    ses=$(echo "$srcfile" | grep -oP '(?<=/)ses-[^/]+(?=/)')

    # Define the corresponding destination directory.
    tgt="$dst/$sub/$ses/fmap"

    # Check if the destination fmap directory exists.
    if [ -d "$tgt" ]; then
    echo "Linking $srcfile to $tgt"
    ln -s "$srcfile" "$tgt/"
    else
    echo "Destination folder $tgt does not exist. Skipping."
    fi
done