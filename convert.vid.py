### current bpython session - make changes and save to reevaluate session.
### lines beginning with ### will be ignored.
### To return to bpython without reevaluating make no changes to this file
### or save an empty file.
import util.videoInfo as v
import sys
### <util.videoInfo.PenseivVideoInfo object at 0x7f38c0d18fd0>
x = v.loadVideoTime(sys.argv[1])
len(x.bitrates)
### 6
x.duration
### 2605.8
x.bitrates
### [400000, 600000, 1000000, 1500000, 2500000, 4000000]
with open(sys.argv[2], "w") as fp:
    print(x.segmentDuration*1000000, file=fp)
    print(*x.bitrates, file=fp)
    for y in x.fileSizes:
        print(*y, file=fp)
