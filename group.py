
class Group():
    def __init__(s, ql):
        s.nodes = []
        s.schedules = {}
        s.segMents = 0
        s.nodeAddedWithSegId = {}
        s.qualityLevel = ql

    def __schedule(s, segId):
        nodeslist = list(s.nodes)
        nodeslist.sort(key=lambda x: - s.nodeAddedWithSegId[x])
        for i, segId in enumerate(range(segId, 1000)):
            x = i % len(nodeslist)
            s.schedules[segId] = nodeslist[x]

    def add(s, node, segId = 0):
        if node in s.nodes:
            return
        s.nodes.append(node)
        s.nodeAddedWithSegId[node] = segId
        s.__schedule(segId)

    def remove(s, node, segId = 0):
        if node not in s.nodes:
            return
        s.nodes.remove(node)
        s.__schedule(segId)

    def currentSchedule(s, node, segId):
        if node not in s.nodes:
            raise Exception("Node not in the group")
        if segId not in s.schedules:
            return
        if segId < s.nodeAddedWithSegId[node]:
            return
        downloader = s.schedules[segId]
        return downloader

class Groups():
    def __init__(self):
        self.groups = []
        self.peers = {}


