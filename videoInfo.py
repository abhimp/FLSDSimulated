import importlib
import os


class VideoInfo():
    def __init__(s, vi):
        s.fileSizes = vi.sizes
        s.segmentDuration = vi.segmentDuration
        s.bitrates = vi.bitrates
        s.duration = vi.duration
        s.minimumBufferTime = vi.minimumBufferTime
        s.segmentDurations = []
#         dur = 0
#         for x in s.fileSizes[0]:
#             if s.duration - dur > vi.segmentDuration:
#                 s.segmentDurations.append(vi.segmentDuration)
#             else:
#                 s.segmentDurations.append(s.duration - dur)
#             dur += vi.segmentDuration
#         print dur, s.duration



def loadVideoTime(fileName):
    assert os.path.isfile(fileName)
    dirname = os.path.dirname(fileName)
    basename = os.path.basename(fileName)
    module,ext = basename.rsplit(".", 1)
    path = importlib.sys.path
    if len(dirname) != 0:
        importlib.sys.path.append(dirname)
    videoInfo = importlib.import_module(module)

    if len(dirname) != 0:
        importlib.sys.path = path
    return VideoInfo(videoInfo)

def dummpyVideoInfo():
    import numpy as np
    class dummy():
        def __init__(s):
            s.bitrates = [200000, 400000, 600000, 800000, 1000000, 1500000, 2500000, 4000000]
            numseg = int(np.random.uniform(90,230))
            s.segmentDuration = 8
            s.minimumBufferTime = 16
            s.duration = s.segmentDuration * numseg
            s.sizes = []
            for br in s.bitrates:
                sz = []
                for x in range(numseg):
                    l = float(br) / 8 * s.segmentDuration * np.random.uniform(0.95, 1.05)
                    sz.append(int(l))
                s.sizes.append(sz)
    return VideoInfo(dummy())



if __name__ == "__main__":
    import sys
    x  = loadVideoTime(sys.argv[1])
    print(x.segmentDurations)
    print(x.bitrates)
    print(x.duration)
    print(x.minimumBufferTime)
    #print(x.sizes)
