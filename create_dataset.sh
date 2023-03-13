#!/bin/bash

# create directory
mkdir ds
cd ds

dat=$1
ds=user.ivukotic:user.ivukotic.xcache_$dat

# create rucio dataset
rucio add-dataset --lifetime 86400 $ds

# create files
for i in {1..288}
do
    fn=xcache_$1_$i.dat
    echo 'creating file: $fn'
    dd if=/dev/zero of=$fn  bs=1M  count=1
    echo 'uploading file: $fn'
    rucio upload --scope user.ivukotic --rse MWT2_UC_SCRATCHDISK $fn
    echo 'attaching file: user.ivukotic:$fn to dataset $ds'
    rucio attach $ds user.ivukotic:$fn
done
rucio list-file-replicas $ds

echo 'done'