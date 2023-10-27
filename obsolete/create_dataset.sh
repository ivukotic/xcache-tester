#!/bin/bash

# single file
rucio upload --scope user.ivukotic --rse MWT2_UC_LOCALGROUPDISK --expiration-date '2025-02-01-00:00:00' xcache.test.dat
rucio list-file-replicas user.ivukotic:xcache.test.dat
root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat



# create directory
mkdir ds
cd ds

dat=$(date +'%Y-%m-%d')
echo $dat

ds=user.ivukotic:user.ivukotic.xcache_$dat
echo $ds

# create rucio dataset
rucio add-dataset --lifetime 86400 $ds

# create files
for i in {1..288}
do
    fn=xcache_${dat}_${i}.dat
    echo "creating file: $fn"
    dd status=none if=/dev/zero of=$fn  bs=1M  count=1
    echo "uploading file: $fn"
    rucio upload --scope user.ivukotic --rse MWT2_UC_SCRATCHDISK $fn
    echo "attaching file: user.ivukotic:$fn to dataset $ds"
    rucio attach $ds user.ivukotic:$fn
done
rucio list-file-replicas $ds

echo 'done'


rucio upload --scope user.ivukotic --rse MWT2_UC_LOCALGROUPDISK --expiration-date '2025-02-01-00:00:00' xcache.test.dat
rucio list-file-replicas user.ivukotic:xcache.test.dat
root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat