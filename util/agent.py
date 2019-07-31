import random
from util.myprint import myprint
import math
import numpy as np
from util.group import Group, GroupManager
from util.calculateMetric import measureQoE
from util.misc import lineno, getPosition

PLAYBACK_DELAY_THRESHOLD = 4
M_IN_K = 1000

class SimpAbr():
    def __init__(self, *kw, **kws):
        pass
    def getNextDownloadTime(self, *kw, **kws):
        return 3, 2

class Agent():
    __count = 0
    def __init__(self, videoInfo, env, abrClass = None, logpath=None, resultpath=None):
        self._id = self.__count
        self.__count += 1
        self._vLogPath = logpath
        self._vResultPath = resultpath
        self._vEnv = env
        self._vVideoInfo = videoInfo
        self._vLastBitrateIndex = 0
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
        self._vRequests = [] # the rquest object
        self._vAbr = abrClass(videoInfo, self, log_file_path=logpath)
        self._vStartingPlaybackTime = 0
        self._vStartingSegId = 0
        self._vTotalUploaded = 0
        self._vTotalDownloaded = 0
        self._vFinished = False
        self._vPendingRequests = set()
        self._vDownloadPending = False
        self._vDead = False
        self._vBufferLenOverTime = [(0,0)]
        self._vQualitiesPlayedOverTime = []

        self._vFirstSegmentDlTime = 0
        self._vSegmentSkiped = 0
        self._vStartUpCallback = []
        self._vTimeSlipage = [(0,0,0)]
        self._vSyncSegment = -1
        self._vTotalPlayableTime = 0

        self._vSegIdPlaybackTime = {}


        self._vBufManBuffer = {} #segment with multiple options solid segments or not
        self._vBufManActionPending = False
        self._vBufManActionId = -1
        self._vBufManNextSegId = 0
        self._vBufManRebuffering = True #Its better this way
        self._vBufManRebufferingFrom = -1
        self._vBufManRemoteBufThresh = 2 # # of segments
        self._vBufManPlayinSegId = -1
        self._vBufManPlayingSegStartedAt = -1
        self._vBufManRemoteFetchingQueue = {}
        self._vBufManBufferOccupacy = 0



    @property
    def bufferUpto(self):
        return self._vBufferUpto

    @bufferUpto.setter
    def bufferUpto(self, value):
        assert self._vMaxPlayerBufferLen >= round(value - self._vPlaybacktime, 3)
        self._vBufferUpto = value

    @property
    def nextSegmentIndex(self):
        return self._vNextSegmentIndex

    @property
    def currentBitrateIndex(self):
        return self._vCurrentBitrateIndex

    @property
    def maxPlayerBufferLen(self):
        return self._vMaxPlayerBufferLen

    @property
    def playbackTime(self):
        now = self._vEnv.getNow()
        assert self._vBufManPlayingSegStartedAt >= 0
        timeSpent = min(now - self._vBufManPlayingSegStartedAt, self._vBufManBuffer[self._vBufManPlayinSegId]["seg"].segmentDuration)

        playbackTime = self._vPlaybacktime + timeSpent
        return round(playbackTime, 3)

    @property
    def bufferLeft(self):
        now = self._vEnv.getNow()
        if not self._vIsStarted:
            return 0
#         assert self._vBufManPlayingSegStartedAt >= 0
        timeSpent = min(now - self._vBufManPlayingSegStartedAt, self._vBufManBuffer[self._vBufManPlayinSegId]["seg"].segmentDuration)
        bufOcc = self._vBufManBuffer[self._vBufManPlayinSegId]["seg"].segmentDuration - timeSpent
        for segId in range(self._vBufManNextSegId, self._vNextSegmentIndex):
            if self._vBufManBuffer[segId]['hvComplete']:
                bufOcc += self._vBufManBuffer[segId]["seg"].segmentDuration

        return bufOcc

#         bufLeft = self._vMaxPlayerBufferLen - bufOcc
#         assert bufLeft >= 0
#         return bufLeft


    @property
    def stallTime(self):
        now = self._vEnv.getNow()
        curStall = 0 if self._vBufManRebufferingFrom < 0 else now - self._vBufManRebufferingFrom
        return self._vTotalStallTime + curStall

#=============================================
    @property
    def avgStallTime(self):
        bitratePlayed = self._vQualitiesPlayed
        return self.totalStallTime / len(bitratePlayed)

#=============================================
    @property
    def avgQualityIndex(self):
        if len(self._vQualitiesPlayed) == 0: return 0

        bitratePlayed = self._vQualitiesPlayed
        return float(sum(bitratePlayed))/len(bitratePlayed)

#=============================================
    @property
    def bitratePlayed(self):
        return [self._vVideoInfo.bitrates[x] for x in self._vQualitiesPlayed]

#=============================================
    @property
    def avgQualityIndexVariation(self):
        if len(self._vQualitiesPlayed) == 0: return 0
        bitratePlayed = self._vQualitiesPlayed
        avgQualityVariation = [abs(bt - bitratePlayed[x - 1]) for x,bt in enumerate(bitratePlayed) if x > 0]
        avgQualityVariation = 0 if len(avgQualityVariation) == 0 else sum(avgQualityVariation)/float(len(avgQualityVariation))

        return avgQualityVariation

#=============================================
    @property
    def avgBitrate(self):
        if len(self._vQualitiesPlayed) == 0: return 0

        bitratePlayed = self._vQualitiesPlayed
        bitratePlayed = [self._vVideoInfo.bitrates[x] for x in self._vQualitiesPlayed]
        return float(sum(bitratePlayed))/len(bitratePlayed)

#=============================================
    @property
    def avgBitrateVariation(self):
        if len(self._vQualitiesPlayed) == 0: return 0

        bitratePlayed = self._vQualitiesPlayed
        bitratePlayed = [self._vVideoInfo.bitrates[x] for x in self._vQualitiesPlayed]
        avgQualityVariation = [abs(bt - bitratePlayed[x - 1]) for x,bt in enumerate(bitratePlayed) if x > 0]
        avgQualityVariation = 0 if len(avgQualityVariation) == 0 else sum(avgQualityVariation)/float(len(avgQualityVariation))

        return avgQualityVariation

#=============================================
    @property
    def startUpDelay(self):
        return self._vStartUpDelay

#=============================================
    @property
    def totalStallTime(self):
        return self._vTotalStallTime

#=============================================
    @property
    def QoE(self):
        numSegs = len(self.bitratePlayed)
#         avgQualityVariation = [abs(bt - bitratePlayed[x - 1]) for x,bt in enumerate(bitratePlayed) if x > 0]
        return (self.avgBitrate/1000000 - 4.3*self.totalStallTime/numSegs - self.avgBitrateVariation/1000000)

#=============================================
    def addStartupCB(self, func):
        self._vStartUpCallback.append(func)

#=============================================
    def bufferAvailableIn(self):
        return max(0, self._vVideoInfo.segmentDuration - self._vMaxPlayerBufferLen + round(self.bufferLeft, 3))

#=============================================
    def _rValidateReq(self, req):
        if self._vDead: return

        assert req.segId == self._vNextSegmentIndex or (req.syncSeg and req.segId > self._vNextSegmentIndex)
        self._vRequests.append(req)

#=============================================
    def _rStoreSegmentPlaybackTime(self, req):
        self._vTotalPlayableTime += req.segmentDuration
        segId = req
        curPlaybackTime = self._vPlaybacktime
        segPlaybackStartTime = req.segId*self._vVideoInfo.segmentDuration
        waitTime = segPlaybackStartTime - curPlaybackTime
        assert waitTime >= 0

        self._vSegIdPlaybackTime[req.segId] = (self._vEnv.now + waitTime, req)

#=============================================
    def _rAddToBufferToBufferManager(self, req, simIds = None):
        if self._vDead: return
        #validate
        assert req.segId == self._vNextSegmentIndex or (req.syncSeg and req.segId > self._vNextSegmentIndex)

        #setupEnv
        now = self._vEnv.now

        if not self._vIsStarted:
            self._rHandleStartup(req)
            self._rDownloadNextData()
            return #end this function here are startup is very special and we are handling it differently.

        segId = req.segId

        segBufInfo = self._vBufManBuffer.get(segId, {"hvComplete": False})
        assert not segBufInfo["hvComplete"], f"Already have complete segment"
        segBufInfo = {"hvComplete":req.isComplete, "seg": req}
        self._vBufManBuffer[segId] = segBufInfo


        #TODO update parameters like bufferLeft bufferUpto
        segPlaybackStartTime = segId * self._vVideoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + req.segmentDuration
        self._vBufferUpto = segPlaybackEndTime
        self._vNextSegmentIndex = req.segId + 1

        if not req.isComplete:
            #TODO fetch it from remote and inform
            self._rBufManIinitRemoteFetch(req)

        if req.syncSeg:
            if self._vBufManActionPending:
                self._vEnv._vSimulator.cancelTask(self._vBufManActionId)
                self._vBufManActionId == -1

            self._vPlaybacktime = segPlaybackStartTime
            self._vBufManNextSegId = req.segId
            self._vBufManBufferOccupacy = 0
            self._rBufferManager()
        else:
            if not self._vBufManActionPending:
                self._rBufferManager()

        if self._vNextSegmentIndex >= self._vVideoInfo.segmentCount:
            return
        self._rDownloadNextData()

#=============================================
    def _rBufManAddCompleteReq(self, req):
        now = self._vEnv.now

        assert req.isComplete
        assert req.segId in self._vBufManBuffer and not self._vBufManBuffer[req.segId]['seg'].isComplete
        self._vBufManBuffer[req.segId] = {"hvComplete":req.isComplete, "seg": req}
        self._vBufManRemoteFetchingQueue[req.segId] += f" done:{now}"
        if self._vBufManNextSegId == req.segId and not self._vBufManActionPending:
            self._rBufferManager()

#=============================================
    def _rBufManIinitRemoteFetch(self, req):
        now = self._vEnv.now
        req = self._vBufManBuffer[req.segId].get("seg", None)
        if req.isComplete:
            return
        if req.segId in self._vBufManRemoteFetchingQueue:
            return

        playbackTime = self.playbackTime
        segPlaybackStartTime = req.segId * self._vVideoInfo.segmentDuration
        thresh = self._vBufManRemoteBufThresh * self._vVideoInfo.segmentDuration
        waitTime = max(0, min(thresh, segPlaybackStartTime - playbackTime - thresh)) #waitTime=0 if syncSeg
        if req.syncSeg: waitTime = 0

        self._vBufManRemoteFetchingQueue[req.segId] = f"fetching:{now+waitTime}"
        self._rRunAfter(waitTime, self._vEnv._rFetchCompletePacket, req)

#=============================================
    def _rBufferManager(self):
        nextBufSeg = self._vBufManNextSegId
        now = self._vEnv.now
#         assert nextBufSeg in self._vBufManBuffer, f"Next segment does not exists in the buffer during startup: {getPosition()}"
        assert self._vBufManRebuffering != self._vBufManActionPending #it easy

        bufSegInfo = self._vBufManBuffer.get(nextBufSeg, None)
        if not bufSegInfo or (not bufSegInfo['seg'].isComplete and bufSegInfo['seg'].segId in self._vBufManRemoteFetchingQueue):
            if self._vBufManRebuffering:
                return #it is odd, probably it will never happen
            self._vBufManRebuffering = True
            self._vBufManRebufferingFrom = now
            self._vBufManActionPending = False #it will continue when new seg arrives
            return

        assert bufSegInfo['seg'].isComplete #it is meaningless and we should debug how this can happen
        req = bufSegInfo["seg"]
        segId = req.segId
        segPlaybackStartTime = segId * self._vVideoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + req.segmentDuration


        if self._vBufManRebuffering:
            assert self._vBufManRebufferingFrom >= 0
            stallTime = now - self._vBufManRebufferingFrom
            self._vTotalStallTime += stallTime
            self._vStallsAt.append((segPlaybackStartTime, stallTime, req.qualityIndex, req.downloader==self._vEnv))
            self._vBufManRebufferingFrom = -1
            self._vBufManRebuffering = False


        if True:
            self._vBufManNextSegId = req.segId + 1
            req.markUsed()
            self._vBufManRebuffering = False
            self._vBufManRebufferingFrom = -1
            self._vPlaybacktime = segPlaybackStartTime
            self._vRequests.append(req)
            self._vSegIdPlaybackTime[req.segId] = (self._vEnv.now, req)
            self._vTotalPlayableTime += req.segmentDuration

            self._vQualitiesPlayed += [req.qualityIndex]
            self._vQualitiesPlayedOverTime += [(now, req.qualityIndex, req.segId)]

            self._vBufferLenOverTime += [(now, req.segmentDuration)]
            self._vLastBitrateIndex = req.qualityIndex

            self._vBufManActionPending = False
            self._vBufManActionId = -1

            self._vBufManPlayinSegId = req.segId
            self._vBufManPlayingSegStartedAt = now


            if self._vBufManNextSegId < self._vVideoInfo.segmentCount:
                self._rRunBufManAfter(req.segmentDuration)
            elif self._vBufManNextSegId == self._vVideoInfo.segmentCount:
                self._vEnv.finishedAfter(req.segmentDuration)
            else:
                assert False, "Some issue"




#=============================================
    def _rHandleStartup(self, req): #unlike old implementation, I don't care about global playback sync in case of live streaming
        now = self._vEnv.now

        startUpDelay = now - self._vStartedAt
        segPlaybackStartTime = req.segId * self._vVideoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + req.segmentDuration

        self._vBufferUpto = segPlaybackEndTime
        self._vBufManNextSegId = req.segId + 1
        req.markUsed()
        self._vBufManRebuffering = False
        self._vFirstSegmentDlTime = req.timetaken
        self._vIsStarted = True
        self._vNextSegmentIndex = req.segId + 1
        self._vPlaybacktime = segPlaybackStartTime
        self._vRequests.append(req)
        self._vSegIdPlaybackTime[req.segId] = (self._vEnv.now, req)
        self._vStartingPlaybackTime = segPlaybackStartTime
        self._vStartingSegId = req.segId
        self._vStartUpDelay = startUpDelay
        self._vTotalPlayableTime += req.segmentDuration

        self._vQualitiesPlayed += [req.qualityIndex]
        self._vQualitiesPlayedOverTime += [(now, req.qualityIndex, req.segId)]

        self._vBufferLenOverTime += [(now, req.segmentDuration)]
        self._vLastBitrateIndex = req.qualityIndex

        self._vBufManPlayinSegId = req.segId
        self._vBufManPlayingSegStartedAt = now

        self._vBufManBuffer[req.segId] = {"hvComplete":req.isComplete, "seg": req}

        self._rRunBufManAfter(req.segmentDuration)

        for cb in self._vStartUpCallback:
            cb(self)
        #Previously we wanted to keep all the player in sync in case of live streaming by skipping segments in case of late arrival. However we don't need this accuracy. So, we will ignore. Instead, it will be taken care during group formation.

#=============================================
    def _rRunBufManAfter(self, sec):
        assert not self._vBufManActionPending
        assert self._vBufManActionId == -1
        self._vBufManActionId = self._rRunAfter(sec, self._rBufferManager)
        self._vBufManActionPending = True

#=============================================
    def _rRunAfter(self, *kw, **kwa): #wrapper function for shortcut. args, after(sec), cb, args
        return self._vEnv.runAfter(*kw, **kwa)

#=============================================
    def _rAddToBufferInternal(self, req, simIds = None):
        if self._vDead: return
        self._rAddToBufferToBufferManager(req, simIds)
        return


#=============================================
    def _rDownloadNextData(self, buflen=0):
        if self._vDead: return

        now = self._vEnv.getNow()
        nextSegId = self._vNextSegmentIndex
        nextQuality = self._vCurrentBitrateIndex
        sleepTime, nextQuality = self._vAbr.getNextDownloadTime(self._vMaxPlayerBufferLen, \
            self.bufferUpto, self._vPlaybacktime, now, self._vNextSegmentIndex)
        self._vCurrentBitrateIndex = nextQuality
        self._vEnv._rDownloadNextData(nextSegId, nextQuality, sleepTime)



#=============================================
    def _rIsAvailable(self, segId):
        if self._vDead: return -1

        assert segId < self._vVideoInfo.segmentCount
        now = self._vEnv.getNow()
        ePlaybackTime = now - self._vGlobalStartedAt
        avlUpTo = self._vVideoInfo.globalDelayPlayback + ePlaybackTime
        segStartTime = (segId+1)*self._vVideoInfo.segmentDuration
        return segStartTime - avlUpTo

#=============================================
    def _rCalculateQoE(self):
        if self._vDead: return
        if self._vPlaybacktime == 0:
            return 0 #not sure. But I think it is better

        return measureQoE(self._vVideoInfo.bitrates, self._vQualitiesPlayed, self._vTotalStallTime, self._vStartUpDelay, False)

#=============================================
    def _rFinish(self):
        if self._vDead: return
#         assert self.playbackTime > 0
        if self._vAbr and "stopAbr" in dir(self._vAbr) and callable(self._vAbr.stopAbr):
            self._vAbr.stopAbr()
        self._vFinished = True
        self._vBufferLenOverTime.append((self._vEnv.getNow(), 0))
        self._vQualitiesPlayedOverTime.append((self._vEnv.getNow(), 0, -1))
        myprint("Simulation finished at:", self._vEnv.getNow(), "totalStallTime:", self._vTotalStallTime, "startUpDelay:", self._vStartUpDelay, "firstSegDlTime:", self._vFirstSegmentDlTime, "segSkipped:", self._vSegmentSkiped)
        myprint("QoE:", self._rCalculateQoE())
        myprint("stallTime:", self._vStallsAt)
#         myprint("Quality played:", self._vQualitiesPlayed)
#         myprint("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
#                 "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)

#=============================================
    def start(self, startedAt = -1):
        segId = self._vNextSegmentIndex
        now = self._vEnv.getNow()
        self._vStartedAt = self._vGlobalStartedAt = now
        if startedAt >= 0:
            playbackTime = now - startedAt
            self._vNextSegmentIndex = int((playbackTime)/self._vVideoInfo.segmentDuration)
            self._vBufManNextSegId = self._vNextSegmentIndex
#             while (self._vNextSegmentIndex + 1) * self._vVideoInfo.segmentDuratio`n < playbackTime + PLAYBACK_DELAY_THRESHOLD:
#                 self._vNextSegmentIndex += 1
#             self._vNextSegmentIndex += 1
            self._vCanSkip = True
            self._vGlobalStartedAt = startedAt
        self._vLastEventTime = now
        self._rDownloadNextData(0)

