import numpy
import pickle

def storeCurrentState(fp = "/tmp/randstate"):
    state = numpy.random.get_state()
    with open(fp, "wb") as f:
        pickle.dump(state, f, pickle.HIGHEST_PROTOCOL)
        print("saved")

def loadCurrentState(fp = "/tmp/randstate"):
    with open(fp, "rb") as f:
        state = pickle.load(f)
        numpy.random.set_state(state)
        print("loaded")
