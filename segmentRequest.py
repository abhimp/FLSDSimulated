
class SegmentRequest():
    def __init__(self, qualityIndex, downloadStarted, downloadFinished, segmentDuration, segId, clen, downloader):
        self._qualityIndex = qualityIndex
        self._downloadStarted = downloadStarted
        self._downloadFinished = downloadFinished
        self._segmentDuration = segmentDuration
        self._segId = segId
        self._clen = clen
        self._downloader = downloader

    @property
    def qualityIndex(self):
        return self._qualityIndex

    @property
    def downloadStarted(self):
        return self._downloadStarted

    @property
    def downloadFinished(self):
        return self._downloadFinished

    @property
    def segmentDuration(self):
        return self._segmentDuration

    @property
    def segId(self):
        return self._segId

    @property
    def clen(self):
        return self._clen

    @property
    def downloader(self):
        return self._downloader

    @property
    def timetaken(self):
        return self.downloadFinished - self.downloadStarted

    @property
    def throughput(self):
        return self.clen*8.0/self.timetaken

