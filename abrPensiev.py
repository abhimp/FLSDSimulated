
import base64
import urllib
import sys
import os
import json
import time
os.environ['CUDA_VISIBLE_DEVICES']=''

import numpy as np
import time
import itertools
import tensorflow as tf
import a3c

from calculateMetric import measureQoE 
from multiprocessing import Process, Pipe

######################## FAST MPC #######################

S_INFO = 6  # bit_rate, buffer_size, rebuffering_time, bandwidth_measurement, chunk_til_video_end
S_LEN = 8  # take how many frames in the past
MPC_FUTURE_CHUNK_COUNT = 5
# VIDEO_BIT_RATE = [300,750,1200,1850,2850,4300]  # Kbps
# BITRATE_REWARD = [1, 2, 3, 12, 15, 20]
# BITRATE_REWARD_MAP = {0: 0, 300: 1, 750: 2, 1200: 3, 1850: 12, 2850: 15, 4300: 20}
M_IN_K = 1000.0
BUFFER_NORM_FACTOR = 10.0
# CHUNK_TIL_VIDEO_END_CAP = 48.0
# TOTAL_VIDEO_CHUNKS = 48
DEFAULT_QUALITY = 0  # default video quality without agent
REBUF_PENALTY = 4.3  # 1 sec rebuffering -> this number of Mbps
SMOOTH_PENALTY = 1
TRAIN_SEQ_LEN = 100  # take as a train batch
MODEL_SAVE_INTERVAL = 100
RANDOM_SEED = 42
RAND_RANGE = 1000
ACTOR_LR_RATE = 0.0001
CRITIC_LR_RATE = 0.001
SUMMARY_DIR = './results'
LOG_FILE = './results/log'
# in format of time_stamp bit_rate buffer_size rebuffer_time video_chunk_size download_time reward
NN_MODEL = None
NN_MODEL = './model/pretrain_linear_reward.ckpt'

# CHUNK_COMBO_OPTIONS = []
SETUP_ABR_CALL_COUNTER = 0
def setup_abr(video, log_file_path=LOG_FILE):
    print("setup_abr called:", SETUP_ABR_CALL_COUNTER, "\n", "="*20)

    A_DIM = len(video.bitratesKbps)
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)

    sess = tf.Session() 
    log_file = open(log_file_path, 'w')

    actor = a3c.ActorNetwork(sess,
                             state_dim=[S_INFO, S_LEN], action_dim=A_DIM,
                             learning_rate=ACTOR_LR_RATE)
    critic = a3c.CriticNetwork(sess,
                               state_dim=[S_INFO, S_LEN],
                               learning_rate=CRITIC_LR_RATE)

    sess.run(tf.initialize_all_variables())
    saver = tf.train.Saver()  # save neural net parameters

    # restore neural net parameters
    nn_model = NN_MODEL
    if nn_model is not None:  # nn_model is the path to file
        saver.restore(sess, nn_model)
        print("Model restored.")

    init_action = np.zeros(A_DIM)
    init_action[DEFAULT_QUALITY] = 1

    s_batch = [np.zeros((S_INFO, S_LEN))]
    a_batch = [init_action]
    r_batch = []

    train_counter = 0

    last_bit_rate = DEFAULT_QUALITY
    last_total_rebuf = 0
    # need this storage, because observation only contains total rebuffering time
    # we compute the difference to get

    video_chunk_count = 0

    input_dict = {
                    'sess': sess, 
                    'log_file': log_file,
                    'actor': actor, 
                    'critic': critic,
                    'saver': saver, 
                    'train_counter': train_counter,
                    'last_bit_rate': last_bit_rate,
                    'last_total_rebuf': last_total_rebuf,
                    'video_chunk_coount': video_chunk_count,
                    's_batch': s_batch, 
                    'a_batch': a_batch, 
                    'r_batch': r_batch,
                    'chunkComboOptions': [],
                }

    # interface to abr_rl server
    return input_dict

FINISHED_PROC = "FINISHED_PROC"

def incId():
    global SETUP_ABR_CALL_COUNTER
    SETUP_ABR_CALL_COUNTER += 1

class AbrPensieve:
    def __init__(self, videoInfo, agent, log_file_path=LOG_FILE):
        self.agent = agent
        self.video = videoInfo
        self.parent_conn, child_conn = Pipe()
        self.proc = Process(target=self.otherProcConnection, args=(child_conn, videoInfo, log_file_path))
        incId()
        self.proc.start()
        ready = self.parent_conn.recv()
        if ready != "ready":
            print("="*50 + "\n" + "FATAL ERROR")
            print("="*50 + "\n")

    def stopAbr(self):
        if not self.proc:
            return
        rcv = {FINISHED_PROC : True}
        self.parent_conn.send(rcv)
        self.proc.join()
        self.proc = None

    def otherProcConnection(self, conn, videoInfo, log_file_path=LOG_FILE):
#         conn = conn
        abr = AbrPensieveProc(videoInfo, None, log_file_path)
        conn.send("ready")
        while True:
            rcv = conn.recv()
            if FINISHED_PROC in rcv:
                break
            info = abr.nextQuality(rcv)
            conn.send(info)

        print("="*50 + "\n" + "FINISHED:", SETUP_ABR_CALL_COUNTER)
        print("="*50 + "\n")

    def getSleepTime(self, buflen):
        if (self.agent._vMaxPlayerBufferLen - self.video.segmentDuration) > buflen:
            return 0
        sleepTime = buflen + self.video.segmentDuration - self.agent._vMaxPlayerBufferLen
        return sleepTime

    def getNextDownloadTime(self, *kw, **kws):
        if len(self.agent._vRequests) == 0:
            return 0, 0

        req = self.agent._vRequests[-1]
        
        bufferLeft = self.agent._vBufferUpto - self.agent._vPlaybacktime
        if bufferLeft < 0:
            bufferLeft = 0
        post_data = {
                'lastquality': self.agent._vLastBitrateIndex,
                'RebufferTime': self.agent._vTotalStallTime,
                'lastChunkFinishTime': req.downloadFinished,
                'lastChunkStartTime': req.downloadStarted,
                'lastChunkSize': req.clen,
                'buffer': bufferLeft,
                'lastRequest': self.agent.nextSegmentIndex,
                }
        self.parent_conn.send(post_data)
        ql = self.parent_conn.recv()
        return self.getSleepTime(bufferLeft), ql

class AbrPensieveProc:
    def __init__(self, videoInfo, agent, log_file_path=LOG_FILE):
        self.video = videoInfo
#         self.agent = agent
        input_dict = setup_abr(videoInfo, log_file_path)
        self.input_dict = input_dict
        self.sess = input_dict['sess']
        self.log_file = input_dict['log_file']
        self.actor = input_dict['actor']
        self.critic = input_dict['critic']
        self.saver = input_dict['saver']
        self.s_batch = input_dict['s_batch']
        self.a_batch = input_dict['a_batch']
        self.r_batch = input_dict['r_batch']
        self.pastBandwidthEsts = []
        self.pastErrors = []

    def get_chunk_size(self, quality, index):
        if index >= self.video.segmentCount: return 0
        return self.video.fileSizes[quality][index]

    
    def nextQuality(self, post_data):
        if ( 'pastThroughput' in post_data ):
            # @Hongzi: this is just the summary of throughput/quality at the end of the load
            # so we don't want to use this information to send back a new quality
            print ("Summary: ", post_data)
            return 0

        A_DIM = len(self.video.bitratesKbps)
        CHUNK_COMBO_OPTIONS = self.input_dict['chunkComboOptions']
        VIDEO_BIT_RATE = self.video.bitratesKbps
        BITRATE_REWARD = self.video.bitrateReward
        CHUNK_TIL_VIDEO_END_CAP = TOTAL_VIDEO_CHUNKS = self.video.segmentCount
        past_bandwidth_ests = self.pastBandwidthEsts
        past_errors = self.pastErrors

#================================================
        # option 1. reward for just quality
        # reward = post_data['lastquality']
        # option 2. combine reward for quality and rebuffer time
        #           tune up the knob on rebuf to prevent it more
        # reward = post_data['lastquality'] - 0.1 * (post_data['RebufferTime'] - self.input_dict['last_total_rebuf'])
        # option 3. give a fixed penalty if video is stalled
        #           this can reduce the variance in reward signal
        # reward = post_data['lastquality'] - 10 * ((post_data['RebufferTime'] - self.input_dict['last_total_rebuf']) > 0)

        # option 4. use the metric in SIGCOMM MPC paper
        rebuffer_time = float(post_data['RebufferTime'] -self.input_dict['last_total_rebuf'])

        # --linear reward--
        reward = VIDEO_BIT_RATE[post_data['lastquality']] / M_IN_K \
                - REBUF_PENALTY * rebuffer_time / M_IN_K \
                - SMOOTH_PENALTY * np.abs(VIDEO_BIT_RATE[post_data['lastquality']] -
                                          self.input_dict['last_bit_rate']) / M_IN_K

        reward = measureQoE(VIDEO_BIT_RATE, [self.input_dict['last_bit_rate'], post_data['lastquality']], rebuffer_time, 0)
        # --log reward--
        # log_bit_rate = np.log(VIDEO_BIT_RATE[post_data['lastquality']] / float(VIDEO_BIT_RATE[0]))   
        # log_last_bit_rate = np.log(self.input_dict['last_bit_rate'] / float(VIDEO_BIT_RATE[0]))

        # reward = log_bit_rate \
        #          - 4.3 * rebuffer_time / M_IN_K \
        #          - SMOOTH_PENALTY * np.abs(log_bit_rate - log_last_bit_rate)

        # --hd reward--
        # reward = BITRATE_REWARD[post_data['lastquality']] \
        #         - 8 * rebuffer_time / M_IN_K - np.abs(BITRATE_REWARD[post_data['lastquality']] - BITRATE_REWARD_MAP[self.input_dict['last_bit_rate']])

        self.input_dict['last_bit_rate'] = post_data['lastquality']
        self.input_dict['last_total_rebuf'] = post_data['RebufferTime']

        # retrieve previous state
        if len(self.s_batch) == 0:
            state = [np.zeros((S_INFO, S_LEN))]
        else:
            state = np.array(self.s_batch[-1], copy=True)

        # compute bandwidth measurement
        video_chunk_fetch_time = post_data['lastChunkFinishTime'] - post_data['lastChunkStartTime']
        video_chunk_size = post_data['lastChunkSize']

        # compute number of video chunks left
        video_chunk_remain = TOTAL_VIDEO_CHUNKS - self.input_dict['video_chunk_coount']
        self.input_dict['video_chunk_coount'] += 1

        # dequeue history record
        state = np.roll(state, -1, axis=1)

        next_video_chunk_sizes = []
        for i in range(A_DIM):
            next_video_chunk_sizes.append(self.get_chunk_size(i, self.input_dict['video_chunk_coount']))

        # this should be S_INFO number of terms
        try:
            state[0, -1] = VIDEO_BIT_RATE[post_data['lastquality']] / float(np.max(VIDEO_BIT_RATE))
            state[1, -1] = post_data['buffer'] / BUFFER_NORM_FACTOR
            state[2, -1] = float(video_chunk_size) / float(video_chunk_fetch_time) / M_IN_K  # kilo byte / ms
            state[3, -1] = float(video_chunk_fetch_time) / M_IN_K / BUFFER_NORM_FACTOR  # 10 sec
            state[4, :A_DIM] = np.array(next_video_chunk_sizes) / M_IN_K / M_IN_K  # mega byte
            state[5, -1] = np.minimum(video_chunk_remain, CHUNK_TIL_VIDEO_END_CAP) / float(CHUNK_TIL_VIDEO_END_CAP)
        except ZeroDivisionError:
            # this should occur VERY rarely (1 out of 3000), should be a dash issue
            # in this case we ignore the observation and roll back to an eariler one
            if len(self.s_batch) == 0:
                state = [np.zeros((S_INFO, S_LEN))]
            else:
                state = np.array(self.s_batch[-1], copy=True)

        # log wall_time, bit_rate, buffer_size, rebuffer_time, video_chunk_size, download_time, reward
        self.log_file.write(str(time.time()) + '\t' +
                            str(VIDEO_BIT_RATE[post_data['lastquality']]) + '\t' +
                            str(post_data['buffer']) + '\t' +
                            str(rebuffer_time / M_IN_K) + '\t' +
                            str(video_chunk_size) + '\t' +
                            str(video_chunk_fetch_time) + '\t' +
                            str(reward) + '\n')
        self.log_file.flush()

        action_prob = self.actor.predict(np.reshape(state, (1, S_INFO, S_LEN)))
        action_cumsum = np.cumsum(action_prob)
        bit_rate = (action_cumsum > np.random.randint(1, RAND_RANGE) / float(RAND_RANGE)).argmax()
        # Note: we need to discretize the probability into 1/RAND_RANGE steps,
        # because there is an intrinsic discrepancy in passing single state and batch states

        # send data to html side
        send_data = bit_rate

#================================================
        return send_data
        #print "TOOK: " + str(end-start)

