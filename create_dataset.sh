#!/bin/bash

# create directory
mkdir ds
cd ds

# create files
for i in {1..2}
do
    dd if=/dev/zero of=xc_test_$1_$i.dat  bs=1M  count=1
done

cd ..
# upload to rucio
rucio upload --scope user.ivukotic --name xc_test_$1 --rse MWT2_UC_SCRATCHDISK ds

echo 'done'