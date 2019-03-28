"""
This code is for illustration purpose only.
Use multi_agent.py for better performance and speed.
"""

import os
import numpy as np
import tensorflow as tf
import a3c


S_INFO = 14  # bit_rate, buffer_size, next_chunk_size, bandwidth_measurement(throughput and time), chunk_til_video_end
S_LEN = 8  # take how many frames in the past
A_DIM = 6
ACTOR_LR_RATE = 0.0001
CRITIC_LR_RATE = 0.001
TRAIN_SEQ_LEN = 100  # take as a train batch
MODEL_SAVE_INTERVAL = 100
M_IN_K = 1000.0
RAND_RANGE = 1000000
GRADIENT_BATCH_SIZE = 16

DEFAULT_ACTION = 0

class PensiveLearner():
    def __init__(self, actionset = [], infoDept=S_LEN, log_path=None, summary_dir=None, nn_model=None):
        
        assert summary_dir
        self.summary_dir = summary_dir
        self.nn_model = nn_model

        self.a_dim = len(actionset)
        self._vActionset = actionset

        self._vInfoDim = S_INFO
        self._vInfoDept = infoDept


        if not os.path.exists(self.summary_dir):
            os.makedirs(self.summary_dir)

        self.sess = tf.Session()
#         log_file = open(os.path.join(log_path, "PensiveLearner", "wb"))


        self.actor = a3c.ActorNetwork(self.sess,
                                 state_dim=[self._vInfoDim, self._vInfoDept], action_dim=self.a_dim,
                                 learning_rate=ACTOR_LR_RATE)

        self.critic = a3c.CriticNetwork(self.sess,
                                   state_dim=[self._vInfoDim, self._vInfoDept], action_dim=self.a_dim,
                                   learning_rate=CRITIC_LR_RATE)

        self.summary_ops, self.summary_vars = a3c.build_summaries()

        self.sess.run(tf.global_variables_initializer())
        self.writer = tf.summary.FileWriter(self.summary_dir, self.sess.graph)  # training monitor
        self.saver = tf.train.Saver()  # save neural net parameters

        # restore neural net parameters
#         nn_model = NN_MODEL
        if self.nn_model is not None:  # nn_model is the path to file
            self.saver.restore(self.sess, self.nn_model)
            print("Model restored.")

        self.epoch = 0


        self.s_batch = []
        self.a_batch = []
        self.r_batch = []
        self.entropy_record = []

        self.actor_gradient_batch = []
        self.critic_gradient_batch = []

        self.keyedSBatch = {}
        self.keyedActionProb = {}
        self.keyedAction = {}

    def getNextAction(self, peerId, segId, state): #peerId and segId are Identifier
        timeBudget, localQualities_, elapsedLocal, \
            downloadedLocal, clenLocal, throughputLocal_, \
            downloadStartedLocal_, downloadFinishedLocal_, \
            elapsedRemote, downloadedRemote, clenRemote, \
            throughputRemote_, downloadStartedRemote_, \
            downloadFinishedRemote_ = state
        

        v_dim = len(downloadStartedLocal_)

        # reward is video quality - rebuffer penalty - smooth penalty
        # retrieve previous state
        if len(self.s_batch) == 0:
            state = np.zeros((self._vInfoDim, self._vInfoDept))
        else:
            state = np.array(self.s_batch[-1], copy=True)

        # dequeue history record
        state = np.roll(state, -1, axis=1)

        state[ 0, -1]       = timeBudget
        state[ 1, :v_dim]   = localQualities_
        state[ 2, -1]       = elapsedLocal
        state[ 3, -1]       = downloadedLocal
        state[ 4, -1]       = clenLocal
        state[ 5, :v_dim]   = throughputLocal_
        state[ 6, :v_dim]   = downloadStartedLocal_
        state[ 7, :v_dim]   = downloadFinishedLocal_
        state[ 8, -1]       = elapsedRemote
        state[ 9, -1]       = downloadedRemote
        state[10, -1]       = clenRemote
        state[11, :v_dim]   = throughputRemote_
        state[12, :v_dim]   = downloadStartedRemote_
        state[13, :v_dim]   = downloadFinishedRemote_


        action_prob = self.actor.predict(np.reshape(state, (1, self._vInfoDim, self._vInfoDept)))
        action_cumsum = np.cumsum(action_prob)
        action = (action_cumsum > np.random.randint(1, RAND_RANGE) / float(RAND_RANGE)).argmax()
        # Note: we need to discretize the probability into 1/RAND_RANGE steps,
        # because there is an intrinsic discrepancy in passing single state and batch states
        
        self.keyedSBatch[(peerId, segId)] = state
        self.keyedActionProb[(peerId, segId)] = action_prob
        self.keyedAction[(peerId, segId)] = action

        return self._vActionset[action]

    def addReward(self, peerId, segId, reward): 
        assert (peerId, segId) in self.keyedSBatch and (peerId, segId) in self.keyedActionProb
        
        state = self.keyedSBatch[(peerId, segId)]
        action_prob = self.keyedActionProb[(peerId, segId)]
        action = self.keyedAction[(peerId, segId)]

        del self.keyedSBatch[(peerId, segId)]
        del self.keyedActionProb[(peerId, segId)]
        del self.keyedAction[(peerId, segId)]

        self.r_batch.append(reward)
        
        self.entropy_record.append(a3c.compute_entropy(action_prob[0]))

        self.s_batch.append(state)

        action_vec = np.zeros(self.a_dim)
        action_vec[action] = 1
        self.a_batch.append(action_vec)


        if len(self.r_batch) >= TRAIN_SEQ_LEN:  # do training once
            self.saveModel()

    def saveModel(self, end_of_video=False):
        actor_gradient, critic_gradient, td_batch = \
            a3c.compute_gradients(s_batch=np.stack(self.s_batch, axis=0),  # ignore the first chuck
                                  a_batch=np.vstack(self.a_batch),  # since we don't have the
                                  r_batch=np.vstack(self.r_batch),  # control over it
                                  terminal=end_of_video, actor=self.actor, critic=self.critic)
        td_loss = np.mean(td_batch)

        self.actor_gradient_batch.append(actor_gradient)
        self.critic_gradient_batch.append(critic_gradient)

        print("====")
        print("Epoch", self.epoch)
        print("TD_loss", td_loss, "Avg_reward", np.mean(self.r_batch), "Avg_entropy", np.mean(self.entropy_record))
        print("====")

        summary_str = self.sess.run(self.summary_ops, feed_dict={
            self.summary_vars[0]: td_loss,
            self.summary_vars[1]: np.mean(self.r_batch),
            self.summary_vars[2]: np.mean(self.entropy_record)
        })

        self.writer.add_summary(summary_str, self.epoch)
        self.writer.flush()

        self.entropy_record = []

        if len(self.actor_gradient_batch) >= GRADIENT_BATCH_SIZE:

            assert len(self.actor_gradient_batch) == len(self.critic_gradient_batch)
            # assembled_actor_gradient = actor_gradient_batch[0]
            # assembled_critic_gradient = critic_gradient_batch[0]
            # assert len(actor_gradient_batch) == len(critic_gradient_batch)
            # for i in xrange(len(actor_gradient_batch) - 1):
            #     for j in xrange(len(actor_gradient)):
            #         assembled_actor_gradient[j] += actor_gradient_batch[i][j]
            #         assembled_critic_gradient[j] += critic_gradient_batch[i][j]
            # actor.apply_gradients(assembled_actor_gradient)
            # critic.apply_gradients(assembled_critic_gradient)

            for i in range(len(self.actor_gradient_batch)):
                self.actor.apply_gradients(self.actor_gradient_batch[i])
                self.critic.apply_gradients(self.critic_gradient_batch[i])

            self.actor_gradient_batch = []
            self.critic_gradient_batch = []

            self.epoch += 1
            if self.epoch % MODEL_SAVE_INTERVAL == 0:
                # Save the neural net parameters to disk.
                save_path = self.saver.save(self.sess, self.summary_dir + "/nn_model_ep_" +
                                       str(self.epoch) + ".ckpt")
                print("Model saved in file: %s" % save_path)

        del self.s_batch[:]
        del self.a_batch[:]
        del self.r_batch[:]

    def finish(self):
        if len(self.r_batch) == 0:
            return
        self.saveModel(True)



PENSIEVE_LEARNER_INSTANT=None
def getPensiveLearner(actionset = [], infoDept=S_LEN, log_path=None, summary_dir=None, *kw, **kws):
    global PENSIEVE_LEARNER_INSTANT
    if PENSIEVE_LEARNER_INSTANT:
        p = PENSIEVE_LEARNER_INSTANT
        assert p._vActionset == actionset and p._vInfoDept == infoDept
        return p

    PENSIEVE_LEARNER_INSTANT = PensiveLearner(actionset, infoDept, log_path, summary_dir, *kw, **kws)
    return PENSIEVE_LEARNER_INSTANT


def saveLearner():
    if PENSIEVE_LEARNER_INSTANT:
        PENSIEVE_LEARNER_INSTANT.finish()
