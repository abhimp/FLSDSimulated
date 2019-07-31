
class SegmentUsage():
    __instance = None
    @staticmethod
    def getInstance(*kw, **kws):
        if SegmentUsage.__instance == None:
            SegmentUsage(*kw, **kws)
        return SegmentUsage.__instance

    @staticmethod
    def clear():
        SegmentUsage.__instance = None

    def __init__(self, *kw, **kws):
        assert SegmentUsage.__instance == None
        SegmentUsage.__instance = self
        self._vDownloadCnt = 0
        self._vDownloadBytes = 0

        self._vPlayedCnt = 0
        self._vPlayedBytes = 0

        self._vPlaybackCnt = {}

    def getPlaybackFreq(self):
        return [x[0] for x in self._vPlaybackCnt.values()]

    def getWastage(self):
        return sum([x[1] for x in self._vPlaybackCnt.values() if x[0] == 0])

    @staticmethod
    def downloaded(req):
        assert req.isComplete
        self = SegmentUsage.getInstance()
        self._vDownloadCnt += 1
        self._vDownloadBytes += req.clen
        req._downloaded = True
        self._vPlaybackCnt[req._id] = [0,req.clen]

    @staticmethod
    def played(req):
        assert req.isComplete
        self = SegmentUsage.getInstance()
        if not req._used:
            self._vPlayedCnt += 1
            self._vPlayedBytes += req.clen
        self._vPlaybackCnt[req._id][0] += 1
        req._used = True

class SegmentRequest():
    __counter = 0
    def __init__(self, qualityIndex, downloadStarted, downloadFinished, segmentDuration, segId, clen, downloader, extraData = None):
        self._id = SegmentRequest.__counter
        SegmentRequest.__counter += 1
        self._qualityIndex = qualityIndex
        self._downloadStarted = downloadStarted
        self._downloadFinished = downloadFinished
        self._segmentDuration = segmentDuration
        self._segId = segId
        self._clen = clen
        self._downloader = downloader
        self._extraData = extraData
        self._syncSeg = False
        self._completSeg = True

        self._downloaded = False
        self._used = False

    def markDownloaded(self):
#         if self._downloaded: return
        assert not self._downloaded
        SegmentUsage.downloaded(self)

    def markUsed(self):
        assert self._downloaded
        SegmentUsage.played(self)


    def getCopy(self, complete=True):
        assert self._completSeg or not complete, "Trying to get complete copy from a incomplete object" # it does not make sense to get a complete copy from incomplete object
        obj = SegmentRequest(
                qualityIndex = self._qualityIndex,
                downloadStarted = self._downloadStarted,
                downloadFinished = self._downloadFinished,
                segmentDuration = self._segmentDuration,
                segId = self._segId,
                clen = self._clen,
                downloader = self._downloader,
                extraData = self._extraData,
            )
        obj.syncSeg = self.syncSeg
        obj._completSeg = complete
        return obj

    def getIncompleteCopy(self):
        return self.getCopy(False)

    @property
    def syncSeg(self):
        return self._syncSeg

    @syncSeg.setter
    def syncSeg(self, p):
        self._syncSeg = p

    @property
    def extraData(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._extraData

    @property
    def qualityIndex(self):
#         assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._qualityIndex

    @property
    def downloadStarted(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._downloadStarted

    @property
    def downloadFinished(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._downloadFinished

    @property
    def segmentDuration(self):
#         assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._segmentDuration

    @property
    def segId(self):
        return self._segId

    @property
    def clen(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self._clen

    @property
    def downloader(self):
        return self._downloader

    @property
    def timetaken(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self.downloadFinished - self.downloadStarted

    @property
    def throughput(self):
        assert self.isComplete, "Incomplete segment. Attribute is not available."
        return self.clen*8.0/self.timetaken

    @property
    def isComplete(self):
        return self._completSeg

