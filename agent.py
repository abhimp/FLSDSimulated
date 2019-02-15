import random
import math
import numpy as np
from group import Group, GroupManager

PLAYBACK_DELAY_THRESHOLD = 4

class SimpAbr():
    def __init__(self, *kw, **kws):
        pass
    def getNextDownloadTime(self, *kw, **kws):
        return 3, 2

class Agent():
    __count = 0
    def __init__(self, videoInfo, env, abrClass = None):
        self._id = self.__count
        self.__count += 1
        self._vEnv = env
        self._vVideoInfo = videoInfo
        self._vCurrentBitrateIndex = 0
        self._vNextSegmentIndex = 0
        self._vPlaybacktime = 0.0
        self._vBufferUpto = 0
        self._vLastEventTime = 0
        self._vTotalStallTime = 0
        self._vStallsAt = []
        self._vStartUpDelay = 0.0
        self._vQualitiesPlayed = []
        self._vStartedAt = -1
        self._vGlobalStartedAt = -1
        self._vCanSkip = False #in case of live playback can be skipped
        self._vIsStarted = 0
        self._vMaxPlayerBufferLen = 50
        self._vTimeouts = []
        self._vRequests = [] #7-tuple throughput, timetaken, bytes/clen, startingTime, segIndex, segDur, bitrate
        abr = None if not abrClass else abrClass(videoInfo, self)
        self._vSetQuality = abr.getNextDownloadTime if abr else self._rWhenToDownload
        self._vStartingPlaybackTime = 0
        self._vStartingSegId = 0
        self._vTotalUploaded = 0
        self._vTotalDownloaded = 0
        self._vFinished = False
        self._vPendingRequests = set()
        self._vDownloadPending = False
        self._vDead = False

        self._vFirstSegmentDlTime = 0
        self._vSegmentSkiped = 0
        self._vStartUpCallback = []


    @property
    def bufferUpto(self):
        return self._vBufferUpto

    @property
    def nextSegmentIndex(self):
        return self._vNextSegmentIndex

    @property
    def currentBitrateIndex(self):
        return self._vCurrentBitrateIndex

    @property
    def maxPlayerBufferLen(self):
        return self._vMaxPlayerBufferLen

    def addStartupCB(self, func):
        self._vStartUpCallback.append(func)

#=============================================
    def _rNextQuality(self, ql, timetaken, segDur, segIndex, clen):
        if self._vDead: return

        assert segIndex == self._vNextSegmentIndex
        totaldata = clen
        throughput = float(totaldata)/timetaken*8
        startingTime = self._vEnv.getNow() - timetaken
        self._vRequests.append((throughput, timetaken, clen, \
                startingTime, segIndex, segDur, ql))

        _, times, clens = list(zip(*self._vRequests))[:3]
        avg = sum(clens)*8/sum(times)
        level = 0
        for ql, q in enumerate(self._vVideoInfo.bitrates):
            if q > avg:
                break
            level = ql
        self._vCurrentBitrateIndex = level

#=============================================
    def _rWhenToDownload(self, *kw):
        if self._vDead: return

        buflen = self._vBufferUpto - self._vPlaybacktime
        if (self._vMaxPlayerBufferLen - self._vVideoInfo.segmentDuration) > buflen:
            return 0, self._vCurrentBitrateIndex
        sleepTime = buflen + self._vVideoInfo.segmentDuration - self._vMaxPlayerBufferLen
        return sleepTime, self._vCurrentBitrateIndex

#=============================================
    def _rAddToBufferInternal(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return

        self._rNextQuality(ql, timetaken, segDur, segIndex, clen)

        now = self._vEnv.getNow()
        segPlaybackStartTime = segIndex * self._vVideoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + segDur

        timeSpent = now - self._vLastEventTime
        self._vLastEventTime = now
        stallTime = 0
        playbackTime = self._vPlaybacktime + timeSpent
        if playbackTime > self._vBufferUpto:
            stallTime = playbackTime - self._vBufferUpto
            playbackTime = self._vBufferUpto

        if not self._vIsStarted:
            expectedPlaybackTime = 0
            startUpDelay = now - self._vStartedAt
            stallTime = 0
            playbackTime = segPlaybackStartTime
            bufferUpto = segPlaybackEndTime
            if self._vGlobalStartedAt != self._vStartedAt:
                expectedPlaybackTime = now - self._vGlobalStartedAt

            if  self._vCanSkip and expectedPlaybackTime + PLAYBACK_DELAY_THRESHOLD > segPlaybackEndTime:
                #need to skip this segment
                self._vNextSegmentIndex += 1
                self._rDownloadNextData(0)
                self._vSegmentSkiped += 1
                return

            if expectedPlaybackTime < segPlaybackStartTime:
                after = segPlaybackStartTime - expectedPlaybackTime
                self._vEnv.runAfter(after, self._rAddToBufferInternal, ql, timetaken, segDur, segIndex, clen, simIds, external)
                return

            if segPlaybackStartTime <= expectedPlaybackTime <= segPlaybackEndTime:
                playbackTime = expectedPlaybackTime

            self._vIsStarted = True
            self._vStartingPlaybackTime = playbackTime
            self._vStartingSegId = segIndex
            self._vFirstSegmentDlTime = timetaken
            self._vStartUpDelay = startUpDelay
            for cb in self._vStartUpCallback:
                cb(self)


        if stallTime > 0:
            assert playbackTime > 0
            self._vStallsAt.append((playbackTime, stallTime, ql))
            self._vTotalStallTime += stallTime
        self._vBufferUpto = segPlaybackEndTime
        self._vPlaybacktime = playbackTime

        buflen = self._vBufferUpto - self._vPlaybacktime
        self._vQualitiesPlayed.append(ql)
        self._vNextSegmentIndex += 1
        if self._vNextSegmentIndex == len(self._vVideoInfo.fileSizes[0]):
            self._vEnv.finishedAfter(buflen)
            return
        self._rDownloadNextData(buflen)

#=============================================
    def _rDownloadNextData(self, buflen):
        if self._vDead: return

        now = self._vEnv.getNow()
        nextSegId = self._vNextSegmentIndex
        nextQuality = self._vCurrentBitrateIndex
        sleepTime, nextQuality = self._vSetQuality(self._vMaxPlayerBufferLen, \
            self._vBufferUpto, self._vPlaybacktime, now, self._vNextSegmentIndex)
        self._vCurrentBitrateIndex = nextQuality
        self._vEnv._rDownloadNextData(nextSegId, nextQuality, sleepTime)

#=============================================
    def _rTimeoutEvent(self, simIds, lastBandwidthPtr, sleepTime):
        if self._vDead: return

        if simIds != None and REQUESTION_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[REQUESTION_SIMID_KEY])

        self._vLastBandwidthPtr = lastBandwidthPtr
        self._vTimeouts.append((self._vNextSegmentIndex, self._vCurrentBitrateIndex))
        self._vCurrentBitrateIndex = 0
        self._rFetchSegment(self._vNextSegmentIndex, self._vCurrentBitrateIndex, sleepTime)

        

#=============================================
    def _rGetTimeOutTime(self):
        if self._vDead: return

        timeout = self._vVideoInfo.segmentDuration
        bufLeft = self._vBufferUpto - self._vPlaybacktime
        if bufLeft - timeout > timeout:
            timeout = bufLeft - timeout
        return timeout

#=============================================
    def _rIsAvailable(self, segId):
        if self._vDead: return -1

        assert segId < self._vVideoInfo.segmentCount
        now = self._vEnv.getNow()
        ePlaybackTime = now - self._vGlobalStartedAt
        segStartTime = (segId+1)*self._vVideoInfo.segmentDuration
        return segStartTime - ePlaybackTime + self._vVideoInfo.globalDelayPlayback

#=============================================
    def _rCalculateQoE(self):
        if self._vDead: return

        lmbda = 1
        mu = 4.3
        mu_s = 1 
        rmin = self._vVideoInfo.bitrates[0]
        bitratePlayed = [self._vVideoInfo.bitrates[x] for x in self._vQualitiesPlayed]
        bitratePlayed = [math.log(self._vVideoInfo.bitrates[x]/rmin) for x in self._vQualitiesPlayed]
        bitratePlayed = self._vQualitiesPlayed
        avgQuality = float(sum(bitratePlayed))/len(bitratePlayed)
        avgQualityVariation = [abs(bt - bitratePlayed[x - 1]) for x,bt in enumerate(bitratePlayed) if x > 0]
        avgQualityVariation = 0 if len(avgQualityVariation) == 0 else sum(avgQualityVariation)/float(len(avgQualityVariation))

        QoE = avgQuality - lmbda * avgQualityVariation - mu * self._vTotalStallTime - mu_s * self._vStartUpDelay
        return QoE

#=============================================
    def _rFinish(self):
        if self._vDead: return

        self._vFinished = True
        print("Simulation finished at:", self._vEnv.getNow(), "totalStallTime:", self._vTotalStallTime, "startUpDelay:", self._vStartUpDelay, "firstSegDlTime:", self._vFirstSegmentDlTime, "segSkipped:", self._vSegmentSkiped)
        print("QoE:", self._rCalculateQoE())
#         print("stallTime:", self._vStallsAt)
#         print("Quality played:", self._vQualitiesPlayed)
#         print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
#                 "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)

#=============================================
    def start(self, startedAt = -1):
        segId = self._vNextSegmentIndex
        now = self._vEnv.getNow()
        self._vStartedAt = self._vGlobalStartedAt = now
        if startedAt >= 0:
            playbackTime = now - startedAt
            self._vNextSegmentIndex = int(playbackTime*1./self._vVideoInfo.segmentDuration)
            while (self._vNextSegmentIndex + 1) * self._vVideoInfo.segmentDuration < playbackTime + PLAYBACK_DELAY_THRESHOLD:
                self._vNextSegmentIndex += 1
            self._vNextSegmentIndex += 1
            self._vCanSkip = True
            self._vGlobalStartedAt = startedAt
        self._vLastEventTime = now
        self._rDownloadNextData(0)

