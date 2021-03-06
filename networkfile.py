# This file contains the definition of the network used to predict IFS parameters
# Created by:   Liam Graham
# Last Updated: June 2020

import torch 
import torch.nn as nn
import os
import numpy as np

def convbr(in_channels, out_channels, kernel_size = 3, stride = 1, padding = 0):
    # Pre-defined concvolutional layer that incorporates batch normalization and 
    # the leaky-ReLU activation function
    #
    # INPUTS:
    #     in_channels:  the number of feature maps of the input
    #     out_channels: the number of output feature maps
    #     kernel_size:  the width or height of the kernel in the convolutional layer
    #     stride:       the stride of the kernel
    #     padding:      the number of layers of zero padding
    #    
    # OUTPUTS:
    #     conv:         a convolutional layer object
                  
    conv = nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size = kernel_size, stride = stride, padding = padding),
        nn.BatchNorm2d(out_channels),
        nn.LeakyReLU())
    return conv

def fcbrd(in_channels, out_channels, dropout = 0):
    # Pre-defined fully connected layer that incorporates batch normalization, the 
    # leaky-ReLU activation function, and dropout (though it is not used)
    #
    # INPUTS:
    #     in_channels:  the length of the input vector
    #     out_channels: the length of the output vector
    #     dropout:      the dropout probability
    #    
    # OUTPUTS:
    #     fc:           a fully connected layer object
    fc = nn.Sequential(
        nn.Dropout(p = dropout),
        nn.Linear(in_channels, out_channels),
        nn.BatchNorm1d(out_channels),
        nn.LeakyReLU()
    )
    return fc

class block(nn.Module):
    # The block class definition used in the neural network
    #
    # INITIALIZATIONS:
    #     channels: the number of features maps of the input and output layers
    #     reduce:   the number of feature maps of the middle layer
    #     ksize:    the size of the kernel in the middel layer
        
    def __init__(self, channels, reduced, ksize):
        super(block, self).__init__()
        self.conv1 = convbr(channels, reduced, kernel_size = 1)
        self.conv2 = convbr(reduced, reduced, kernel_size = ksize, padding = int(ksize/2))
        self.conv3 = convbr(reduced, channels, kernel_size = 1)
    
    #Passing the data forward through the block
    #
    # INPUTS:
    #     x: the output of the previous layer
    #
    # OUTPUTS:
    #     out: the output of the block
    
    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2(out)
        out = self.conv3(out)
        out += x
        return out
    
class FracNet(nn.Module):
    # The class definition of the neural network used to model IFS parameters
    #
    # INITIALIZATIONS:
    #     num_classes: the number of outputs of the network
    #     dropout:     the dropout probability (this was not used)
    #     chunks:      a list of size 7 representing the chunk sizes
    #     ksize:       a list of size 7 representing the kernel size 
    #                  for the layer in each chunk
    #                  note: ksize should only be odd numbers
    #     psize:       a list of size 7 representing the kernel size 
    #                  in each pooling layer
    #                  note: psize should only be even numbers
    
    def __init__(self, num_classes, dropout, chunks, ksize, psize):
        # ATTRIBUTES:
        #     Accuracies:   a numpy array keeping track of the accuracy at 
        #                   tolerance levels 0.1, 0.2, 0.3, 0.4, 0.5,
        #                   measured after each epoch
        #     losses:       a numpy array keeping track of the loss
        #                   at each step
        #     total_epochs: the total epochs for which the model has been 
        #                   trained
        #     num_maps:     the number of feature maps in a given chunk
      
        super(FracNet, self).__init__()
        self.Accuracies = [[0],[0],[0],[0],[0]]
        self.losses = np.array([])
        self.total_epochs = 0
        self.num_classes = num_classes
        num_maps = [8,16,32,64,128,256,512]
        reduce_maps = [8,16,16,32,32,64,128]
        
        #the dimensions after each chunk:
        #640 x 640 
        self.pool0 = convbr(1, num_maps[0], kernel_size = psize[0], stride = 2, padding = 0)
        #316 x 316
        self.chunk0 = self.make_chunk(num_maps[0], chunks[0], reduce_maps[0], ksize[0])
        
        #316 x 316
        self.pool1 = convbr(num_maps[0], num_maps[1], kernel_size = psize[1], stride = 2, padding = 0)
        #154 x 154
        self.chunk1 = self.make_chunk(num_maps[1], chunks[1], reduce_maps[1],ksize[1])
        
        #154 x 154
        self.pool2 = convbr(num_maps[1], num_maps[2], kernel_size = psize[2], stride = 2, padding = 0)
        #74 x 74
        self.chunk2 = self.make_chunk(num_maps[2], chunks[2],reduce_maps[2],ksize[2])
        
        #74 x 74
        self.pool3 = convbr(num_maps[2], num_maps[3], kernel_size = psize[3], stride = 2, padding = 0)
        #34 x 34
        self.chunk3 = self.make_chunk(num_maps[3], chunks[3], reduce_maps[3],ksize[3])
        
        #34 x 34
        self.pool4 = convbr(num_maps[3], num_maps[4], kernel_size = psize[4], stride = 2, padding = 0)
        #16 x 16
        self.chunk4 = self.make_chunk(num_maps[4], chunks[4], reduce_maps[4],ksize[4])
        
        #16 x 16
        self.pool5 = convbr(num_maps[4], num_maps[5], kernel_size = psize[5], stride = 2, padding = 0)
        #7 x 7
        self.chunk5 = self.make_chunk(num_maps[5], chunks[5], reduce_maps[5],ksize[5])
        
        #7 x 7
        self.pool6 = convbr(num_maps[5], num_maps[6], kernel_size = psize[6], stride = 2, padding = 0)
        #3 x 3
        self.chunk6 = self.make_chunk(num_maps[6], chunks[6], reduce_maps[6],ksize[6])
        
        self.fc0 = fcbrd(num_maps[6] * 3 * 3, 1000, dropout = dropout)
        self.fcout = nn.Linear(1000, num_classes)
        
    
    def make_chunk(self, channels, chunks, reduced, ksize):
        # This class function creates the chunks in the network by
        # using the block class above
        #
        # INPUTS:
        #     channels: the number of features maps of the input and output layers
        #               of each block in each chunk
        #     chunks:   the size of the chunk to be made
        #     reduce:   the number of feature maps of the middle layer of each block
        #     ksize:    the size of the kernel in the middel layer of each block
        layers = []
        for i in range(chunks):
            layers.append(block(channels, reduced, ksize))
        return nn.Sequential(*layers)
    
    def forward(self, x):
        #Passing the data forward through the block
        #
        # INPUTS:
        #     x: the output of the previous layer
        #
        # OUTPUTS:
        #     out: the output of the block
        
        out = self.pool0(x)
        out = self.chunk0(out)
        
        out = self.pool1(out)
        out = self.chunk1(out)
        
        out = self.pool2(out)
        out = self.chunk2(out)
        
        out = self.pool3(out)
        out = self.chunk3(out)
        
        out = self.pool4(out)
        out = self.chunk4(out)
        
        out = self.pool5(out)
        out = self.chunk5(out)
        
        out = self.pool6(out)
        out = self.chunk6(out)

        out = out.reshape(out.size(0), -1)
        
        out = self.fc0(out)
        out = self.fcout(out)
        return out
    
