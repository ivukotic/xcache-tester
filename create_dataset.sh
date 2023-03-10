#!/bin/bash

# create directory
mkdir ds
cd ds

# create files
for i in {1..288}
do
    dd if=/dev/zero of=xc_test_{$1}_{$i}.dat  bs=1M  count=1
done

# upload to rucio
rucio upload --scope tests --name xc_test_{$1} --rse MWT2_UC_SCRATCHDISK *

echo 'done'