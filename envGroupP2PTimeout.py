import os
import math
import json
import matplotlib.pyplot as plt
import mpld3

from envSimple import SimpleEnvironment, np, Simulator, load_trace, video, P2PNetwork
from group import GroupManager
import randStateInit as randstate
from easyPlotViewer import EasyPlot
from calculateMetric import measureQoE



LOG_LOCATION = "./results/"

SEGMENT_NOT_WORKING = 0
SEGMENT_WORKING = 1
SEGMENT_CACHED = 2
SEGMENT_PEER_WAITING = 3
SEGMENT_IN_QUEUE = 4
SEGMENT_SLEEPING = 5
SEGMENT_PEER_WORKING = 6

SEGMENT_STATUS_STRING = [
"SEGMENT_NOT_WORKING",
"SEGMENT_WORKING",
"SEGMENT_CACHED",
"SEGMENT_PEER_WAITING",
"SEGMENT_IN_QUEUE",
"SEGMENT_SLEEPING",
"SEGMENT_PEER_WORKING",
]

class SegmentDlStat:
    def __init__(self):
        self._status = SEGMENT_NOT_WORKING
        self.peerStartedAt = -1
        self.peerResponsible = None
        self.peerStatus = {}
        self.peerTimeoutHappened = False
        self.peerTimeoutRef = -1
        self.servingTo = []
        self.autoEntryOver = False

    @property
    def statusString(self):
        return SEGMENT_STATUS_STRING[self._status]

    @property
    def status(self):
        return self._status

    @status.setter
    def status(s, st):
        if s._status == SEGMENT_CACHED:
            assert st == SEGMENT_CACHED
        if s._status == SEGMENT_WORKING:
            assert st == SEGMENT_WORKING or st == SEGMENT_CACHED
        s._status = st

class GroupP2PEnvTimeout(SimpleEnvironment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, *kw, **kws):
        super().__init__(vi, traces, simulator, abr, peerId, *kw, **kws)
#         self._vAgent = Agent(vi, self, abr)
        self._vDownloadPending = False
        self._vSegmentDownloading = -1
        self._vGroup = grp
        self._vCatched = {}
        self._vOtherPeerRequest = {}
        self._vTotalDownloaded = 0
        self._vTotalUploaded = 0
        self._vStarted = False
        self._vFinished = False

        self._vSegmentStatus = [SegmentDlStat() for x in range(self._vVideoInfo.segmentCount)]
        self._vGroupNodes = None
        self._vQueue = []

        self._vEarlyDownloaded = 0
        self._vNormalDownloaded = 0
        self._vThroughPutData = []
        self._vDownloadQueue = []
        self._vServingPeers = {}
        self._vDownloadedReqByItSelf = []
        self._vTimeoutDataAndDecision = {} # segid -> data

    def playerStartedCB(self, *kw, **kwa):
        if self._vGroup:
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)
        self._vStarted = True

    def die(self):
        self._vDead = True
        self._vGroup.remove(self, self._vAgent.nextSegmentIndex)

    def schedulesChanged(self, changedFrom, nodes, sched):
        self._vGroupNodes = nodes

    def _rGetRtt(self, node):
        return self._vGroup.getRtt(self, node)

    def _rTransmissionTime(self, *kw):
        return self._vGroup.transmissionTime(self, *kw)

    @property
    def now(self):
        return self.getNow()

#=============================================
    def _rFinish(self):
        if self._vResultPath:
            dpath = os.path.join(self._vResultPath, "groupP2PTimeout-timeoutdata")
            if not os.path.isdir(dpath):
                os.makedirs(dpath)
            fpath = os.path.join(dpath, "%s.log"%(self._vPeerId))
            with open(fpath, "w") as fp:
                points = sorted(list(self._vTimeoutDataAndDecision.items()), key=lambda x:x[0])
                for seg,pt in points:
                    print(json.dumps(pt), file=fp)
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
        print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)
        print("Early download:", self._vEarlyDownloaded, "normal:", self._vNormalDownloaded)
        print("video id:", self._vPeerId)
        print("=============================")
        self._vFinished = True

#=============================================
    def _rDownloadNextDataTimeout(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

#=============================================
    def _rAddToAgentBuffer(self, req):
        segId = req.segId
        if segId in self._vTimeoutDataAndDecision:
            br = self._vVideoInfo.bitrates
            ql = [self._vAgent._vQualitiesPlayed[-1], req.qualityIndex]
            stall = self._vAgent.stallTime
            reward = measureQoE(br, ql, stall, 0)
            self._vTimeoutDataAndDecision[segId] += [reward]

        self._vAgent._rAddToBufferInternal(req)

#=============================================
# return point after download completed i.e. on simulation event, Only for self dl
    def _rAddToBuffer(self, req, simIds = None):
        if self._vDead: return
        segId, clen = req.segId, req.clen
        seg = self._vSegmentStatus[segId]
        self._rDistributeToOther(req) #sending to others
        self._vDownloadedReqByItSelf.append(req)
        if seg.status == SEGMENT_CACHED:
            return
        assert seg.status != SEGMENT_CACHED
        self._vTotalDownloaded += clen
        self._vDownloadPending = False
        seg.status = SEGMENT_CACHED
        self._vCatched[segId] = req

        seg = self._vSegmentStatus[segId]
        self._rDownloadFromDownloadQueue()

        if segId == self._vAgent.nextSegmentIndex and seg.autoEntryOver:
            self._rAddToAgentBuffer(req)

        self._vThroughPutData += [(self.now, req.throughput)]

        if self._vGroup.currentSchedule(self, segId) == self:
           for node in self._vGroupNodes:
               if node == self:
                   continue
               node._rPeerSegmentStatus(self, segId, SEGMENT_CACHED)

#=============================================
    def _rDistributeToOther(self, req):
        if not self._vGroupNodes:
            return
        for node in self._vGroupNodes:
            if node == self:
                continue
            rtt = self._rGetRtt(node)
            seg = node._vSegmentStatus[req.segId]
            if seg.status in [SEGMENT_WORKING, SEGMENT_CACHED]:
                continue
            if seg.status != SEGMENT_PEER_WORKING:
                rtt = self._rTransmissionTime(node, req.clen)
                seg.status = SEGMENT_PEER_WORKING
                seg.peerStartedAt = self.now
                seg.peerResponsible = self
            elif seg.peerResponsible != self:
                # segment is peer waiting but for some other peer
                continue
            servingTos = self._vServingPeers.setdefault(req.segId, [])
            if node not in servingTos:
                servingTos.append(node)
            self.runAfter(rtt, self._rSendToOtherPeer, node, req)


#=============================================
    def _rPredictedThroughput(self):
        #as per rate based algo
        thrpt = [1/x for t, x in self._vThroughPutData[-5:]]
        return len(thrpt)/sum(thrpt)

#=============================================
# exit point from this class to envSimple
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return
        assert sleepTime == 0
        if nextSegId > self._vAgent.nextSegmentIndex:
            self._vEarlyDownloaded += 1
        else:
            self._vNormalDownloaded += 1
        self._vDownloadPending = True
        self._rFetchNextSeg(nextSegId, nextQuality)
        if self._vGroup.currentSchedule(self, nextSegId) == self:
           for node in self._vGroupNodes:
               if node == self:
                   continue
               node._rPeerSegmentStatus(self, nextSegId, SEGMENT_WORKING) #this function suppose to be called after some time i.e. through simulator


#=============================================
    def _rAddToDownloadQueue(self, nextSegId, nextQuality, position=float("inf")):
        seg = self._vSegmentStatus[nextSegId]
        assert seg.status == SEGMENT_NOT_WORKING
        position = min(position, len(self._vDownloadQueue))
        self._vDownloadQueue.insert(position, (nextSegId, nextQuality))
        self._rDownloadFromDownloadQueue()

#=============================================
    def _rDownloadFromDownloadQueue(self):
        if self._vDownloadPending:
            return
        while len(self._vDownloadQueue):
            segId, ql = self._vDownloadQueue.pop(0)
            seg = self._vSegmentStatus[segId]
            if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
                continue
            if self._vStarted:
                node = self._vGroup.currentSchedule(self, segId)
#                 if node == self:
#                     ql = self._rReAdjustQl(ql)
            seg.status = SEGMENT_WORKING
            self._rFetchSegment(segId, ql)
            break

#=============================================
    def _rEstimatedTimeToFreeUpDownloader(self):
        curFinishingTime = 0
        if self._vDownloadPending:
            timeElapsed, downLoadedTillNow, chsize = self._rDownloadStatus()
            assert chsize > 0
            if timeElapsed <= 0 or downLoadedTillNow <= 0:
                throughput = self._rPredictedThroughput()
                curFinishingTime = chsize * 8 / throughput
            else:
                curFinishingTime = (chsize - downLoadedTillNow) * timeElapsed/downLoadedTillNow

        queuingTime = 0
        for segId, ql in self._vDownloadQueue:
            queuingTime += self._rEstimateDownloadTime(segId, ql)

        return curFinishingTime + queuingTime

#=============================================
    def _rEstimateDownloadTime(self, segId, ql):
        estimatedSize = round(self._vVideoInfo.bitrates[ql] * self._vVideoInfo.segmentDuration / 8)
        estimatedDownloadTime = estimatedSize * 8 / self._rPredictedThroughput()
        return estimatedDownloadTime

#=============================================
    def _rPeerSegmentStatus(self, node, segId, status):
        seg = self._vSegmentStatus[segId]
        assert status in [SEGMENT_CACHED, SEGMENT_WORKING]
        if status == SEGMENT_WORKING:
            if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
                return
            seg.status = SEGMENT_PEER_WORKING
            seg.peerStartedAt = self.now
            seg.peerResponsible = node

            node._vSegmentStatus[segId].servingTo += [self]
            node._vServingPeers.setdefault(segId, []).append(self)
        seg.peerStatus[node] = status

#=============================================
    def _rDownloadNextDataBeforeGroupStart(self, nextSegId, nextQuality, sleepTime):
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataBeforeGroupStart, nextSegId, nextQuality, 0)
            return
        if seg.status == SEGMENT_SLEEPING or seg.status == SEGMENT_NOT_WORKING:
            seg.status = SEGMENT_NOT_WORKING
            self._rAddToDownloadQueue(nextSegId, nextQuality)
            return

        assert False


#=============================================
    def _rTimeoutForPeer(self, segId, ql = -1):
        if ql == -1:
            ql = self._vGroup.getQualityLevel(self)
#         if ql > 0:
#             ql = ql - 1
        downloadTIme = self._vVideoInfo.bitrates[ql] * self._vVideoInfo.segmentDuration / self._rPredictedThroughput()
        downloadTIme = max(self._vVideoInfo.segmentDuration, downloadTIme)
        bufferLeft = self._vAgent.bufferLeft
        timeout = bufferLeft - downloadTIme
        return round(timeout, 3), ql

#=============================================
    def _rReAdjustQl(self, ql):
        thrpt = self._rPredictedThroughput()
        while ql:
            if self._vVideoInfo.bitrates[ql] < thrpt:
                return ql
            ql -= 1
        return ql

#=============================================
    def _rLogTimeoutDecisionData(self, segId, timeBudget, remoteStatus, localStatus, decision):
        # decision -1 if wait for other peer to finish, >= 0 startdownloading
        seg = self._vSegmentStatus[segId]
        lastDownloads = [(0,0,0)]*5 + [(x.throughput, x.downloadStarted, x.downloadFinished) for x in self._vDownloadedReqByItSelf[-5:]]
        lastLocalDownLoads = lastDownloads[-5:]

        lastDownloads = [(0,0,0)]*5 + [(x.throughput, x.downloadStarted, x.downloadFinished) for x in seg.peerResponsible._vDownloadedReqByItSelf[-5:]]
        lastRemoteDownLoads = lastDownloads[-5:]

        lastRemoteDownLoads = tuple(zip(*lastRemoteDownLoads))
        lastLocalDownLoads = tuple(zip(*lastLocalDownLoads))

        localQualities = [0]*5 + self._vAgent._vQualitiesPlayed
        localQualities = tuple(localQualities[-5:])

        point = (timeBudget, localQualities,) + localStatus + lastLocalDownLoads + remoteStatus + lastRemoteDownLoads
#         print(point)
        assert segId not in self._vTimeoutDataAndDecision
        dataPoint = self._vTimeoutDataAndDecision.setdefault(segId, [])
        dataPoint += [point, decision]

    
#=============================================
    def _rPeerDownloadTimeout(self, downloader, segId, ql):
        seg = self._vSegmentStatus[segId]
        seg.peerTimeoutHappened = True
        seg.peerTimeoutRef = -1
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING]:
            return
        if seg.status == SEGMENT_PEER_WORKING and self._vAgent.nextSegmentIndex == segId:
            #it is very complecated. Need to know how much it have downloaded so far.
            #it will be great if we can measure download speed some how. Important thing
            #is get some prediction on peer finishing time.
            elapsed, downloaded, clen = remoteStatus = seg.peerResponsible._rGetPeerDownloadStatus(self, segId)
            timeleft = float("inf")
            ql = self._rReAdjustQl(ql)

            if elapsed > 0 and downloaded > 0:
                timeleft = round((clen - downloaded)*elapsed/downloaded, 3)

            timeToFinishDl = self._rEstimateDownloadTime(segId, ql)
            localStatus = (0, 0, 0)
            if self._vDownloadPending:
                elapsed, downloaded, clen = localStatus = self._rDownloadStatus()

                if downloaded > 0:
                    timeToFinishDl += (clen - downloaded)*elapsed/downloaded
                else:
                    timeToFinishDl += clen * 8 / self._rPredictedThroughput()

            timeBudget = round(segId * self._vVideoInfo.segmentDuration - self._vAgent.playbackTime, 3)
            
            if timeToFinishDl > timeleft:
                self._rLogTimeoutDecisionData(segId, timeBudget, remoteStatus, localStatus, -1)
                return
            if timeleft <= timeBudget:
                self._rLogTimeoutDecisionData(segId, timeBudget, remoteStatus, localStatus, -1)
                return

            self._rLogTimeoutDecisionData(segId, timeBudget, remoteStatus, localStatus, ql)
            seg.status = SEGMENT_PEER_WAITING

        if seg.status == SEGMENT_PEER_WAITING:
            seg.status = SEGMENT_NOT_WORKING
        if self._vAgent.nextSegmentIndex == segId:
            self._rAddToDownloadQueue(segId, ql, 0)
        else:
            self._rAddToDownloadQueue(segId, ql)

#=============================================
# entry point from agent
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]

        if not self._vStarted or len(self._vGroupNodes) <= 1:
            seg.autoEntryOver = True
            return self._rDownloadNextDataBeforeGroupStart(nextSegId, nextQuality, sleepTime)

        if sleepTime > 0:
            self.runAfter(sleepTime, self._rDownloadNextData, nextSegId, nextQuality, 0)
            return

        if seg.status == SEGMENT_CACHED:
            assert self._vAgent.nextSegmentIndex >= nextSegId
            if self._vAgent.nextSegmentIndex == nextSegId:
                req= self._vCatched[nextSegId]
                self._rAddToAgentBuffer(req)
            return

        seg.autoEntryOver = True

        if seg.status == SEGMENT_WORKING \
                or seg.status == SEGMENT_SLEEPING \
                or seg.status == SEGMENT_PEER_WAITING \
                or seg.status == SEGMENT_IN_QUEUE:
            return

        if seg.status == SEGMENT_PEER_WORKING:
            if seg.peerTimeoutRef == -1:
                timeout, ql = self._rTimeoutForPeer(nextSegId)
                if timeout > 0:
                    ref = self.runAfter(timeout, self._rPeerDownloadTimeout, seg.peerResponsible, nextSegId, ql)
                    seg.peerTimeoutRef = ref
                else:
                    self._rPeerDownloadTimeout(seg.peerResponsible, nextSegId, ql)
            return

        assert sleepTime == 0

        seg.status = SEGMENT_NOT_WORKING

        self._rDownloadNextDataGroup(nextSegId, nextQuality, 0)

#=============================================
    def _rDownloadNextDataGroup(self, nextSegId, nextQuality, sleepTime):
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        downloader = self._vGroup.currentSchedule(self, nextSegId)

        if downloader and downloader != self:
            timeout, ql = self._rTimeoutForPeer(nextSegId)
            seg.status = SEGMENT_PEER_WAITING
            if timeout <= 0:
                self._rPeerDownloadTimeout(downloader, nextSegId, ql)
            else:
                ref = self.runAfter(timeout, self._rPeerDownloadTimeout, downloader, nextSegId, ql)
                seg.peerTimeoutRef = ref

        nextSegId, waitTime = self._rFindNextDownloadableSegment(nextSegId)
        if nextSegId < 0 or waitTime > 0:
            return

        seg = self._vSegmentStatus[nextSegId]
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
            return

        self._rAddToDownloadQueue(nextSegId, self._vGroup.getQualityLevel(self))



#=============================================
# findout next segId to be downloaded
    def _rFindNextDownloadableSegment(self, nextSegId):
        now = self.getNow()
        while nextSegId < self._vVideoInfo.segmentCount:
            waitTime = self._vAgent._rIsAvailable(nextSegId)
            downloader = self._vGroup.currentSchedule(self, nextSegId) #self._vGroup.currentSchedule(self, nextSegId)
            if not downloader or downloader == self:
                return (nextSegId, round(waitTime, 3))
            nextSegId += 1
        return (-1, 0)

#=============================================
    def _rGetPeerDownloadStatus(self, node, segId): #we dont need to call this function through simulator
        seg = self._vSegmentStatus[segId]
        assert seg.status in [SEGMENT_WORKING, SEGMENT_CACHED]
        segNode = node._vSegmentStatus[segId]
        assert segNode.peerResponsible == self

        if seg.status == SEGMENT_WORKING:
            timeElapsed, downLoadedTillNow, chsize = self._rDownloadStatus()
            return timeElapsed, downLoadedTillNow, chsize
        else: # seg.status == SEGMENT_CACHED
            downCompletedAt = self._vCatched[segId].downloadFinished
            peerStartedAt = seg.peerStartedAt
            chsize = self._vCatched[segId].clen
            if peerStartedAt < downCompletedAt: #i.e. peer was waiting
                totalDur = downCompletedAt-peerStartedAt
                elapsed = max(totalDur - self._rGetRtt(node), 0)
                downloaded = chsize*elapsed/totalDur

                return elapsed, downloaded, chsize
            else:
                elapsed = max(self.now - downCompletedAt - self._rGetRtt(node), 0) #don't ask why
                expectedDur = self._rTransmissionTime(node, chsize)
                expectedDownloaded = chsize*elapsed/expectedDur
                return elapsed, expectedDownloaded, chsize


#=============================================
    def _rReceiveReq(self, node, req):
        if self._vDead: return

        segId = req.segId
        seg = self._vSegmentStatus[segId]
        assert seg.status != SEGMENT_WORKING
        if seg.status != SEGMENT_CACHED:
            seg.status = SEGMENT_CACHED
            self._vCatched[segId] = req
            if segId == self._vAgent.nextSegmentIndex and seg.autoEntryOver:
                self._rAddToAgentBuffer(req)
            node._vTotalUploaded += req.clen #this is not exactly the way it will
                                             #happen in the real world scenerio.
                                             #However, in real world,

#=============================================
#Calling other peer function
    def _rSendToOtherPeer(self, node, req):
        if self._vDead: return
#         self._vTotalUploaded += clen
        seg = node._vSegmentStatus[req.segId]
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING]:
            return
        if seg.status == SEGMENT_NOT_WORKING and seg.peerTimeoutHappened \
                and seg.peerResponsible == self:
            seg.status = SEGMENT_PEER_WORKING

        assert seg.status == SEGMENT_PEER_WORKING
        node._rReceiveReq(self, req)

        if req.segId in self._vServingPeers:
            servingTos = self._vServingPeers[req.segId]
            if node in servingTos:
                servingTos.remove(node)
            if len(servingTos) == 0:
                del self._vServingPeers[req.segId]

#=============================================
    def start(self, startedAt = -1):
        super().start(startedAt)
        self._vAgent.addStartupCB(self.playerStartedCB)

#=============================================
def randomDead(vi, traces, grp, simulator, agents, deadAgents):
    now = simulator.getNow()
    if now - 5 < vi.duration:
        return
    if np.random.randint(2) == 1 or len(deadAgents) == 0:
        nextDead = np.random.randint(len(agents))
        agents[nextDead].die()
        del agents[nextDead]
        trace = (agents[nextDead]._vCookedTime, agents[nextDead]._vCookedBW, agents[nextDead]._vTraceFile)
        deadAgents.append((agents[nextDead]._vPeerId, trace))
    else:
        startAgain = np.random.randint(len(deadAgents))
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        np.random.shuffle(deadAgents)
        nodeId, trace = deadAgents.pop()
        env = GroupP2PEnvTimeout(vi, trace, simulator, None, grp, nodeId)
        simulator.runAfter(10, env.start, 5)
    ranwait = np.random.uniform(0, 1000)
    for x in agents:
        if not x._vDead and not x._vFinished:
            simulator.runAfter(ranwait, randomDead, vi, traces, grp, simulator, agents, deadAgents)
            break

#=============================================
def storeAsPlotViewer(path, fig, label):
    with open(path, "a") as fp:
        print("<br><br>", file=fp)
        print("<div><b>", label, "</b></div>", file=fp)
        print('<div style="float:left; display:inline-block; width:95%">', file=fp)
        mpld3.save_html(fig, fp)
        print('</div><div style="clear:both"></div><br>', file=fp)

def encloser(st, label):
        p = "<br><br>"
        p += "<div><b>" + label + "</b></div>"
        return p + st

def plotIdleStallTIme(dpath, group):
    if not os.path.isdir(dpath):
        os.makedirs(dpath)

    colors = ["blue", "green", "red", "cyan", "magenta", "yellow", "black"]

    pltHtmlPath = os.path.join(dpath,"groupP2PTimeout.html")
    open(pltHtmlPath, "w").close()
    eplt = EasyPlot()
    for ql,grpSet in group.groups.items():
        for grp in grpSet:
            grpLabel = str([x._vPeerId for x in grp.getAllNode()])
            label = "<hr><h2>BufferLen</h2>"
            label += " NumNode:" + str(len(grp.getAllNode()))
            label += " Quality Index: " + str(grp.qualityLevel)
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vBufferLenOverTime
                Xs, Ys = list(zip(*pltData))
                eplt.plot(Xs, Ys, marker="x", label=str(ag._vPeerId), color=colors[i%len(colors)])

                label += "\n<br><span style=\"color: " + colors[i%len(colors)] + "\" >PeerId: " + str(ag._vPeerId)
                label += " avgQualityIndex: " + str(ag._vAgent.avgQualityIndex)
                label += " avgStallTime: " + str(ag._vAgent.totalStallTime)
                label += " startedAt: " + str(ag._vAgent._vStartedAt)
                label += " traceIdx: " + str(AGENT_TRACE_MAP.get(ag._vPeerId, 0))
                label += "</span>"
#             storeAsPlotViewer(pltHtmlPath, fig, label)
            eplt.setFigHeader(label)
            label = "<h2>workingTime</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vWorkingTimes
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
#             storeAsPlotViewer(pltHtmlPath, fig, label)
            eplt.setFigHeader(label)
            label = "<h2>StallTime</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vTimeSlipage
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.plot(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
#             storeAsPlotViewer(pltHtmlPath, fig, label)
            eplt.setFigHeader(label)

            label = "<h2>qualityLevel</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vQualitiesPlayedOverTime
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="post", color=colors[i%len(colors)])
#             storeAsPlotViewer(pltHtmlPath, fig, label)
            eplt.setFigHeader(label)

    with open(pltHtmlPath, "w") as fp:
        eplt.printFigs(fp, width=1000, height=400)

#=============================================
def logThroughput(ag):
    logPath = os.path.join(LOG_LOCATION, "logThroughput")
    if not os.path.isdir(logPath):
        os.makedirs(logPath)
    path = os.path.join(logPath, "%s.csv"%(ag._vPeerId))
    with open(path, "w") as fp:
        print("#time\tBandwidth", file=fp)
        for t, x in ag._vThroughPutData:
            print("{t}\t{x}".format(t=t, x=x), file=fp)

AGENT_TRACE_MAP = {}

#=============================================
def experimentGroupP2PTimeout(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    maxTime = 0
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        startsAt = np.random.randint(vi.duration/2)
        trace = traces[idx]
        env = GroupP2PEnvTimeout(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startsAt, env.start, 5)
        maxTime = 101.0 + x
        AGENT_TRACE_MAP[nodeId] = idx
        ags.append(env)
    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
        logThroughput(a)
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

#=============================================
def experimentGroupP2PSmall(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []

    for trx, nodeId, startedAt in [( 5, 267, 107), (36, 701, 111), (35, 1800, 124), (5, 2033, 127)]:
        trace = traces[trx]
        env = GroupP2PEnvTimeout(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startedAt, env.start, 5)
        AGENT_TRACE_MAP[nodeId] = trx
        ags.append(env)

    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
        logThroughput(a)
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    experimentGroupP2PTimeout(traces, vi, network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
