import numpy as np
import h5py
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.python.framework import ops
import os
import argparse

os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

# layers_dims_Hp2d = [10, 9, 8, 7, 6, 5, 5, 6, 7, 8, 9, 10]
# layers_dims_Dh = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
# layers_dims_Dm = [20, 18, 16, 14, 12, 10, 8, 6, 4, 2, 1]


def load_dataset():

    train_dataset = h5py.File('output.hdf5', "r")
    train_set_x_orig = np.array(train_dataset["image_dataset"][:]) # your train set features
    train_set_y_orig = np.array(train_dataset["sketch_dataset"][:]) # your train set labels
    train_set_x_flat = train_set_x_orig.reshape(train_set_x_orig.shape[0],-1).T
    train_set_y_flat = train_set_y_orig.reshape(train_set_y_orig.shape[0],-1).T
    return train_set_x_flat/255, train_set_y_flat/255

A, B = load_dataset()

layers_dims_Hp2d = [A.shape[0], 256, 128, 64, 32, 64, 128, 256, A.shape[0]]
layers_dims_Dh = [A.shape[0], 256, 128, 64, 32, 16, 8, 4, 1]
layers_dims_Dm = [A.shape[0]+B.shape[0], 256, 128, 64, 32, 16, 8, 4, 1]

learning_rate = 1
m = 10000
k = 10 #Number of interations of dicriminator training before training generator

minibatch_size = 250
# Makes sure the minibatch size is not larger than the dataset
minibatch_size = min(minibatch_size, A.shape[1])

def create_placeholders(n_P, n_D):
    P = tf.placeholder(tf.float32,[n_P,None], name='P') #Input Photo
    D_real = tf.placeholder(tf.float32,[n_D,None], name='D_real') #Real Doodle
    #D_fake = tf.placeholder(tf.float32,[n_D,None]) #Fake Doodle generator from Hp2d
    #Y_match_real = tf.placeholder(tf.float32,[n_y,None]) #Labels
    #Y_human_real = tf.placeholder(tf.float32,[n_y,None])
    #Y_match_fake = tf.placeholder(tf.float32,[n_y,None]) #Labels
    #Y_human_fake = tf.placeholder(tf.float32,[n_y,None])

    return P, D_real #D_fake Y_match_real, Y_human_real, Y_match

def initialize_parameters(layers_dims_Hp2d, layers_dims_Dh, layers_dims_Dm):
# Per sample, inputs will be 
# Hp2d:  
    parameters_Hp2d = {}
    L = len(layers_dims_Hp2d)            # number of layers in the network
    for l in range(1, L):
        parameters_Hp2d['WHp2d' + str(l)] = tf.get_variable("WHp2d"+str(l), [layers_dims_Hp2d[l],layers_dims_Hp2d[l-1]], initializer = tf.contrib.layers.xavier_initializer(seed = 1))
        parameters_Hp2d['bHp2d' + str(l)] = tf.get_variable("bHp2d"+str(l), [layers_dims_Hp2d[l],1], initializer = tf.zeros_initializer())

    parameters_Dm = {}
    L = len(layers_dims_Dm)            # number of layers in the network
    for l in range(1, L):
        parameters_Dm['WDm' + str(l)] = tf.get_variable("WDm"+str(l), [layers_dims_Dm[l],layers_dims_Dm[l-1]], initializer = tf.contrib.layers.xavier_initializer(seed = 1))
        parameters_Dm['bDm' + str(l)] = tf.get_variable("bDm"+str(l), [layers_dims_Dm[l],1], initializer = tf.zeros_initializer())
       
    parameters_Dh = {}
    L = len(layers_dims_Dh)            # number of layers in the network
    for l in range(1, L):
        parameters_Dh['WDh' + str(l)] = tf.get_variable("WDh"+str(l), [layers_dims_Dh[l],layers_dims_Dh[l-1]], initializer = tf.contrib.layers.xavier_initializer(seed = 1))
        parameters_Dh['bDh' + str(l)] = tf.get_variable("bDh"+str(l), [layers_dims_Dh[l],1], initializer = tf.zeros_initializer())

    return parameters_Hp2d, parameters_Dh, parameters_Dm

def forward_prop(X, parameters, layers_dims, namestring):
    Z = {}
    A = {"A"+namestring+str(0): X}
    
    L = len(layers_dims)
    for l in range(1, L):
        W = parameters['W'+namestring+str(l)]
        b = parameters['b'+namestring+str(l)]
        Z['Z'+namestring+str(l)] = tf.add(tf.matmul(W,A['A'+namestring+str(l-1)]),b)
        A['A'+namestring+str(l)] = tf.nn.sigmoid(Z['Z'+namestring+str(l)])
	
    #print(str(l))
    A_out = A['A'+namestring+str(l)]
    return A_out, Z, A

#cross_entropy = tf.nn.sigmoid_cross_entropy_with_logits()

def Dh_loss(A_human_real, A_human_fake):
    real_loss = cross_entropy(labels = tf.ones_like(A_human_real), logits = A_human_real)
    fake_loss = cross_entropy(labels = tf.zeros_like(A_human_fake), logits = A_human_fake)
    total_loss = real_loss + fake_loss
    return total_loss

def Dm_loss(A_match_real, A_match_fake):
    real_loss = tf.nn.sigmoid_cross_entropy_with_logits(labels = tf.ones_like(A_match_real), logits = A_match_real)
    fake_loss = tf.nn.sigmoid_cross_entropy_with_logits(labels = tf.zeros_like(A_match_fake), logits = A_match_fake)
    total_loss = real_loss + fake_loss
    return total_loss

def Hp2d_loss(A_human_fake, A_match_fake):
    human_loss = tf.nn.sigmoid_cross_entropy_with_logits(labels = tf.ones_like(A_human_fake), logits = A_human_fake)
    match_loss = tf.nn.sigmoid_cross_entropy_with_logits(labels = tf.ones_like(A_match_fake), logits = A_match_fake)
    total_loss = human_loss + match_loss
    return total_loss

# Adds command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--load_checkpoint", required=False, type=bool, default=False, 
    help="Load a checkpoint?")
parser.add_argument("--checkpoint_file", required=False, type=str, default="./checkpoints/GeneratorDiscriminator.ckpt", 
    help="Which checkpoint file?")
args = parser.parse_args()

#Start Trying out the code
ops.reset_default_graph() #reset default graph
P, D_real = create_placeholders(A.shape[0], A.shape[0])

#Initilize Data Inputs Dictionary

with tf.Session() as sess:
    parameters_Hp2d, parameters_Dh, parameters_Dm = initialize_parameters(layers_dims_Hp2d, layers_dims_Dh, layers_dims_Dm)


D_fake, _, _ = forward_prop(P, parameters_Hp2d, layers_dims_Hp2d, "Hp2d")
##PD_real = concatenated version of P and D_real
##PD_fake = concatenated version of P and D_fake
PD_real = tf.concat([P, D_real], 0, name="PD_real")
PD_fake = tf.concat([P, D_fake], 0, name="PD_fake")
A_human_fake, _, _ = forward_prop(D_fake,parameters_Dh, layers_dims_Dh, "Dh")
A_human_real, _, _ = forward_prop(D_real,parameters_Dh, layers_dims_Dh, "Dh")
A_match_fake, _, _ = forward_prop(PD_fake,parameters_Dm, layers_dims_Dm, "Dm")
A_match_real, _, _ = forward_prop(PD_real,parameters_Dm, layers_dims_Dm, "Dm")

# feed_dict = {x: 3}

Loss_Hp2d = Hp2d_loss(A_human_fake, A_match_fake)
Loss_Dm = Dm_loss(A_match_real, A_match_fake)
Loss_Dh = Hp2d_loss(A_human_fake, A_match_fake)

optimizer_Hp2d = tf.train.AdamOptimizer(learning_rate = learning_rate).minimize(Loss_Hp2d, var_list = parameters_Hp2d)
optimizer_Dm = tf.train.AdamOptimizer(learning_rate = learning_rate).minimize(Loss_Dm, var_list = parameters_Dm)
optimizer_Dh = tf.train.AdamOptimizer(learning_rate = learning_rate).minimize(Loss_Dh, var_list = parameters_Dh)

init = tf.global_variables_initializer()

#to create tensorboard graph
writer = tf.summary.FileWriter('./graphs',tf.get_default_graph())

J_Hp2d = ()
J_Dh = ()
J_Dm = ()

saver = tf.train.Saver()

with tf.Session() as sess:
    if args.load_checkpoint:
        saver.restore(sess, args.checkpoint_file)
        print("Session restored from: " + args.checkpoint_file)
        args.load_checkpoint = False
    else:
        print("Starting session from scratch")
        sess.run(init)
    for i in range(1,m):
    #i = m
        print("epoch: ", i)
        for minibatch_iteration in range(int(A.shape[1]/minibatch_size)):
            selection_indices = np.random.choice(A.shape[1], minibatch_size)
            A_minibatch = A[:,selection_indices]
            B_minibatch = B[:,selection_indices]
            print("selection shape: ", A_minibatch.shape)
            #writer = tf.summary.FileWriter('./graphs', sess.graph)
            Loss_Hp2d_, Loss_Dm_, Loss_Dh_, = sess.run(Loss_Hp2d, feed_dict = {P: A_minibatch, D_real: B_minibatch}), sess.run(Loss_Dm, feed_dict = {P: A_minibatch, D_real: B_minibatch}), sess.run(Loss_Dh, feed_dict = {P: A_minibatch, D_real: B_minibatch})
            _, _ = sess.run(optimizer_Dm, feed_dict = {P: A_minibatch, D_real: B_minibatch}), sess.run(optimizer_Dh, feed_dict = {P: A_minibatch, D_real: B_minibatch})
            
            # This should update the generator ones for every k updates to the discriminator
            # It uses the epoch (i) * minibatch updates per epoch (A.shape[1]/minibatch_size) + minibatch number to determine when to update the generator
            if np.mod(i*int(A.shape[1]/minibatch_size)+minibatch_iteration,k) == 0:
                print("Updating generator")
                _ = sess.run(optimizer_Hp2d, feed_dict = {P: A_minibatch, D_real: B_minibatch})
            #J_Hp2d += (Loss_Hp2d_,)
            #J_Dh += (Loss_Dh_,)
            #J_Dm += (Loss_Dm_,)
        if i % 200 == 0:
            save_path = saver.save(sess, "./checkpoints/GeneratorDiscriminator.ckpt")
            print("Saved checkpoint to file: ", save_path)
            
#print("Loss in Hp2d = "+str(Loss_Hp2d_))
#print("Loss in Dh = "+str(Loss_Dh_))
#print("Loss in Dm = "+str(Loss_Dm_))
sess.close()

#plt.plot(Loss_Hp2d_)
#plt.xlabel("Iterations")
#plt.ylabel("Cost Function of Generator")

#plt.show()
#plt.plot(Loss_Dm_)
#plt.xlabel("Iterations")
#plt.ylabel("Cost Function of Match Discriminator")
#plt.show()
#plt.plot(Loss_Dh_)
#plt.xlabel("Iterations")
#plt.ylabel("Cost Function of Drawn by Human Discriminiator")
#plt.show()



#cross_entropy = tf.keras.losses.BinaryCrossentropy(from_logits=True)

#def Dh_loss(real_output, fake_output):
#    real_loss = cross_entropy(tf.ones_like(real_output), real_output)
#    fake_loss = cross_entropy(tf.zeros_like(fake_output), fake_output)
#    total_loss = real_loss + fake_loss
#    return total_loss

#def Dm_loss(real_output, fake_output):
#    real_loss = cross_entropy(tf.ones_like(real_output), real_output)
#    fake_loss = cross_entropy(tf.zeros_like(fake_output), fake_output)
#    total_loss = real_loss + fake_loss
#    return total_loss


#def generator_loss(fake_output):
#    human_loss = 
#    match_loss = cross_entropy(tf.ones_like(fake_output), fake_output)
#    return cross_entropy(tf.ones_like(fake_output), fake_output)
