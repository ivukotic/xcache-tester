#!/bin/bash

# create directory
mkdir ds
cd ds

# create files
for i in {1..288}
do
    dd if=/dev/zero of=output.dat  bs=1M  count=1
done

# upload to rucio
