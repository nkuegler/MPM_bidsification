#!/bin/bash

echo "Comparing MPM bidsmaps..."
if diff supplementary/bidsmaps/example_bidsmap_MPM.yaml /data/pt_02262/data/TH_bids/bids/code/bidsme/bidsmap.yaml > /dev/null; then
    echo "MPM bidsmaps are the same"
else
    echo "MPM bidsmaps are different"
fi

echo ""
echo "Comparing LORAKS bidsmaps..."
if diff supplementary/bidsmaps/example_bidsmap_loraks.yaml /data/pt_02262/data/TH_bids/bids/derivatives/LORAKS/code/bidsme/bidsmap.yaml > /dev/null; then
    echo "LORAKS bidsmaps are the same"
else
    echo "LORAKS bidsmaps are different"
fi
echo ""