from simenv.FLiDASH import FLiDASH
from util.segmentRequest import SegmentRequest
# from test_shared_dl import SharedDownloader


class FLiDASHShared(FLiDASH):
    def __init__(self, *kw, sharedLink=None, **kws):
        super().__init__(*kw, **kws)
        self._vSharedLink = sharedLink
        self._vCurJobId = -1
        self._vCurDlState = None

#         req = SegmentRequest(ql, startedAt, now, dur, segId, clen, self, extraData)
#=============================================
    def _rFetchNextSeg(self, nextSegId, nextQuality, extraData=None):
        if self._vSharedLink is None:
            return super()._rFetchNextSeg(nextSegId, nextQuality, extraData)

        if self._vDead: return

        assert not self._vWorking
        self._vWorking = True
        now = self.now

        sleepTime = now - self._vLastDownloadedAt
        idleTime = round(sleepTime, 3)
        self._vIdleTimes += [(now, 0)]
        if idleTime > 0:
            self._vTotalIdleTime += idleTime
            self._vWorkingTimes += [(now, 0, nextSegId)]

        dur = self._vVideoInfo.getSegDuration(nextSegId)
        clen = self._vVideoInfo.fileSizes[nextQuality][nextSegId]
        curDlId = self._vNextDownloadId
        self._vNextDownloadId += 1

        dlState = []
        state = [nextSegId, nextQuality, extraData, clen, curDlId, dlState, now, dur]

        self._vCurDlState = state
        self._vCurJobId = self._vSharedLink.addJob(self._rOnUpdate, self._rOnFinish, state, clen, 128*1024)
        self._vWorkingStatus = (now, None, nextSegId, clen, dlState, None, curDlId)

#=============================================
    def _rOnUpdate(self, state, downloaded, now, *_):
        nextSegId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = state

        timeSpent = round(now - startedAt, 3)
        dlState += [(timeSpent, downloaded)]

#=============================================
    def _rOnFinish(self, state, downloaded, now, *_):
        if not self._vWorking:# or self._vWorkingStatus[6] != dlId:
            return
        assert self._vWorking
        segId, ql, extraData, clen, curDlId, dlState, startedAt, dur = state
        self._vWorking = False
        self._vWorkingStatus = None

        self._vIdleTimes += [(now, 25)]
        time = now - startedAt
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(ql, startedAt, now, dur, segId, clen, self, extraData)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)
        req.markDownloaded()
        self._rAddToBuffer(req, None)


# #=============================================
# # Not that important
#     def _rFetchNextSegReturn(self, ql, startedAt, dur, segId, clen, simIds, extraData, dlId):
#         if self._vSharedLink is None:
#             return super()._rFetchNextSegReturn(ql, startedAt, dur, segId, clen, simIds, extraData, dlId)

#=============================================
    def _rStopDownload(self):
        if self._vSharedLink is None:
            return super()._rStopDownload()
        assert self._vWorking
        self._vSharedLink.cancelJob(self._vCurJobId)

        now = self.now
#         startedAt, dur, segId, clen, downloadData, simIds, dlId = self._vWorkingStatus
        segId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = self._vCurDlState
        time, downloaded, _ = self._rDownloadStatus()
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(0, startedAt, now, dur, segId, downloaded, self)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)

#=============================================
    def _rDownloadStatus(self):
        if self._vSharedLink is None:
            return super()._rDownloadStatus()

        if not self._vWorking:
            return (0,0,0)
        assert self._vWorking
        nextSegId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = self._vCurDlState
        if len(dlState) == 0:
            return 0, 0, clen
        ts, dl = dlState[-1]
        return ts, dl, clen
