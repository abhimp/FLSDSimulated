
class SegmentRequest():
    def __init__(self, qualityIndex, downloadStarted, downloadFinished, segmentDuration, segId, clen, downloader, extraData = None):
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

