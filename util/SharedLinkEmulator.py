import sys
from simulator.simulator import Simulator

def gDict(**kw): return kw


#SIMULATOR TIME is seconds

class SharedDownloader:
    def __init__(self, simulator, linkCapa=-1, linkDelay=50): #capa in bps, linkDelay in ms
        self.simulator = simulator
        self.linkCapa = linkCapa
        self.linkDelay = linkDelay

        self.nextJobId = 1

        self.jobInfos = {} #jobId: details
        self.onGoingJobs = []

        self.lastSpeedAdjustedAt = simulator.getNow()

    @property
    def now(self):
        return self.simulator.getNow()

    def addJob(self, updateCB, finishedCB, cbArg1, size, buflen=64*1024, excessDelay = 0):
        assert excessDelay >= 0
        assert buflen >= 1024
        jobId = self.nextJobId
        self.nextJobId = jobId + 1

        jobInfo = gDict(
                    finished = False,
                    downloaded = 0, #bytes
                    lastEventAt = self.now, #second
                    curSpeed = 0, #bps
                    jobId = jobId,

                    updateCB = updateCB,
                    finishedCB = finishedCB,
                    cbArg1 = cbArg1,
                    size = size, #bytes
                    buflen = buflen, #bytes
                    excessDelay = excessDelay, #ms
                )

        assert jobId not in self.jobInfos
        self.jobInfos[jobId] = jobInfo

        self.onGoingJobs.append(jobId)

        self.adjustJobSpeed()

        return jobId

    def cancelJob(self, jobId):
        if jobId not in self.onGoingJobs:
            return
        downloaded = self.getDownloaded(jobId)
        job = self.jobInfos[jobId]
        job["downloaded"] = downloaded
        job["lastEventAt"] = self.now
        job["finished"] = True
        self.onGoingJobs.remove(jobId)
        self.adjustJobSpeed()
        job["updateCB"](job["cbArg1"], job["downloaded"], self.now, job)

    def getJobSpeed(self, jobId):
        assert jobId in self.jobInfos
        info = self.jobInfos[jobId]
        buflen = info["buflen"]
        delay = self.linkDelay + self.jobInfos[jobId]["excessDelay"]
        speed = buflen*8/(delay*2/1000)
        return speed

    def getDownloaded(self, jobId):
        now = self.now
        id = jobId
        le = self.jobInfos[id]["lastEventAt"]
        sp = self.jobInfos[id]["curSpeed"]
        assert le <= now
        dld = self.jobInfos[id]["downloaded"] + ((now - le)*sp/8)
        if dld > self.jobInfos[id]["size"]:
            dld = self.jobInfos[id]["size"]
        return round(dld)

    def getExpTimeToFinish(self, jobId, downloaded, curSpeed):
        size = self.jobInfos[jobId]["size"]
        assert downloaded <= size

        remaining = size - downloaded

        if remaining == 0:
            return 0
        return remaining*8 / curSpeed

    def informFinished(self, finished):
        now = self.now
        for id in finished:
            job = self.jobInfos[id]
            job["finishedCB"](job["cbArg1"], job["downloaded"], now, job)

    def informStatus(self):
        now = self.now
        for id in self.onGoingJobs:
            job = self.jobInfos[id]
            job["updateCB"](job["cbArg1"], job["downloaded"], now, job)


    def adjustJobSpeed(self):
        now = self.now
        if now == self.lastSpeedAdjustedAt:
            return
        self.lastSpeedAdjustedAt = now
        downloaded = {id: self.getDownloaded(id) for id in self.onGoingJobs}

        finished = []
        for id in downloaded:
            job = self.jobInfos[id]
            assert job["size"] >= downloaded[id]
            job["downloaded"] = downloaded[id]
            job["lastEventAt"] = now
            done = job["size"] == downloaded[id]
            if done:
                job["finished"] = True
                self.onGoingJobs.remove(id)
                finished.append(id)

        if len(self.onGoingJobs) == 0:
            self.simulator.runAfter(0.001, self.informFinished, finished)
            self.simulator.runAfter(0.001, self.informStatus)
            return

        maxSpeeds = {id: self.getJobSpeed(id) for id in self.onGoingJobs}
        totSpeed = sum(maxSpeeds.values())
        if totSpeed > self.linkCapa and self.linkCapa > 0:
            print(f"{now} speed suppose to change", file=sys.stderr)
            maxSpeeds = {id: round((self.linkCapa * maxSpeeds[id] / totSpeed), 3) for id in maxSpeeds}
        finishingIn = {id: self.getExpTimeToFinish(id, downloaded[id], sp) for id,sp in maxSpeeds.items()}

        minFinishingTime = min(finishingIn.values())
        minFinishingTime = round(minFinishingTime, 3)
        if minFinishingTime == 0: minFinishingTime = 0.001

        for id in self.onGoingJobs:
            self.jobInfos[id]["curSpeed"] = maxSpeeds[id]

        self.simulator.runAfter(minFinishingTime, self.adjustJobSpeed)
        self.simulator.runAfter(0.001, self.informFinished, finished)
        self.simulator.runAfter(0.001, self.informStatus)

def updateCB(dlid, dlsize, now, job):
    size = job["size"]
    print(f"{dlid} at {now} downloaded {dlsize} {size}")

def finishedCB(dlid, dlsize, now, job):
    size = job["size"]
    print(f"{dlid} at {now} finished {dlsize} {size}")

def main():
    sim = Simulator()
    downloader = SharedDownloader(sim, linkCapa = 4*1000*1000, linkDelay=50)

    sim.runAt(1, downloader.addJob, updateCB, finishedCB, 1, 25*1024*1024, 1*1024*1024)
    sim.runAt(25, downloader.addJob, updateCB, finishedCB, 2, 25*1024*1024, 1*1024*1024)

    sim.run()

if __name__ == "__main__":
    main()
