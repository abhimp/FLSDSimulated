REBUF_PENALTY = 4.3  # 1 sec rebuffering -> this number of Mbps
SMOOTH_PENALTY = 1
M_IN_K = 1000.0

def measureQoE(bitrates, qualityLevels, stallTimes, startUpDelay, reward=True):
    qualityPlayed = [bitrates[x] for x in qualityLevels]
    assert len(qualityPlayed) > 0
    avgQl = qualityPlayed[-1]
    avgQualityVariation = 0 if len(qualityPlayed) == 1 else abs(qualityPlayed[-1] - qualityPlayed[-2])
    if not reward:
        avgQl = sum(qualityPlayed)*1.0/len(qualityPlayed)
        avgQualityVariation = 0 if len(qualityPlayed) == 1 else sum([abs(bt - qualityPlayed[x - 1]) for x,bt in enumerate(qualityPlayed) if x > 0])/(len(qualityPlayed) - 1)

    reward = avgQl / M_IN_K \
            - REBUF_PENALTY * stallTimes \
             - SMOOTH_PENALTY * avgQualityVariation / M_IN_K

    return reward
